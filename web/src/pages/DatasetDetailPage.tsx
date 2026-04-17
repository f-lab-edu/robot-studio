import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import {
  getDatasetInfo,
  listEpisodes,
  getEpisodeFrames,
  getVideoUrls,
  getVideoProxyUrl,
  type DatasetInfo,
  type Episode,
  type EpisodeFramesResponse,
  type FrameData,
  type VideoUrl,
} from "../api/datasets";
import "./DatasetDetailPage.css";

const STATE_COLORS = ["#7c3aed", "#2563eb", "#0891b2", "#059669", "#d97706", "#dc2626"];
const ACTION_COLORS = ["#c4b5fd", "#93c5fd", "#67e8f9", "#6ee7b7", "#fcd34d", "#fca5a5"];

export default function DatasetDetailPage() {
  const { name } = useParams<{ name: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedIdx = Number(searchParams.get("episode") ?? "0");

  const [info, setInfo] = useState<DatasetInfo | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loadingMeta, setLoadingMeta] = useState(true);
  const [metaError, setMetaError] = useState<string | null>(null);

  const [videoUrls, setVideoUrls] = useState<VideoUrl[]>([]);
  const [framesData, setFramesData] = useState<EpisodeFramesResponse | null>(null);
  const [loadingEpisode, setLoadingEpisode] = useState(false);
  const [episodeError, setEpisodeError] = useState<string | null>(null);

  const [currentTime, setCurrentTime] = useState(0);
  const [currentFrame, setCurrentFrame] = useState<FrameData | null>(null);

  const masterRef = useRef<HTMLVideoElement | null>(null);
  const slaveRefs = useRef<HTMLVideoElement[]>([]);

  // 데이터셋 메타 + 에피소드 목록 로드
  useEffect(() => {
    if (!name) return;
    setLoadingMeta(true);
    Promise.all([getDatasetInfo(name), listEpisodes(name)])
      .then(([i, eps]) => {
        setInfo(i);
        setEpisodes(eps);
      })
      .catch((e) => setMetaError(e.message))
      .finally(() => setLoadingMeta(false));
  }, [name]);

  // 선택된 에피소드 데이터 로드
  useEffect(() => {
    if (!name || episodes.length === 0) return;
    setLoadingEpisode(true);
    setEpisodeError(null);
    setCurrentTime(0);
    setCurrentFrame(null);
    slaveRefs.current = [];

    Promise.all([
      getVideoUrls(name, selectedIdx),
      getEpisodeFrames(name, selectedIdx),
    ])
      .then(([urls, frames]) => {
        setVideoUrls(urls);
        setFramesData(frames);
        if (frames.frames.length > 0) setCurrentFrame(frames.frames[0]);
      })
      .catch((e) => setEpisodeError(e.message))
      .finally(() => setLoadingEpisode(false));
  }, [name, selectedIdx, episodes.length]);

  // 마스터 비디오 동기화
  useEffect(() => {
    const master = masterRef.current;
    if (!master || !framesData) return;

    const onTimeUpdate = () => {
      const t = master.currentTime;
      setCurrentTime(t);
      slaveRefs.current.forEach((slave) => {
        if (slave && Math.abs(slave.currentTime - t) > 0.1) slave.currentTime = t;
      });
      const frameIdx = Math.min(
        Math.floor(t * framesData.fps),
        framesData.frames.length - 1
      );
      if (frameIdx >= 0) setCurrentFrame(framesData.frames[frameIdx]);
    };

    const onPlay = () => slaveRefs.current.forEach((s) => s?.play());
    const onPause = () => slaveRefs.current.forEach((s) => s?.pause());
    const onSeeked = () =>
      slaveRefs.current.forEach((s) => {
        if (s) s.currentTime = master.currentTime;
      });

    master.addEventListener("timeupdate", onTimeUpdate);
    master.addEventListener("play", onPlay);
    master.addEventListener("pause", onPause);
    master.addEventListener("seeked", onSeeked);

    return () => {
      master.removeEventListener("timeupdate", onTimeUpdate);
      master.removeEventListener("play", onPlay);
      master.removeEventListener("pause", onPause);
      master.removeEventListener("seeked", onSeeked);
    };
  }, [framesData]);

  const selectEpisode = (idx: number) => {
    setSearchParams({ episode: String(idx) });
  };

  const jointNames =
    info?.features["observation.state"]?.names ??
    ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"];

  const chartData = (() => {
    if (!framesData) return [];
    const frames = framesData.frames;
    const step = Math.max(1, Math.floor(frames.length / 500));
    return frames
      .filter((_, i) => i % step === 0)
      .map((f) => {
        const point: Record<string, number> = {
          time: parseFloat((f.frame_index / framesData.fps).toFixed(2)),
        };
        jointNames.forEach((jname, i) => {
          point[`state_${jname}`] = f.observation_state[i] ?? 0;
          point[`action_${jname}`] = f.action[i] ?? 0;
        });
        return point;
      });
  })();

  const selectedEpisode = episodes.find((ep) => ep.episode_index === selectedIdx);

  if (loadingMeta) {
    return (
      <div className="dd-page">
        <nav className="navbar">
          <Link to="/datasets" className="navbar-logo">⬡ Robot Studio</Link>
        </nav>
        <p className="dd-state-msg">Loading...</p>
      </div>
    );
  }

  if (metaError || !info) {
    return (
      <div className="dd-page">
        <nav className="navbar">
          <Link to="/datasets" className="navbar-logo">⬡ Robot Studio</Link>
        </nav>
        <p className="dd-state-msg dd-state-error">{metaError ?? "Not found"}</p>
      </div>
    );
  }

  return (
    <div className="dd-page">
      <nav className="navbar">
        <Link to="/datasets" className="navbar-logo">⬡ Robot Studio</Link>
        <span className="dd-nav-sep">·</span>
        <span className="dd-nav-name">{info.name}</span>
        <div className="dd-nav-badges">
          <span className="badge badge-purple">{info.robot_type}</span>
          <span className="badge badge-gray">{info.fps} fps</span>
          <span className="badge badge-gray">{info.total_episodes} episodes</span>
          <span className="badge badge-gray">{info.total_frames.toLocaleString()} frames</span>
        </div>
      </nav>

      <div className="dd-layout">
        {/* 왼쪽 사이드바 */}
        <aside className="dd-sidebar">
          <div className="dd-sidebar-header">
            <span className="label">Episodes</span>
            <span className="badge badge-gray">{episodes.length}</span>
          </div>
          <div className="dd-sidebar-list">
            {episodes.map((ep) => (
              <button
                key={ep.episode_index}
                className={`dd-ep-item ${ep.episode_index === selectedIdx ? "selected" : ""}`}
                onClick={() => selectEpisode(ep.episode_index)}
              >
                <div className="dd-ep-top">
                  <span className="dd-ep-index">Ep #{ep.episode_index}</span>
                  <span className={`dd-ep-status ${ep.success ? "success" : "fail"}`}>
                    {ep.success ? "✓" : "✗"}
                  </span>
                </div>
                {ep.language_instruction && (
                  <span className="dd-ep-instruction">{ep.language_instruction}</span>
                )}
                <span className="dd-ep-frames">{ep.length} frames</span>
              </button>
            ))}
          </div>
        </aside>

        {/* 메인 콘텐츠 */}
        <main className="dd-main">
          {loadingEpisode && <p className="dd-state-msg">Loading episode...</p>}
          {episodeError && (
            <p className="dd-state-msg dd-state-error">Error: {episodeError}</p>
          )}

          {!loadingEpisode && !episodeError && (
            <>
              {/* 에피소드 헤더 */}
              <div className="dd-ep-header">
                <h2 className="dd-ep-title">Episode #{selectedIdx}</h2>
                {selectedEpisode && (
                  <span
                    className={`dd-ep-badge ${selectedEpisode.success ? "success" : "fail"}`}
                  >
                    {selectedEpisode.success ? "Success" : "Fail"}
                  </span>
                )}
                {selectedEpisode?.language_instruction && (
                  <span className="dd-ep-instr-tag">
                    {selectedEpisode.language_instruction}
                  </span>
                )}
              </div>

              {/* 비디오 섹션 */}
              {videoUrls.length > 0 && (
                <section className="dd-section glass-card">
                  <div className="dd-section-title">
                    <span className="label">Video</span>
                    {videoUrls.length > 1 && (
                      <span className="dd-sync-note">
                        ※ 상단 영상 컨트롤로 재생 시 나머지 영상 자동 동기화
                      </span>
                    )}
                  </div>
                  <div
                    className="dd-video-grid"
                    style={{
                      gridTemplateColumns: `repeat(${Math.min(videoUrls.length, 3)}, 1fr)`,
                    }}
                  >
                    {videoUrls.map((v, i) => (
                      <div key={v.camera} className="dd-video-wrap">
                        <span className="dd-camera-label label">
                          {v.camera.replace("observation.images.", "")}
                        </span>
                        <video
                          ref={(el) => {
                            if (i === 0) masterRef.current = el;
                            else if (el) slaveRefs.current[i - 1] = el;
                          }}
                          src={getVideoProxyUrl(name ?? "", selectedIdx, v.camera)}
                          preload="auto"
                          className="dd-video"
                          controls={i === 0}
                          onError={(e) => {
                            const vid = e.currentTarget;
                            console.error(`Video error [${v.camera}]`, vid.error);
                          }}
                        />
                      </div>
                    ))}
                  </div>
                </section>
              )}

              {/* 모터 데이터 섹션 */}
              {framesData && (
                <section className="dd-section glass-card">
                  <div className="dd-section-title">
                    <span className="label">Motor Data</span>
                    {currentFrame && (
                      <span className="dd-frame-badge">
                        Frame {currentFrame.frame_index}
                      </span>
                    )}
                  </div>

                  {/* 조인트 테이블 */}
                  <div className="dd-joint-table-wrap">
                    <table className="dd-joint-table">
                      <thead>
                        <tr>
                          <th>Joint</th>
                          <th>State (follower)</th>
                          <th>Action (leader)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {jointNames.map((jname, i) => (
                          <tr key={jname}>
                            <td className="dd-joint-name">{jname}</td>
                            <td className="dd-joint-val">
                              {currentFrame
                                ? (currentFrame.observation_state[i]?.toFixed(1) ?? "—")
                                : "—"}
                            </td>
                            <td className="dd-joint-val">
                              {currentFrame
                                ? (currentFrame.action[i]?.toFixed(1) ?? "—")
                                : "—"}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  {/* 차트 */}
                  {chartData.length > 0 && (
                    <div className="dd-chart-wrap">
                      <p className="dd-chart-note label">Trajectory — state: solid / action: dashed</p>
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
                          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                          <XAxis
                            dataKey="time"
                            label={{ value: "time (s)", position: "insideBottomRight", offset: -8 }}
                            tick={{ fontSize: 11, fill: "var(--text-3)" }}
                          />
                          <YAxis tick={{ fontSize: 11, fill: "var(--text-3)" }} />
                          <Tooltip
                            contentStyle={{
                              background: "rgba(255,255,255,0.95)",
                              border: "1px solid var(--border)",
                              borderRadius: 8,
                              fontSize: 12,
                            }}
                          />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <ReferenceLine
                            x={parseFloat(currentTime.toFixed(2))}
                            stroke="var(--purple)"
                            strokeWidth={2}
                            label={{ value: "▶", fill: "var(--purple)", fontSize: 11 }}
                          />
                          {jointNames.map((jname, i) => (
                            <Line
                              key={`state_${jname}`}
                              type="monotone"
                              dataKey={`state_${jname}`}
                              stroke={STATE_COLORS[i % STATE_COLORS.length]}
                              dot={false}
                              strokeWidth={1.5}
                              name={`state: ${jname}`}
                            />
                          ))}
                          {jointNames.map((jname, i) => (
                            <Line
                              key={`action_${jname}`}
                              type="monotone"
                              dataKey={`action_${jname}`}
                              stroke={ACTION_COLORS[i % ACTION_COLORS.length]}
                              dot={false}
                              strokeWidth={1.5}
                              strokeDasharray="4 2"
                              name={`action: ${jname}`}
                            />
                          ))}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </section>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}

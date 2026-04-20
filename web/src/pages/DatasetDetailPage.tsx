import { useCallback, useEffect, useRef, useState } from "react";
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
import RobotViewer from "./RobotViewer";

const STATE_COLORS = ["#7c3aed", "#2563eb", "#0891b2", "#059669", "#d97706", "#dc2626"];
const ACTION_COLORS = ["#c4b5fd", "#93c5fd", "#67e8f9", "#6ee7b7", "#fcd34d", "#fca5a5"];
const CHART_GROUP_SIZE = 3;

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
  const [isPlaying, setIsPlaying] = useState(false);
  const [duration, setDuration] = useState(0);
  const [hiddenCameras, setHiddenCameras] = useState<Set<string>>(new Set());

  const [trailKey, setTrailKey] = useState(0);
  const playIntervalRef = useRef<number | null>(null);
  const isPlayingRef = useRef(isPlaying);
  isPlayingRef.current = isPlaying;

  const videoRefs = useRef<Map<string, HTMLVideoElement>>(new Map());

  useEffect(() => {
    if (!name) return;
    setLoadingMeta(true);
    Promise.all([getDatasetInfo(name), listEpisodes(name)])
      .then(([i, eps]) => { setInfo(i); setEpisodes(eps); })
      .catch((e) => setMetaError(e.message))
      .finally(() => setLoadingMeta(false));
  }, [name]);

  useEffect(() => {
    if (!name || episodes.length === 0) return;
    setLoadingEpisode(true);
    setEpisodeError(null);
    setCurrentTime(0);
    setCurrentFrame(null);
    setIsPlaying(false);
    setDuration(0);
    setHiddenCameras(new Set());
    setTrailKey((k) => k + 1);
    if (playIntervalRef.current !== null) {
      clearInterval(playIntervalRef.current);
      playIntervalRef.current = null;
    }
    videoRefs.current.clear();

    Promise.all([getVideoUrls(name, selectedIdx), getEpisodeFrames(name, selectedIdx)])
      .then(([urls, frames]) => {
        setVideoUrls(urls);
        setFramesData(frames);
        if (frames.frames.length > 0) setCurrentFrame(frames.frames[0]);
      })
      .catch((e) => setEpisodeError(e.message))
      .finally(() => setLoadingEpisode(false));
  }, [name, selectedIdx, episodes.length]);

  const firstCameraKey = videoUrls.find((v) => !hiddenCameras.has(v.camera))?.camera;

  useEffect(() => {
    const masterVid = firstCameraKey ? videoRefs.current.get(firstCameraKey) : null;
    if (!masterVid || !framesData) return;

    const onLoadedMetadata = () => setDuration(masterVid.duration);
    const onTimeUpdate = () => {
      const t = masterVid.currentTime;
      setCurrentTime(t);
      videoRefs.current.forEach((vid, cam) => {
        if (cam !== firstCameraKey && Math.abs(vid.currentTime - t) > 0.1)
          vid.currentTime = t;
      });
      const frameIdx = Math.min(
        Math.floor(t * framesData.fps),
        framesData.frames.length - 1
      );
      if (frameIdx >= 0) setCurrentFrame(framesData.frames[frameIdx]);
    };
    const onPlay = () => {
      setIsPlaying(true);
      videoRefs.current.forEach((vid, cam) => { if (cam !== firstCameraKey) vid.play(); });
    };
    const onPause = () => {
      setIsPlaying(false);
      videoRefs.current.forEach((vid, cam) => { if (cam !== firstCameraKey) vid.pause(); });
    };
    const onSeeked = () => {
      videoRefs.current.forEach((vid, cam) => {
        if (cam !== firstCameraKey) vid.currentTime = masterVid.currentTime;
      });
    };

    masterVid.addEventListener("loadedmetadata", onLoadedMetadata);
    masterVid.addEventListener("timeupdate", onTimeUpdate);
    masterVid.addEventListener("play", onPlay);
    masterVid.addEventListener("pause", onPause);
    masterVid.addEventListener("seeked", onSeeked);

    return () => {
      masterVid.removeEventListener("loadedmetadata", onLoadedMetadata);
      masterVid.removeEventListener("timeupdate", onTimeUpdate);
      masterVid.removeEventListener("play", onPlay);
      masterVid.removeEventListener("pause", onPause);
      masterVid.removeEventListener("seeked", onSeeked);
    };
  }, [framesData, firstCameraKey]);

  const selectEpisode = (idx: number) => setSearchParams({ episode: String(idx) });

  const togglePlayPause = useCallback(() => {
    const vid = firstCameraKey ? videoRefs.current.get(firstCameraKey) : null;
    if (!vid) return;
    if (vid.paused) vid.play();
    else vid.pause();
  }, [firstCameraKey]);

  const handleSeek = useCallback(
    (ratio: number) => {
      const time = ratio * duration;
      videoRefs.current.forEach((vid) => { vid.currentTime = time; });
      setCurrentTime(time);
      if (framesData) {
        const frameIdx = Math.min(
          Math.floor(time * framesData.fps),
          framesData.frames.length - 1
        );
        if (frameIdx >= 0) setCurrentFrame(framesData.frames[frameIdx]);
      }
    },
    [duration, framesData]
  );

  const stepFrame = useCallback(
    (delta: number) => {
      if (!framesData || duration === 0) return;
      const newTime = Math.max(
        0,
        Math.min(duration, currentTime + (delta / framesData.fps))
      );
      handleSeek(newTime / duration);
    },
    [framesData, duration, currentTime, handleSeek]
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;
      if (e.code === "Space") { e.preventDefault(); togglePlayPause(); }
      if (e.code === "ArrowUp") { e.preventDefault(); selectEpisode(Math.min(selectedIdx + 1, episodes.length - 1)); }
      if (e.code === "ArrowDown") { e.preventDefault(); selectEpisode(Math.max(selectedIdx - 1, 0)); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlayPause, selectedIdx, episodes.length]);

  const handleFullscreen = (camera: string) => {
    const vid = videoRefs.current.get(camera);
    if (vid?.requestFullscreen) vid.requestFullscreen();
  };

  const jointNames =
    info?.features["observation.state"]?.names ??
    ["shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper"];

  const jointGroups: string[][] = [];
  for (let i = 0; i < jointNames.length; i += CHART_GROUP_SIZE) {
    jointGroups.push(jointNames.slice(i, i + CHART_GROUP_SIZE));
  }

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
  const visibleVideos = videoUrls.filter((v) => !hiddenCameras.has(v.camera));

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
        <span className="badge badge-purple" style={{ marginLeft: 8 }}>{info.robot_type}</span>
      </nav>

      <div className="dd-layout">
        <aside className="dd-sidebar">
          <div className="dd-sidebar-stats">
            <div className="dd-sidebar-stat">
              <span className="label">Frames</span>
              <span className="dd-stat-val">{info.total_frames.toLocaleString()}</span>
            </div>
            <div className="dd-sidebar-stat">
              <span className="label">Episodes</span>
              <span className="dd-stat-val">{info.total_episodes}</span>
            </div>
            <div className="dd-sidebar-stat">
              <span className="label">FPS</span>
              <span className="dd-stat-val">{info.fps}</span>
            </div>
          </div>

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
                  <span className="dd-ep-index">Episode {ep.episode_index}</span>
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

        <div className="dd-main-wrapper">
          <main className="dd-main">
            {loadingEpisode && <p className="dd-state-msg">Loading episode...</p>}
            {episodeError && (
              <p className="dd-state-msg dd-state-error">Error: {episodeError}</p>
            )}

            {!loadingEpisode && !episodeError && (
              <>
                <div className="dd-ep-header">
                  <span className="dd-nav-name">{info.name}</span>
                  <span className="dd-nav-sep">·</span>
                  <span className="dd-ep-title">episode {selectedIdx}</span>
                  {selectedEpisode && (
                    <span className={`dd-ep-badge ${selectedEpisode.success ? "success" : "fail"}`}>
                      {selectedEpisode.success ? "Success" : "Fail"}
                    </span>
                  )}
                </div>

                <div>
                  {hiddenCameras.size > 0 && (
                    <button
                      className="dd-restore-cameras"
                      onClick={() => setHiddenCameras(new Set())}
                    >
                      + 숨겨진 카메라 {hiddenCameras.size}개 표시
                    </button>
                  )}
                  <div className="dd-video-grid">
                    {framesData && (
                      <div className="dd-video-card glass-card">
                        <div className="dd-video-card-header">
                          <span className="dd-camera-label label">3D Replay</span>
                        </div>
                        <div className="dd-3d-video-canvas">
                          <RobotViewer
                            jointPositions={
                              currentFrame
                                ? Object.fromEntries(
                                    jointNames.map((jname, i) => [jname, currentFrame.observation_state[i] ?? 0])
                                  )
                                : {}
                            }
                            showTrail={true}
                            isPlaying={isPlaying}
                            trailKey={trailKey}
                          />
                        </div>
                      </div>
                    )}
                    {visibleVideos.map((v) => (
                      <div key={v.camera} className="dd-video-card glass-card">
                        <div className="dd-video-card-header">
                          <span className="dd-camera-label label">
                            {v.camera.replace("observation.images.", "")}
                          </span>
                          <div className="dd-video-card-actions">
                            <button
                              className="dd-video-action-btn"
                              onClick={() => handleFullscreen(v.camera)}
                              title="전체화면"
                            >
                              ⛶
                            </button>
                            <button
                              className="dd-video-action-btn"
                              onClick={() =>
                                setHiddenCameras((prev) => new Set([...prev, v.camera]))
                              }
                              title="닫기"
                            >
                              ×
                            </button>
                          </div>
                        </div>
                        <video
                          ref={(el) => {
                            if (el) videoRefs.current.set(v.camera, el);
                            else videoRefs.current.delete(v.camera);
                          }}
                          src={getVideoProxyUrl(name ?? "", selectedIdx, v.camera)}
                          preload="auto"
                          className="dd-video"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {selectedEpisode?.language_instruction && (
                  <div className="dd-lang-instruction glass-card">
                    <span className="label">Language Instruction</span>
                    <p className="dd-lang-text">{selectedEpisode.language_instruction}</p>
                  </div>
                )}

                {framesData && (
                  <div className="dd-data-grid">
                    <div className="dd-data-cell glass-card">
                      <div className="dd-data-cell-header">
                        <span className="label">Joint State</span>
                        {currentFrame && (
                          <span className="dd-frame-badge">
                            Frame {currentFrame.frame_index}
                          </span>
                        )}
                      </div>
                      <div className="dd-joint-table-wrap">
                        <table className="dd-joint-table">
                          <thead>
                            <tr>
                              <th>Joint</th>
                              <th>State</th>
                              <th>Action</th>
                            </tr>
                          </thead>
                          <tbody>
                            {jointNames.map((jname, i) => (
                              <tr key={jname}>
                                <td className="dd-joint-name">{jname}</td>
                                <td className="dd-joint-val dd-val-state">
                                  {currentFrame
                                    ? (currentFrame.observation_state[i]?.toFixed(2) ?? "—")
                                    : "—"}
                                </td>
                                <td className="dd-joint-val dd-val-action">
                                  {currentFrame
                                    ? (currentFrame.action[i]?.toFixed(2) ?? "—")
                                    : "—"}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>

                    {chartData.length > 0 &&
                      jointGroups.map((group, gi) => {
                        const groupOffset = gi * CHART_GROUP_SIZE;
                        return (
                          <div key={gi} className="dd-data-cell glass-card">
                            <div className="dd-data-cell-header">
                              <span className="label dd-chart-group-label">
                                {group.join(", ")}
                              </span>
                              <span className="dd-chart-hint label">━ state · ╌ action</span>
                            </div>
                            <ResponsiveContainer width="100%" height={200}>
                              <LineChart
                                data={chartData}
                                margin={{ top: 4, right: 8, bottom: 4, left: -16 }}
                              >
                                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                                <XAxis
                                  dataKey="time"
                                  tick={{ fontSize: 10, fill: "var(--text-3)" }}
                                />
                                <YAxis tick={{ fontSize: 10, fill: "var(--text-3)" }} />
                                <Tooltip
                                  contentStyle={{
                                    background: "rgba(255,255,255,0.95)",
                                    border: "1px solid var(--border)",
                                    borderRadius: 8,
                                    fontSize: 11,
                                  }}
                                />
                                <Legend wrapperStyle={{ fontSize: 10 }} />
                                <ReferenceLine
                                  x={currentFrame
                                    ? parseFloat((currentFrame.frame_index / framesData.fps).toFixed(2))
                                    : 0}
                                  stroke="var(--orange)"
                                  strokeWidth={1.5}
                                />
                                {group.flatMap((jname, i) => {
                                  const ci = (groupOffset + i) % STATE_COLORS.length;
                                  return [
                                    <Line
                                      key={`state_${jname}`}
                                      type="monotone"
                                      dataKey={`state_${jname}`}
                                      stroke={STATE_COLORS[ci]}
                                      dot={false}
                                      strokeWidth={1.5}
                                      name={jname}
                                      isAnimationActive={false}
                                    />,
                                    <Line
                                      key={`action_${jname}`}
                                      type="monotone"
                                      dataKey={`action_${jname}`}
                                      stroke={ACTION_COLORS[ci]}
                                      dot={false}
                                      strokeWidth={1.5}
                                      strokeDasharray="4 2"
                                      name={`${jname}(a)`}
                                      isAnimationActive={false}
                                    />,
                                  ];
                                })}
                              </LineChart>
                            </ResponsiveContainer>
                          </div>
                        );
                      })}
                  </div>
                )}
              </>
            )}
          </main>

          {framesData && !loadingEpisode && (
            <div className="dd-playbar">
              <button className="dd-playbar-btn" onClick={() => stepFrame(-1)} title="이전 프레임">
                ⏮
              </button>
              <button className="dd-playbar-btn dd-play-btn" onClick={togglePlayPause}>
                {isPlaying ? "⏸" : "▶"}
              </button>
              <button className="dd-playbar-btn" onClick={() => stepFrame(1)} title="다음 프레임">
                ⏭
              </button>
              <input
                type="range"
                min={0}
                max={1}
                step={0.001}
                value={duration > 0 ? currentTime / duration : 0}
                onChange={(e) => handleSeek(Number(e.target.value))}
                className="dd-scrubber"
              />
              <span className="dd-frame-counter">
                {currentFrame?.frame_index ?? 0} / {framesData.frames.length - 1}
              </span>
              <span className="dd-key-hint">Space: play/pause · ↑↓: episode</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
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
  getEpisodeFrames,
  getVideoUrls,
  type DatasetInfo,
  type EpisodeFramesResponse,
  type FrameData,
  type VideoUrl,
} from "../api/datasets";

const STATE_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b"];
const ACTION_COLORS = ["#aec7e8", "#ffbb78", "#98df8a", "#ff9896", "#c5b0d5", "#c49c94"];

export default function EpisodeDetailPage() {
  const { name, idx } = useParams<{ name: string; idx: string }>();
  const episodeIndex = Number(idx);

  const [info, setInfo] = useState<DatasetInfo | null>(null);
  const [videoUrls, setVideoUrls] = useState<VideoUrl[]>([]);
  const [framesData, setFramesData] = useState<EpisodeFramesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [currentTime, setCurrentTime] = useState(0);
  const [currentFrame, setCurrentFrame] = useState<FrameData | null>(null);

  const masterRef = useRef<HTMLVideoElement>(null);
  const slaveRefs = useRef<HTMLVideoElement[]>([]);

  useEffect(() => {
    if (!name) return;
    Promise.all([getDatasetInfo(name), getVideoUrls(name, episodeIndex), getEpisodeFrames(name, episodeIndex)])
      .then(([i, urls, frames]) => {
        setInfo(i);
        setVideoUrls(urls);
        setFramesData(frames);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [name, episodeIndex]);

  useEffect(() => {
    const master = masterRef.current;
    if (!master || !framesData) return;

    const onTimeUpdate = () => {
      const t = master.currentTime;
      setCurrentTime(t);

      slaveRefs.current.forEach((slave) => {
        if (slave && Math.abs(slave.currentTime - t) > 0.1) {
          slave.currentTime = t;
        }
      });

      const frameIdx = Math.min(
        Math.floor(t * framesData.fps),
        framesData.frames.length - 1
      );
      if (frameIdx >= 0) setCurrentFrame(framesData.frames[frameIdx]);
    };

    const onPlay = () => slaveRefs.current.forEach((s) => s?.play());
    const onPause = () => slaveRefs.current.forEach((s) => s?.pause());

    const onSeeked = () => {
      slaveRefs.current.forEach((s) => {
        if (s) s.currentTime = master.currentTime;
      });
    };

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
        const point: Record<string, number> = { time: parseFloat((f.frame_index / framesData.fps).toFixed(2)) };
        jointNames.forEach((name, i) => {
          point[`state_${name}`] = f.observation_state[i] ?? 0;
          point[`action_${name}`] = f.action[i] ?? 0;
        });
        return point;
      });
  })();

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error: {error}</p>;

  return (
    <div>
      <p>
        <Link to={`/datasets/${encodeURIComponent(name ?? "")}`}>← Episodes</Link>
      </p>
      <h1>Episode {episodeIndex}</h1>

      <h2>Videos</h2>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {videoUrls.map((v, i) => (
          <div key={v.camera}>
            <p>{v.camera}</p>
            <video
              ref={(el) => {
                if (i === 0) (masterRef as React.MutableRefObject<HTMLVideoElement | null>).current = el;
                else if (el) slaveRefs.current[i - 1] = el;
              }}
              src={v.url}
              preload="auto"
              width={480}
              controls
            />
          </div>
        ))}
      </div>
      {videoUrls.length > 1 && (
        <div style={{ marginTop: 8 }}>
          <small>※ 상단 영상(master) 컨트롤로 재생 시 나머지 영상이 자동 동기화됩니다.</small>
        </div>
      )}

      <h2>
        Motor Data{" "}
        {currentFrame && (
          <span style={{ fontWeight: "normal", fontSize: "0.85em" }}>
            (Frame: {currentFrame.frame_index})
          </span>
        )}
      </h2>

      <table border={1} cellPadding={6} cellSpacing={0} style={{ marginBottom: 24 }}>
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
              <td>{jname}</td>
              <td>{currentFrame ? currentFrame.observation_state[i]?.toFixed(0) ?? "—" : "—"}</td>
              <td>{currentFrame ? currentFrame.action[i]?.toFixed(0) ?? "—" : "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {chartData.length > 0 && (
        <div>
          <p>Trajectory (state: solid / action: dashed)</p>
          <ResponsiveContainer width="100%" height={320}>
            <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="time" label={{ value: "time (s)", position: "insideBottomRight", offset: -8 }} />
              <YAxis />
              <Tooltip />
              <Legend />
              <ReferenceLine x={parseFloat(currentTime.toFixed(2))} stroke="red" strokeWidth={2} label="▶" />
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
    </div>
  );
}

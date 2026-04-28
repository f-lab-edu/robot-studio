import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getDatasetInfo, listEpisodes, type DatasetInfo, type Episode } from "../api/datasets";

export default function DatasetDetailPage() {
  const { name } = useParams<{ name: string }>();
  const [info, setInfo] = useState<DatasetInfo | null>(null);
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!name) return;
    Promise.all([getDatasetInfo(name), listEpisodes(name)])
      .then(([i, eps]) => {
        setInfo(i);
        setEpisodes(eps);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [name]);

  if (loading) return <p>Loading...</p>;
  if (error) return <p>Error: {error}</p>;
  if (!info) return null;

  return (
    <div>
      <p>
        <Link to="/datasets">← Datasets</Link>
      </p>
      <h1>{info.name}</h1>
      <p>
        robot_type: <b>{info.robot_type}</b> | fps: <b>{info.fps}</b> | episodes:{" "}
        <b>{info.total_episodes}</b> | frames: <b>{info.total_frames}</b> | successes:{" "}
        <b>{info.total_successes}</b>
      </p>

      <h2>Episodes</h2>
      {episodes.length === 0 && <p>No episodes found.</p>}
      {episodes.length > 0 && (
        <table border={1} cellPadding={8} cellSpacing={0}>
          <thead>
            <tr>
              <th>#</th>
              <th>Instruction</th>
              <th>Frames</th>
              <th>Success</th>
              <th>Timestamp</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {episodes.map((ep) => (
              <tr key={ep.episode_index}>
                <td>{ep.episode_index}</td>
                <td>{ep.language_instruction || "—"}</td>
                <td>{ep.length}</td>
                <td>{ep.success ? "✓" : "✗"}</td>
                <td>{ep.timestamp}</td>
                <td>
                  <Link
                    to={`/datasets/${encodeURIComponent(info.name)}/episodes/${ep.episode_index}`}
                  >
                    보기 →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

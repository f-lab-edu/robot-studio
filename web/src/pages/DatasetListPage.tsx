import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listDatasets, getDatasetInfo, type DatasetInfo } from "../api/datasets";
import "./DatasetListPage.css";

export default function DatasetListPage() {
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    listDatasets()
      .then((summaries) =>
        Promise.all(summaries.map((s) => getDatasetInfo(s.name)))
      )
      .then(setDatasets)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="ds-list-page">
      <nav className="navbar">
        <span className="navbar-logo">⬡ Robot Studio</span>
      </nav>

      <main className="ds-list-main">
        <div className="ds-list-header">
          <h1 className="ds-list-title">Datasets</h1>
          {!loading && !error && (
            <span className="badge badge-gray">{datasets.length} datasets</span>
          )}
        </div>

        {loading && <p className="ds-state-msg">Loading...</p>}
        {error && <p className="ds-state-msg ds-state-error">Error: {error}</p>}
        {!loading && !error && datasets.length === 0 && (
          <p className="ds-state-msg">No datasets found.</p>
        )}

        {datasets.length > 0 && (
          <div className="ds-table glass-card">
            <div className="ds-table-header">
              <span className="label">Name</span>
              <span className="label">Robot</span>
              <span className="label">FPS</span>
              <span className="label">Episodes</span>
              <span className="label">Frames</span>
              <span className="label">Successes</span>
              <span />
            </div>

            <div className="ds-table-body">
              {datasets.map((ds) => {
                const successRate = ds.total_episodes > 0
                  ? ds.total_successes / ds.total_episodes
                  : 0;
                const successColor =
                  successRate === 1
                    ? "var(--purple)"
                    : successRate >= 0.5
                    ? "var(--warning)"
                    : "var(--danger)";

                return (
                  <div
                    key={ds.name}
                    className="ds-row"
                    onClick={() => navigate(`/datasets/${encodeURIComponent(ds.name)}`)}
                  >
                    <span className="ds-name">{ds.name}</span>
                    <span>
                      <span className="badge badge-purple">{ds.robot_type}</span>
                    </span>
                    <span className="ds-num">{ds.fps}</span>
                    <span className="ds-num">{ds.total_episodes}</span>
                    <span className="ds-num">{ds.total_frames.toLocaleString()}</span>
                    <span className="ds-num" style={{ color: successColor }}>
                      {ds.total_successes} / {ds.total_episodes}
                    </span>
                    <span className="ds-row-action">
                      <button className="ds-view-btn">보기 →</button>
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listDatasets, type DatasetSummary } from "../api/datasets";

export default function DatasetListPage() {
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listDatasets()
      .then(setDatasets)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div>
      <h1>Datasets</h1>
      {loading && <p>Loading...</p>}
      {error && <p>Error: {error}</p>}
      {!loading && !error && datasets.length === 0 && <p>No datasets found.</p>}
      {datasets.length > 0 && (
        <table border={1} cellPadding={8} cellSpacing={0}>
          <thead>
            <tr>
              <th>Name</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {datasets.map((ds) => (
              <tr key={ds.name}>
                <td>{ds.name}</td>
                <td>
                  <Link to={`/datasets/${encodeURIComponent(ds.name)}`}>보기 →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

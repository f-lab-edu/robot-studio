import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Login from "./pages/Login";
import Signup from "./pages/Signup";
import DatasetListPage from "./pages/DatasetListPage";
import DatasetDetailPage from "./pages/DatasetDetailPage";
import EpisodeDetailPage from "./pages/EpisodeDetailPage";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/" element={<Navigate to="/datasets" replace />} />
        <Route path="/datasets" element={<DatasetListPage />} />
        <Route path="/datasets/:name" element={<DatasetDetailPage />} />
        <Route path="/datasets/:name/episodes/:idx" element={<EpisodeDetailPage />} />
        <Route path="*" element={<Navigate to="/datasets" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;

import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Hotspots from "./pages/Hotspots";
import Demographics from "./pages/Demographics";
import Network from "./pages/Network";
import Predictive from "./pages/Predictive";
import Assistant from "./pages/Assistant";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="hotspots" element={<Hotspots />} />
        <Route path="demographics" element={<Demographics />} />
        <Route path="network" element={<Network />} />
        <Route path="predictive" element={<Predictive />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

import { Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Hotspots from "./pages/Hotspots";
import Demographics from "./pages/Demographics";
import Sociological from "./pages/Sociological";
import Network from "./pages/Network";
import PersonProfile from "./pages/PersonProfile";
import Operations from "./pages/Operations";
import Predictive from "./pages/Predictive";
import Reports from "./pages/Reports";
import Assistant from "./pages/Assistant";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="hotspots" element={<Hotspots />} />
        <Route path="demographics" element={<Demographics />} />
        <Route path="sociological" element={<Sociological />} />
        <Route path="network" element={<Network />} />
        <Route path="person/:id" element={<PersonProfile />} />
        <Route path="operations" element={<Operations />} />
        <Route path="predictive" element={<Predictive />} />
        <Route path="reports" element={<Reports />} />
        <Route path="assistant" element={<Assistant />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import Navbar from "@/components/Navbar";
import HomePage from "@/pages/HomePage";
import TournamentsPage from "@/pages/TournamentsPage";
import TournamentDetailPage from "@/pages/TournamentDetailPage";
import CreateTournamentPage from "@/pages/CreateTournamentPage";
import GamesPage from "@/pages/GamesPage";

function App() {
  return (
    <div className="min-h-screen bg-[#050505]">
      <BrowserRouter>
        <Navbar />
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/tournaments" element={<TournamentsPage />} />
          <Route path="/tournaments/create" element={<CreateTournamentPage />} />
          <Route path="/tournaments/:id" element={<TournamentDetailPage />} />
          <Route path="/games" element={<GamesPage />} />
        </Routes>
        <Toaster theme="dark" position="top-right" />
      </BrowserRouter>
    </div>
  );
}

export default App;

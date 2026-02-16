import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/context/AuthContext";
import Navbar from "@/components/Navbar";
import HomePage from "@/pages/HomePage";
import TournamentsPage from "@/pages/TournamentsPage";
import TournamentDetailPage from "@/pages/TournamentDetailPage";
import CreateTournamentPage from "@/pages/CreateTournamentPage";
import GamesPage from "@/pages/GamesPage";
import LoginPage from "@/pages/LoginPage";
import RegisterPage from "@/pages/RegisterPage";
import TeamsPage from "@/pages/TeamsPage";
import AdminPage from "@/pages/AdminPage";
import ProfilePage from "@/pages/ProfilePage";
import WidgetPage from "@/pages/WidgetPage";
import MatchDetailPage from "@/pages/MatchDetailPage";

function App() {
  return (
    <div className="min-h-screen bg-[#050505]">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Widget route - no navbar */}
            <Route path="/widget/:tournamentId" element={<WidgetPage />} />
            {/* Main app routes */}
            <Route path="*" element={<MainLayout />} />
          </Routes>
          <Toaster theme="dark" position="top-right" />
        </AuthProvider>
      </BrowserRouter>
    </div>
  );
}

function MainLayout() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/tournaments" element={<TournamentsPage />} />
        <Route path="/tournaments/create" element={<CreateTournamentPage />} />
        <Route path="/tournaments/:id" element={<TournamentDetailPage />} />
        <Route path="/tournaments/:id/matches/:matchId" element={<MatchDetailPage />} />
        <Route path="/games" element={<GamesPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/teams" element={<TeamsPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/profile/:userId" element={<ProfilePage />} />
      </Routes>
    </>
  );
}

export default App;

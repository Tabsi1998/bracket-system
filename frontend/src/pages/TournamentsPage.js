import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { Search, Users, Trophy, Plus, Calendar } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusColors = {
  registration: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  checkin: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  live: "bg-red-500/10 text-red-400 border-red-500/20 live-pulse",
  completed: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
};
const statusLabels = {
  registration: "Registrierung",
  checkin: "Check-in",
  live: "LIVE",
  completed: "Abgeschlossen",
};

export default function TournamentsPage() {
  const [tournaments, setTournaments] = useState([]);
  const [games, setGames] = useState([]);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [gameFilter, setGameFilter] = useState("all");

  useEffect(() => {
    axios.get(`${API}/tournaments`).then(r => setTournaments(r.data)).catch(() => {});
    axios.get(`${API}/games`).then(r => setGames(r.data)).catch(() => {});
  }, []);

  const filtered = tournaments.filter(t => {
    if (search && !t.name.toLowerCase().includes(search.toLowerCase())) return false;
    if (statusFilter !== "all" && t.status !== statusFilter) return false;
    if (gameFilter !== "all" && t.game_id !== gameFilter) return false;
    return true;
  });

  return (
    <div data-testid="tournaments-page" className="pt-20 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-8">
          <div>
            <h1 className="font-['Barlow_Condensed'] text-3xl sm:text-4xl font-bold text-white uppercase tracking-tight">
              Turniere
            </h1>
            <p className="text-sm text-zinc-500 mt-1">{tournaments.length} Turniere verfügbar</p>
          </div>
          <Link to="/tournaments/create" data-testid="create-tournament-btn">
            <Button className="bg-yellow-500 text-black hover:bg-yellow-400 font-semibold gap-2 active:scale-95 transition-transform">
              <Plus className="w-4 h-4" />
              Neues Turnier
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-3 mb-8">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <Input
              data-testid="search-tournaments"
              placeholder="Turnier suchen..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="pl-10 bg-zinc-950 border-white/10 text-white placeholder:text-zinc-600"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger data-testid="filter-status" className="w-full sm:w-44 bg-zinc-950 border-white/10 text-white">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-white/10">
              <SelectItem value="all">Alle Status</SelectItem>
              <SelectItem value="registration">Registrierung</SelectItem>
              <SelectItem value="checkin">Check-in</SelectItem>
              <SelectItem value="live">Live</SelectItem>
              <SelectItem value="completed">Abgeschlossen</SelectItem>
            </SelectContent>
          </Select>
          <Select value={gameFilter} onValueChange={setGameFilter}>
            <SelectTrigger data-testid="filter-game" className="w-full sm:w-44 bg-zinc-950 border-white/10 text-white">
              <SelectValue placeholder="Spiel" />
            </SelectTrigger>
            <SelectContent className="bg-zinc-950 border-white/10">
              <SelectItem value="all">Alle Spiele</SelectItem>
              {games.map(g => (
                <SelectItem key={g.id} value={g.id}>{g.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Tournament Grid */}
        {filtered.length === 0 ? (
          <div className="text-center py-24">
            <Trophy className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
            <p className="text-zinc-500">Keine Turniere gefunden</p>
            <Link to="/tournaments/create">
              <Button className="mt-4 bg-yellow-500 text-black hover:bg-yellow-400">
                Erstes Turnier erstellen
              </Button>
            </Link>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filtered.map((t, i) => (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.05 }}
              >
                <Link to={`/tournaments/${t.id}`} data-testid={`tournament-item-${i}`}>
                  <div className="group glass rounded-xl overflow-hidden border border-white/5 hover:border-yellow-500/30 transition-all duration-300 game-card-hover">
                    <div className="p-5">
                      <div className="flex items-center justify-between mb-3">
                        <Badge className={`text-xs border ${statusColors[t.status] || statusColors.registration}`}>
                          {statusLabels[t.status] || t.status}
                        </Badge>
                        <span className="text-xs text-zinc-600 font-mono uppercase">{t.bracket_type?.replace("_", " ")}</span>
                      </div>
                      <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white group-hover:text-yellow-500 transition-colors truncate">
                        {t.name}
                      </h3>
                      <p className="text-sm text-zinc-500 mt-1">{t.game_name} - {t.game_mode}</p>
                      <div className="flex items-center gap-3 mt-3 text-xs text-zinc-600">
                        <span className="flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          {t.team_size > 1 ? `${t.team_size}v${t.team_size}` : "1v1"}
                        </span>
                        <span>Bo{t.best_of}</span>
                        {t.start_date && (
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {new Date(t.start_date).toLocaleDateString("de-DE")}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/5">
                        <div className="flex items-center gap-1 text-xs text-zinc-500">
                          <Users className="w-3 h-3" />
                          {t.registered_count || 0}/{t.max_participants}
                        </div>
                        <div className={`text-xs font-mono font-semibold ${t.entry_fee > 0 ? "text-yellow-500" : "text-green-500"}`}>
                          {t.entry_fee > 0 ? `$${t.entry_fee.toFixed(2)}` : "KOSTENLOS"}
                        </div>
                      </div>
                    </div>
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

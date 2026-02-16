import { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { Trophy, Users, Gamepad2, Zap, ArrowRight, ChevronRight } from "lucide-react";
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

export default function HomePage() {
  const [tournaments, setTournaments] = useState([]);
  const [stats, setStats] = useState({});

  useEffect(() => {
    axios.get(`${API}/tournaments`).then(r => setTournaments(r.data.slice(0, 6))).catch(() => {});
    axios.get(`${API}/stats`).then(r => setStats(r.data)).catch(() => {});
  }, []);

  return (
    <div data-testid="home-page">
      {/* Hero */}
      <section className="relative min-h-[90vh] flex items-end overflow-hidden">
        <div className="absolute inset-0">
          <img
            src="https://images.unsplash.com/photo-1542751371-adc38448a05e?w=1920&q=80"
            alt="eSports arena"
            className="w-full h-full object-cover opacity-40"
          />
          <div className="hero-gradient absolute inset-0" />
          <div className="absolute inset-0 bg-gradient-to-r from-[#050505] via-transparent to-transparent" />
        </div>

        <div className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-24 pt-32 w-full">
          <motion.div
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
          >
            <Badge className="bg-yellow-500/10 text-yellow-500 border border-yellow-500/30 mb-6 text-xs uppercase tracking-widest font-mono">
              eSports Tournament Platform
            </Badge>
            <h1
              data-testid="hero-title"
              className="font-['Barlow_Condensed'] text-5xl sm:text-7xl lg:text-8xl font-extrabold text-white uppercase tracking-tight leading-none"
            >
              COMPETE.<br />
              <span className="text-yellow-500 neon-text">DOMINATE.</span><br />
              WIN.
            </h1>
            <p className="mt-6 text-lg text-zinc-400 max-w-lg">
              Erstelle und verwalte professionelle eSport-Turniere. Single & Double Elimination, Round Robin und mehr.
            </p>
            <div className="mt-8 flex flex-wrap gap-4">
              <Link to="/tournaments" data-testid="hero-browse-btn">
                <Button className="bg-yellow-500 text-black hover:bg-yellow-400 h-12 px-8 text-base font-bold uppercase tracking-wide active:scale-95 transition-transform">
                  Turniere entdecken
                  <ArrowRight className="w-5 h-5 ml-2" />
                </Button>
              </Link>
              <Link to="/tournaments/create" data-testid="hero-create-btn">
                <Button variant="outline" className="h-12 px-8 text-base border-white/20 text-white hover:bg-white/5 uppercase tracking-wide">
                  Turnier erstellen
                </Button>
              </Link>
            </div>
          </motion.div>
        </div>
      </section>

      {/* Stats */}
      <section className="relative -mt-16 z-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Turniere", value: stats.total_tournaments || 0, icon: Trophy },
            { label: "Live", value: stats.live_tournaments || 0, icon: Zap },
            { label: "Spieler", value: stats.total_registrations || 0, icon: Users },
            { label: "Spiele", value: stats.total_games || 0, icon: Gamepad2 },
          ].map((stat, i) => (
            <motion.div
              key={stat.label}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 + i * 0.1 }}
              className="glass rounded-xl p-5"
            >
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
                  <stat.icon className="w-5 h-5 text-yellow-500" />
                </div>
                <div>
                  <div className="font-['Barlow_Condensed'] text-2xl font-bold text-white">{stat.value}</div>
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">{stat.label}</div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Featured Tournaments */}
      {tournaments.length > 0 && (
        <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
          <div className="flex items-center justify-between mb-8">
            <h2 className="font-['Barlow_Condensed'] text-2xl sm:text-3xl font-bold text-white uppercase tracking-tight">
              Aktuelle Turniere
            </h2>
            <Link to="/tournaments" data-testid="view-all-tournaments">
              <Button variant="ghost" className="text-zinc-400 hover:text-yellow-500 gap-1">
                Alle anzeigen <ChevronRight className="w-4 h-4" />
              </Button>
            </Link>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {tournaments.map((t, i) => (
              <motion.div
                key={t.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.1 }}
              >
                <Link to={`/tournaments/${t.id}`} data-testid={`tournament-card-${i}`}>
                  <div className="group glass rounded-xl overflow-hidden border border-white/5 hover:border-yellow-500/30 transition-all duration-300 game-card-hover">
                    <div className="p-5">
                      <div className="flex items-center justify-between mb-3">
                        <Badge className={`text-xs border ${statusColors[t.status] || statusColors.registration}`}>
                          {statusLabels[t.status] || t.status}
                        </Badge>
                        <span className="text-xs text-zinc-600 font-mono">{t.bracket_type?.replace("_", " ")}</span>
                      </div>
                      <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white group-hover:text-yellow-500 transition-colors truncate">
                        {t.name}
                      </h3>
                      <p className="text-sm text-zinc-500 mt-1">{t.game_name} - {t.game_mode}</p>
                      <div className="flex items-center justify-between mt-4 pt-3 border-t border-white/5">
                        <div className="flex items-center gap-1 text-xs text-zinc-500">
                          <Users className="w-3 h-3" />
                          {t.registered_count || 0}/{t.max_participants}
                        </div>
                        <div className="text-xs text-zinc-500 font-mono">
                          {t.entry_fee > 0 ? `$${t.entry_fee.toFixed(2)}` : "Kostenlos"}
                        </div>
                      </div>
                    </div>
                  </div>
                </Link>
              </motion.div>
            ))}
          </div>
        </section>
      )}

      {/* How it works */}
      <section className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pb-24">
        <h2 className="font-['Barlow_Condensed'] text-2xl sm:text-3xl font-bold text-white uppercase tracking-tight mb-12 text-center">
          So funktioniert es
        </h2>
        <div className="grid md:grid-cols-3 gap-8">
          {[
            { step: "01", title: "Turnier erstellen", desc: "Wähle ein Spiel, konfiguriere die Parameter und starte dein Turnier in Sekunden." },
            { step: "02", title: "Spieler registrieren", desc: "Teile den Link. Spieler registrieren sich mit Name und E-Mail. Kein Account nötig." },
            { step: "03", title: "Bracket generieren", desc: "Generiere den Bracket automatisch. Live-Updates und Animationen inklusive." },
          ].map((item, i) => (
            <motion.div
              key={item.step}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: i * 0.15 }}
              className="relative p-8 rounded-xl bg-zinc-950/50 border border-white/5 group hover:border-yellow-500/20 transition-all"
            >
              <div className="font-['Barlow_Condensed'] text-5xl font-extrabold text-yellow-500/10 absolute top-4 right-4">
                {item.step}
              </div>
              <h3 className="font-['Barlow_Condensed'] text-xl font-bold text-white mt-4 mb-2">
                {item.title}
              </h3>
              <p className="text-sm text-zinc-500 leading-relaxed">{item.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>
    </div>
  );
}

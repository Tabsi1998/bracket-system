import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { motion } from "framer-motion";
import { User, Trophy, Users, Swords, TrendingUp, Calendar } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export default function ProfilePage() {
  const { userId } = useParams();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/users/${userId}/profile`)
      .then(r => setProfile(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId]);

  if (loading) return (
    <div className="pt-20 min-h-screen flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!profile) return (
    <div className="pt-20 min-h-screen flex items-center justify-center">
      <p className="text-zinc-500">Benutzer nicht gefunden</p>
    </div>
  );

  const winRate = profile.stats.wins + profile.stats.losses > 0
    ? Math.round((profile.stats.wins / (profile.stats.wins + profile.stats.losses)) * 100)
    : 0;

  return (
    <div data-testid="profile-page" className="pt-20 min-h-screen">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
          className="glass rounded-2xl p-8 border border-white/5 mb-8"
        >
          <div className="flex items-center gap-5">
            <img src={profile.avatar_url || `https://api.dicebear.com/7.x/avataaars/svg?seed=${profile.username}`}
              className="w-20 h-20 rounded-xl border-2 border-yellow-500/30" alt="" />
            <div>
              <h1 className="font-['Barlow_Condensed'] text-3xl font-bold text-white uppercase tracking-tight flex items-center gap-2">
                {profile.username}
                {profile.role === "admin" && <Badge className="bg-yellow-500/10 text-yellow-500 text-xs">Admin</Badge>}
              </h1>
              <p className="text-sm text-zinc-500 mt-1">{profile.email}</p>
              <p className="text-xs text-zinc-600 font-mono mt-1">
                Mitglied seit {new Date(profile.created_at).toLocaleDateString("de-DE")}
              </p>
            </div>
          </div>
        </motion.div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          {[
            { label: "Turniere", value: profile.stats.tournaments_played, icon: Trophy },
            { label: "Siege", value: profile.stats.wins, icon: TrendingUp, color: "text-green-500" },
            { label: "Niederlagen", value: profile.stats.losses, icon: Swords, color: "text-red-500" },
            { label: "Winrate", value: `${winRate}%`, icon: TrendingUp, color: "text-yellow-500" },
          ].map((s, i) => (
            <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className="glass rounded-xl p-4 border border-white/5"
            >
              <s.icon className={`w-4 h-4 mb-2 ${s.color || "text-yellow-500"}`} />
              <div className="font-['Barlow_Condensed'] text-2xl font-bold text-white">{s.value}</div>
              <div className="text-xs text-zinc-500">{s.label}</div>
            </motion.div>
          ))}
        </div>

        {/* Teams */}
        <div className="mb-8">
          <h2 className="font-['Barlow_Condensed'] text-xl font-bold text-white uppercase tracking-tight mb-4 flex items-center gap-2">
            <Users className="w-5 h-5 text-yellow-500" />Teams ({profile.teams?.length || 0})
          </h2>
          {profile.teams?.length > 0 ? (
            <div className="grid sm:grid-cols-2 gap-3">
              {profile.teams.map(t => (
                <div key={t.id} className="glass rounded-lg p-4 border border-white/5">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-yellow-500" />
                    <span className="text-white font-semibold">{t.name}</span>
                    {t.tag && <span className="text-xs text-zinc-500 font-mono">[{t.tag}]</span>}
                  </div>
                  <div className="text-xs text-zinc-500 mt-1">{t.members?.length || 0} Mitglieder</div>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-zinc-600">Keine Teams</p>
          )}
        </div>

        {/* Tournaments */}
        <div>
          <h2 className="font-['Barlow_Condensed'] text-xl font-bold text-white uppercase tracking-tight mb-4 flex items-center gap-2">
            <Trophy className="w-5 h-5 text-yellow-500" />Turniere ({profile.tournaments?.length || 0})
          </h2>
          {profile.tournaments?.length > 0 ? (
            <div className="space-y-2">
              {profile.tournaments.map(t => (
                <Link key={t.id} to={`/tournaments/${t.id}`} data-testid={`profile-tournament-${t.id}`}>
                  <div className="glass rounded-lg p-4 border border-white/5 hover:border-yellow-500/20 transition-all flex items-center justify-between">
                    <div>
                      <span className="text-white font-semibold">{t.name}</span>
                      <span className="text-xs text-zinc-500 ml-3">{t.game_name}</span>
                    </div>
                    <Badge className={`text-xs border ${t.status === "live" ? "bg-red-500/10 text-red-400" : t.status === "completed" ? "bg-zinc-500/10 text-zinc-500" : "bg-blue-500/10 text-blue-400"}`}>
                      {t.status}
                    </Badge>
                  </div>
                </Link>
              ))}
            </div>
          ) : (
            <p className="text-sm text-zinc-600">Noch an keinem Turnier teilgenommen</p>
          )}
        </div>
      </div>
    </div>
  );
}

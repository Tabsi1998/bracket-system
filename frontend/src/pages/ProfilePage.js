import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { motion } from "framer-motion";
import { Trophy, Users, Swords, TrendingUp } from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export default function ProfilePage() {
  const { userId } = useParams();
  const { user, refreshUser } = useAuth();
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(true);
  const [accountForm, setAccountForm] = useState({ username: "", email: "" });
  const [passwordForm, setPasswordForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [savingAccount, setSavingAccount] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  useEffect(() => {
    axios.get(`${API}/users/${userId}/profile`)
      .then(r => setProfile(r.data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [userId]);

  useEffect(() => {
    if (!profile) return;
    setAccountForm({
      username: profile.username || "",
      email: profile.email || "",
    });
  }, [profile?.id]);

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
  const isOwnProfile = Boolean(user && user.id === profile.id);

  const handleAccountSave = async () => {
    if (!accountForm.username.trim()) { toast.error("Benutzername darf nicht leer sein"); return; }
    if (!accountForm.email.trim()) { toast.error("E-Mail darf nicht leer sein"); return; }
    setSavingAccount(true);
    try {
      const res = await axios.put(`${API}/users/me/account`, {
        username: accountForm.username,
        email: accountForm.email,
      });
      setProfile(prev => ({ ...(prev || {}), ...res.data }));
      await refreshUser();
      toast.success("Konto aktualisiert");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Konto konnte nicht gespeichert werden");
    } finally {
      setSavingAccount(false);
    }
  };

  const handlePasswordSave = async () => {
    if (!passwordForm.current_password || !passwordForm.new_password) { toast.error("Passwortfelder ausfüllen"); return; }
    if (passwordForm.new_password.length < 6) { toast.error("Neues Passwort muss mindestens 6 Zeichen haben"); return; }
    if (passwordForm.new_password !== passwordForm.confirm_password) { toast.error("Passwörter stimmen nicht überein"); return; }
    setSavingPassword(true);
    try {
      await axios.put(`${API}/users/me/password`, {
        current_password: passwordForm.current_password,
        new_password: passwordForm.new_password,
      });
      setPasswordForm({ current_password: "", new_password: "", confirm_password: "" });
      toast.success("Passwort geändert");
    } catch (e) {
      toast.error(e.response?.data?.detail || "Passwort konnte nicht geändert werden");
    } finally {
      setSavingPassword(false);
    }
  };

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

        {isOwnProfile && (
          <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            className="glass rounded-xl p-6 border border-white/5 mb-8"
          >
            <h2 className="font-['Barlow_Condensed'] text-xl font-bold text-white uppercase tracking-tight mb-4">
              Kontoeinstellungen
            </h2>
            <div className="grid md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <Label className="text-zinc-400 text-sm">Benutzername</Label>
                <Input
                  value={accountForm.username}
                  onChange={(e) => setAccountForm({ ...accountForm, username: e.target.value })}
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">E-Mail</Label>
                <Input
                  type="email"
                  value={accountForm.email}
                  onChange={(e) => setAccountForm({ ...accountForm, email: e.target.value })}
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Button onClick={handleAccountSave} disabled={savingAccount} className="bg-yellow-500 text-black hover:bg-yellow-400">
                  {savingAccount ? "Speichert..." : "Profil speichern"}
                </Button>
              </div>

              <div className="space-y-3">
                <Label className="text-zinc-400 text-sm">Aktuelles Passwort</Label>
                <Input
                  type="password"
                  value={passwordForm.current_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, current_password: e.target.value })}
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">Neues Passwort</Label>
                <Input
                  type="password"
                  value={passwordForm.new_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, new_password: e.target.value })}
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">Neues Passwort wiederholen</Label>
                <Input
                  type="password"
                  value={passwordForm.confirm_password}
                  onChange={(e) => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })}
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Button onClick={handlePasswordSave} disabled={savingPassword} variant="outline" className="border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10">
                  {savingPassword ? "Ändert..." : "Passwort ändern"}
                </Button>
              </div>
            </div>
          </motion.div>
        )}

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

import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
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
  const [accountForm, setAccountForm] = useState({
    username: "",
    email: "",
    avatar_url: "",
    banner_url: "",
    bio: "",
    discord_url: "",
    website_url: "",
    twitter_url: "",
    instagram_url: "",
    twitch_url: "",
    youtube_url: "",
  });
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
      avatar_url: profile.avatar_url || "",
      banner_url: profile.banner_url || "",
      bio: profile.bio || "",
      discord_url: profile.discord_url || "",
      website_url: profile.website_url || "",
      twitter_url: profile.twitter_url || "",
      instagram_url: profile.instagram_url || "",
      twitch_url: profile.twitch_url || "",
      youtube_url: profile.youtube_url || "",
    });
  }, [profile]);

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
        username: accountForm.username.trim(),
        email: accountForm.email.trim(),
        avatar_url: accountForm.avatar_url.trim(),
        banner_url: accountForm.banner_url.trim(),
        bio: accountForm.bio,
        discord_url: accountForm.discord_url.trim(),
        website_url: accountForm.website_url.trim(),
        twitter_url: accountForm.twitter_url.trim(),
        instagram_url: accountForm.instagram_url.trim(),
        twitch_url: accountForm.twitch_url.trim(),
        youtube_url: accountForm.youtube_url.trim(),
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
          className="glass rounded-2xl p-8 border border-white/5 mb-8 relative overflow-hidden"
        >
          {profile.banner_url ? (
            <div className="absolute inset-0 opacity-20">
              <img src={profile.banner_url} alt="" className="w-full h-full object-cover" />
            </div>
          ) : null}
          <div className="absolute inset-0 bg-gradient-to-r from-black/60 to-black/20" />
          <div className="flex items-center gap-5 relative z-10">
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
              {profile.bio ? <p className="text-sm text-zinc-300 mt-2 max-w-2xl whitespace-pre-wrap">{profile.bio}</p> : null}
              <div className="flex gap-3 mt-2 text-xs">
                {profile.discord_url ? <a href={profile.discord_url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:text-cyan-300">Discord</a> : null}
                {profile.website_url ? <a href={profile.website_url} target="_blank" rel="noreferrer" className="text-zinc-300 hover:text-white">Website</a> : null}
                {profile.twitter_url ? <a href={profile.twitter_url} target="_blank" rel="noreferrer" className="text-sky-400 hover:text-sky-300">X/Twitter</a> : null}
                {profile.instagram_url ? <a href={profile.instagram_url} target="_blank" rel="noreferrer" className="text-pink-400 hover:text-pink-300">Instagram</a> : null}
                {profile.twitch_url ? <a href={profile.twitch_url} target="_blank" rel="noreferrer" className="text-purple-400 hover:text-purple-300">Twitch</a> : null}
                {profile.youtube_url ? <a href={profile.youtube_url} target="_blank" rel="noreferrer" className="text-red-400 hover:text-red-300">YouTube</a> : null}
              </div>
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
                <Label className="text-zinc-400 text-sm">Avatar URL</Label>
                <Input
                  value={accountForm.avatar_url}
                  onChange={(e) => setAccountForm({ ...accountForm, avatar_url: e.target.value })}
                  placeholder="https://..."
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">Banner URL</Label>
                <Input
                  value={accountForm.banner_url}
                  onChange={(e) => setAccountForm({ ...accountForm, banner_url: e.target.value })}
                  placeholder="https://..."
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">Bio</Label>
                <Textarea
                  value={accountForm.bio}
                  onChange={(e) => setAccountForm({ ...accountForm, bio: e.target.value })}
                  className="bg-zinc-900 border-white/10 text-white min-h-[90px]"
                />
                <Label className="text-zinc-400 text-sm">Discord URL</Label>
                <Input
                  value={accountForm.discord_url}
                  onChange={(e) => setAccountForm({ ...accountForm, discord_url: e.target.value })}
                  placeholder="https://discord.gg/..."
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">Website URL</Label>
                <Input
                  value={accountForm.website_url}
                  onChange={(e) => setAccountForm({ ...accountForm, website_url: e.target.value })}
                  placeholder="https://..."
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">X / Twitter URL</Label>
                <Input
                  value={accountForm.twitter_url}
                  onChange={(e) => setAccountForm({ ...accountForm, twitter_url: e.target.value })}
                  placeholder="https://x.com/..."
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">Instagram URL</Label>
                <Input
                  value={accountForm.instagram_url}
                  onChange={(e) => setAccountForm({ ...accountForm, instagram_url: e.target.value })}
                  placeholder="https://instagram.com/..."
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">Twitch URL</Label>
                <Input
                  value={accountForm.twitch_url}
                  onChange={(e) => setAccountForm({ ...accountForm, twitch_url: e.target.value })}
                  placeholder="https://twitch.tv/..."
                  className="bg-zinc-900 border-white/10 text-white"
                />
                <Label className="text-zinc-400 text-sm">YouTube URL</Label>
                <Input
                  value={accountForm.youtube_url}
                  onChange={(e) => setAccountForm({ ...accountForm, youtube_url: e.target.value })}
                  placeholder="https://youtube.com/..."
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

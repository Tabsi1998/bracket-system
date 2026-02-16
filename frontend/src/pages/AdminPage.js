import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Shield, Users, Trophy, Gamepad2, Settings, CreditCard, Trash2, Eye } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export default function AdminPage() {
  const { user, isAdmin } = useAuth();
  const navigate = useNavigate();
  const [dashboard, setDashboard] = useState({});
  const [users, setUsers] = useState([]);
  const [tournaments, setTournaments] = useState([]);
  const [games, setGames] = useState([]);
  const [settings, setSettings] = useState([]);
  const [settingForm, setSettingForm] = useState({ key: "", value: "" });

  useEffect(() => {
    if (!isAdmin) return;
    axios.get(`${API}/admin/dashboard`).then(r => setDashboard(r.data)).catch(() => {});
    axios.get(`${API}/admin/users`).then(r => setUsers(r.data)).catch(() => {});
    axios.get(`${API}/tournaments`).then(r => setTournaments(r.data)).catch(() => {});
    axios.get(`${API}/games`).then(r => setGames(r.data)).catch(() => {});
    axios.get(`${API}/admin/settings`).then(r => setSettings(r.data)).catch(() => {});
  }, [isAdmin]);

  if (!user || !isAdmin) return (
    <div className="pt-20 min-h-screen flex items-center justify-center">
      <div className="text-center">
        <Shield className="w-16 h-16 text-red-500/30 mx-auto mb-4" />
        <p className="text-zinc-500 text-lg">Admin-Zugang erforderlich</p>
      </div>
    </div>
  );

  const handleSaveSetting = async () => {
    if (!settingForm.key.trim()) return;
    try {
      await axios.put(`${API}/admin/settings`, settingForm);
      toast.success("Einstellung gespeichert");
      const res = await axios.get(`${API}/admin/settings`);
      setSettings(res.data);
      setSettingForm({ key: "", value: "" });
    } catch (e) { toast.error("Fehler beim Speichern"); }
  };

  const handleDeleteTournament = async (id) => {
    if (!window.confirm("Turnier wirklich löschen?")) return;
    try {
      await axios.delete(`${API}/tournaments/${id}`);
      toast.success("Turnier gelöscht");
      setTournaments(tournaments.filter(t => t.id !== id));
    } catch { toast.error("Fehler"); }
  };

  const handleDeleteGame = async (id) => {
    if (!window.confirm("Spiel wirklich löschen?")) return;
    try {
      await axios.delete(`${API}/games/${id}`);
      toast.success("Spiel gelöscht");
      setGames(games.filter(g => g.id !== id));
    } catch { toast.error("Fehler"); }
  };

  const getSetting = (key) => settings.find(s => s.key === key)?.value || "";

  const settingKeys = [
    { key: "stripe_public_key", label: "Stripe Public Key", placeholder: "pk_test_..." },
    { key: "stripe_secret_key", label: "Stripe Secret Key", placeholder: "sk_test_..." },
    { key: "paypal_client_id", label: "PayPal Client ID", placeholder: "PayPal Client ID" },
    { key: "paypal_secret", label: "PayPal Secret", placeholder: "PayPal Secret" },
    { key: "smtp_host", label: "SMTP Host", placeholder: "smtp.gmail.com" },
    { key: "smtp_port", label: "SMTP Port", placeholder: "587" },
    { key: "smtp_user", label: "SMTP Benutzer", placeholder: "email@domain.de" },
    { key: "smtp_password", label: "SMTP Passwort", placeholder: "Passwort" },
  ];

  return (
    <div data-testid="admin-page" className="pt-20 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center gap-3 mb-8">
          <Shield className="w-8 h-8 text-yellow-500" />
          <h1 className="font-['Barlow_Condensed'] text-3xl sm:text-4xl font-bold text-white uppercase tracking-tight">
            Admin Panel
          </h1>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
          {[
            { label: "Benutzer", value: dashboard.total_users || 0, icon: Users },
            { label: "Teams", value: dashboard.total_teams || 0, icon: Users },
            { label: "Turniere", value: dashboard.total_tournaments || 0, icon: Trophy },
            { label: "Anmeldungen", value: dashboard.total_registrations || 0, icon: Users },
            { label: "Live", value: dashboard.live_tournaments || 0, icon: Trophy },
            { label: "Zahlungen", value: dashboard.total_payments || 0, icon: CreditCard },
          ].map((s, i) => (
            <motion.div key={s.label} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
              className="glass rounded-xl p-4 border border-white/5"
            >
              <s.icon className="w-4 h-4 text-yellow-500 mb-2" />
              <div className="font-['Barlow_Condensed'] text-2xl font-bold text-white">{s.value}</div>
              <div className="text-xs text-zinc-500">{s.label}</div>
            </motion.div>
          ))}
        </div>

        <Tabs defaultValue="tournaments">
          <TabsList className="bg-zinc-900/50 border border-white/5">
            <TabsTrigger data-testid="admin-tab-tournaments" value="tournaments" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
              <Trophy className="w-4 h-4 mr-2" />Turniere
            </TabsTrigger>
            <TabsTrigger data-testid="admin-tab-games" value="games" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
              <Gamepad2 className="w-4 h-4 mr-2" />Spiele
            </TabsTrigger>
            <TabsTrigger data-testid="admin-tab-users" value="users" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
              <Users className="w-4 h-4 mr-2" />Benutzer
            </TabsTrigger>
            <TabsTrigger data-testid="admin-tab-settings" value="settings" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
              <Settings className="w-4 h-4 mr-2" />Einstellungen
            </TabsTrigger>
          </TabsList>

          {/* Tournaments Tab */}
          <TabsContent value="tournaments" className="mt-6">
            <div className="glass rounded-xl border border-white/5 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-white/5 text-zinc-500 text-left">
                    <th className="px-4 py-3">Name</th><th className="px-4 py-3">Spiel</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Teilnehmer</th><th className="px-4 py-3">Aktionen</th>
                  </tr></thead>
                  <tbody>
                    {tournaments.map(t => (
                      <tr key={t.id} className="border-b border-white/5 hover:bg-white/2">
                        <td className="px-4 py-3 text-white font-semibold">{t.name}</td>
                        <td className="px-4 py-3 text-zinc-400">{t.game_name}</td>
                        <td className="px-4 py-3"><Badge className="text-xs border bg-zinc-800 text-zinc-300">{t.status}</Badge></td>
                        <td className="px-4 py-3 text-zinc-400 font-mono">{t.registered_count || 0}/{t.max_participants}</td>
                        <td className="px-4 py-3">
                          <div className="flex gap-1">
                            <Button variant="ghost" size="sm" onClick={() => navigate(`/tournaments/${t.id}`)} className="text-zinc-400 hover:text-white"><Eye className="w-4 h-4" /></Button>
                            <Button data-testid={`admin-delete-tournament-${t.id}`} variant="ghost" size="sm" onClick={() => handleDeleteTournament(t.id)} className="text-red-500 hover:text-red-400"><Trash2 className="w-4 h-4" /></Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>

          {/* Games Tab */}
          <TabsContent value="games" className="mt-6">
            <div className="glass rounded-xl border border-white/5 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-white/5 text-zinc-500 text-left">
                    <th className="px-4 py-3">Name</th><th className="px-4 py-3">Kategorie</th><th className="px-4 py-3">Modi</th><th className="px-4 py-3">Typ</th><th className="px-4 py-3">Aktionen</th>
                  </tr></thead>
                  <tbody>
                    {games.map(g => (
                      <tr key={g.id} className="border-b border-white/5 hover:bg-white/2">
                        <td className="px-4 py-3 text-white font-semibold">{g.name}</td>
                        <td className="px-4 py-3 text-zinc-400 capitalize">{g.category}</td>
                        <td className="px-4 py-3 text-zinc-400">{g.modes?.map(m => m.name).join(", ")}</td>
                        <td className="px-4 py-3"><Badge className={`text-xs ${g.is_custom ? "bg-purple-500/10 text-purple-400" : "bg-blue-500/10 text-blue-400"}`}>{g.is_custom ? "Custom" : "Standard"}</Badge></td>
                        <td className="px-4 py-3">
                          {g.is_custom && <Button data-testid={`admin-delete-game-${g.id}`} variant="ghost" size="sm" onClick={() => handleDeleteGame(g.id)} className="text-red-500 hover:text-red-400"><Trash2 className="w-4 h-4" /></Button>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>

          {/* Users Tab */}
          <TabsContent value="users" className="mt-6">
            <div className="glass rounded-xl border border-white/5 overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead><tr className="border-b border-white/5 text-zinc-500 text-left">
                    <th className="px-4 py-3">Benutzer</th><th className="px-4 py-3">E-Mail</th><th className="px-4 py-3">Rolle</th><th className="px-4 py-3">Erstellt</th>
                  </tr></thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.id} className="border-b border-white/5 hover:bg-white/2">
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <img src={u.avatar_url} className="w-6 h-6 rounded-full" alt="" />
                            <span className="text-white font-semibold">{u.username}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-zinc-400">{u.email}</td>
                        <td className="px-4 py-3"><Badge className={`text-xs ${u.role === "admin" ? "bg-yellow-500/10 text-yellow-500" : "bg-zinc-800 text-zinc-400"}`}>{u.role}</Badge></td>
                        <td className="px-4 py-3 text-zinc-500 text-xs font-mono">{new Date(u.created_at).toLocaleDateString("de-DE")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </TabsContent>

          {/* Settings Tab */}
          <TabsContent value="settings" className="mt-6">
            <div className="space-y-6">
              {/* Payment Settings */}
              <div className="glass rounded-xl p-6 border border-white/5">
                <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase mb-4 flex items-center gap-2">
                  <CreditCard className="w-5 h-5 text-yellow-500" />Zahlungs-Einstellungen
                </h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  {settingKeys.filter(s => s.key.startsWith("stripe") || s.key.startsWith("paypal")).map(sk => (
                    <div key={sk.key}>
                      <Label className="text-zinc-400 text-sm">{sk.label}</Label>
                      <Input
                        data-testid={`setting-${sk.key}`}
                        type={sk.key.includes("secret") || sk.key.includes("password") ? "password" : "text"}
                        defaultValue={getSetting(sk.key)}
                        placeholder={sk.placeholder}
                        onBlur={e => {
                          if (e.target.value !== getSetting(sk.key)) {
                            axios.put(`${API}/admin/settings`, { key: sk.key, value: e.target.value })
                              .then(() => { toast.success(`${sk.label} gespeichert`); axios.get(`${API}/admin/settings`).then(r => setSettings(r.data)); })
                              .catch(() => toast.error("Fehler"));
                          }
                        }}
                        className="bg-zinc-900 border-white/10 text-white mt-1"
                      />
                    </div>
                  ))}
                </div>
              </div>

              {/* SMTP Settings */}
              <div className="glass rounded-xl p-6 border border-white/5">
                <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase mb-4 flex items-center gap-2">
                  <Settings className="w-5 h-5 text-yellow-500" />E-Mail (SMTP) Einstellungen
                </h3>
                <div className="grid sm:grid-cols-2 gap-4">
                  {settingKeys.filter(s => s.key.startsWith("smtp")).map(sk => (
                    <div key={sk.key}>
                      <Label className="text-zinc-400 text-sm">{sk.label}</Label>
                      <Input
                        data-testid={`setting-${sk.key}`}
                        type={sk.key.includes("password") ? "password" : "text"}
                        defaultValue={getSetting(sk.key)}
                        placeholder={sk.placeholder}
                        onBlur={e => {
                          if (e.target.value !== getSetting(sk.key)) {
                            axios.put(`${API}/admin/settings`, { key: sk.key, value: e.target.value })
                              .then(() => { toast.success(`${sk.label} gespeichert`); axios.get(`${API}/admin/settings`).then(r => setSettings(r.data)); })
                              .catch(() => toast.error("Fehler"));
                          }
                        }}
                        className="bg-zinc-900 border-white/10 text-white mt-1"
                      />
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Users, Plus, Trash2, UserPlus, Crown, X, Key, Copy, RefreshCw, ChevronDown, ChevronRight, Shield } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

export default function TeamsPage() {
  const { user } = useAuth();
  const [teams, setTeams] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [joinOpen, setJoinOpen] = useState(false);
  const [inviteOpen, setInviteOpen] = useState(false);
  const [subTeamOpen, setSubTeamOpen] = useState(false);
  const [selectedTeam, setSelectedTeam] = useState(null);
  const [expandedTeam, setExpandedTeam] = useState(null);
  const [subTeams, setSubTeams] = useState({});
  const [newTeam, setNewTeam] = useState({ name: "", tag: "" });
  const [joinForm, setJoinForm] = useState({ team_id: "", join_code: "" });
  const [inviteEmail, setInviteEmail] = useState("");
  const [newSubTeam, setNewSubTeam] = useState({ name: "", tag: "" });

  const fetchTeams = async () => {
    try {
      const res = await axios.get(`${API}/teams`);
      setTeams(res.data);
    } catch { /* ignore */ } finally { setLoading(false); }
  };

  useEffect(() => { fetchTeams(); }, []);

  const fetchSubTeams = async (teamId) => {
    try {
      const res = await axios.get(`${API}/teams/${teamId}/sub-teams`);
      setSubTeams(prev => ({ ...prev, [teamId]: res.data }));
    } catch { /* ignore */ }
  };

  const toggleExpand = (teamId) => {
    if (expandedTeam === teamId) { setExpandedTeam(null); return; }
    setExpandedTeam(teamId);
    fetchSubTeams(teamId);
  };

  const handleCreate = async () => {
    if (!newTeam.name.trim()) { toast.error("Team-Name erforderlich"); return; }
    try {
      await axios.post(`${API}/teams`, newTeam);
      toast.success("Team erstellt!");
      setCreateOpen(false);
      setNewTeam({ name: "", tag: "" });
      fetchTeams();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };

  const handleJoin = async () => {
    if (!joinForm.team_id.trim() || !joinForm.join_code.trim()) { toast.error("Team-ID und Code erforderlich"); return; }
    try {
      await axios.post(`${API}/teams/join`, joinForm);
      toast.success("Team beigetreten!");
      setJoinOpen(false);
      setJoinForm({ team_id: "", join_code: "" });
      fetchTeams();
    } catch (e) { toast.error(e.response?.data?.detail || "Beitritt fehlgeschlagen"); }
  };

  const handleCreateSubTeam = async () => {
    if (!newSubTeam.name.trim() || !selectedTeam) return;
    try {
      await axios.post(`${API}/teams`, { ...newSubTeam, parent_team_id: selectedTeam.id });
      toast.success("Sub-Team erstellt!");
      setSubTeamOpen(false);
      setNewSubTeam({ name: "", tag: "" });
      fetchSubTeams(selectedTeam.id);
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };

  const handleDelete = async (teamId) => {
    if (!window.confirm("Team wirklich löschen?")) return;
    try {
      await axios.delete(`${API}/teams/${teamId}`);
      toast.success("Team gelöscht");
      fetchTeams();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };

  const handleInvite = async () => {
    if (!inviteEmail.trim() || !selectedTeam) return;
    try {
      await axios.post(`${API}/teams/${selectedTeam.id}/members`, { email: inviteEmail });
      toast.success("Mitglied hinzugefügt!");
      setInviteEmail("");
      setInviteOpen(false);
      fetchTeams();
    } catch (e) { toast.error(e.response?.data?.detail || "Benutzer nicht gefunden"); }
  };

  const handleRemoveMember = async (teamId, memberId) => {
    try {
      await axios.delete(`${API}/teams/${teamId}/members/${memberId}`);
      toast.success("Mitglied entfernt");
      fetchTeams();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };

  const handlePromoteLeader = async (teamId, userId) => {
    try {
      await axios.put(`${API}/teams/${teamId}/leaders/${userId}`);
      toast.success("Zum Leader befördert!");
      fetchTeams();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };

  const handleDemoteLeader = async (teamId, userId) => {
    try {
      await axios.delete(`${API}/teams/${teamId}/leaders/${userId}`);
      toast.success("Leader-Rechte entfernt");
      fetchTeams();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler"); }
  };

  const handleRegenerateCode = async (teamId) => {
    try {
      const res = await axios.put(`${API}/teams/${teamId}/regenerate-code`);
      toast.success(`Neuer Code: ${res.data.join_code}`);
      fetchTeams();
    } catch (e) { toast.error("Fehler"); }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success("Kopiert!");
  };

  if (!user) return (
    <div className="pt-20 min-h-screen flex items-center justify-center">
      <p className="text-zinc-500">Bitte einloggen um Teams zu verwalten</p>
    </div>
  );

  const isOwner = (team) => team.owner_id === user.id;

  return (
    <div data-testid="teams-page" className="pt-20 min-h-screen">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="font-['Barlow_Condensed'] text-3xl sm:text-4xl font-bold text-white uppercase tracking-tight">Meine Teams</h1>
            <p className="text-sm text-zinc-500 mt-1">{teams.length} Teams</p>
            <p className="text-xs text-zinc-600 mt-1">Turnier-Anmeldungen sind nur mit Sub-Teams möglich.</p>
          </div>
          <div className="flex gap-2">
            {/* Join Team */}
            <Dialog open={joinOpen} onOpenChange={setJoinOpen}>
              <DialogTrigger asChild>
                <Button data-testid="join-team-btn" variant="outline" className="border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10 gap-2">
                  <Key className="w-4 h-4" />Beitreten
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-sm">
                <DialogHeader><DialogTitle className="font-['Barlow_Condensed'] text-xl text-white">Team beitreten</DialogTitle></DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <Label className="text-zinc-400 text-sm">Team-ID</Label>
                    <Input data-testid="join-team-id" value={joinForm.team_id} onChange={e => setJoinForm({...joinForm, team_id: e.target.value})} placeholder="Team-ID einfügen" className="bg-zinc-900 border-white/10 text-white mt-1 font-mono" />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-sm">Beitrittscode</Label>
                    <Input data-testid="join-team-code" value={joinForm.join_code} onChange={e => setJoinForm({...joinForm, join_code: e.target.value})} placeholder="6-stelliger Code" className="bg-zinc-900 border-white/10 text-white mt-1 font-mono uppercase" maxLength={6} />
                  </div>
                  <Button data-testid="submit-join-team" onClick={handleJoin} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">Beitreten</Button>
                </div>
              </DialogContent>
            </Dialog>
            {/* Create Team */}
            <Dialog open={createOpen} onOpenChange={setCreateOpen}>
              <DialogTrigger asChild>
                <Button data-testid="create-team-btn" className="bg-yellow-500 text-black hover:bg-yellow-400 font-semibold gap-2">
                  <Plus className="w-4 h-4" />Neues Team
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-sm">
                <DialogHeader><DialogTitle className="font-['Barlow_Condensed'] text-xl text-white">Team erstellen</DialogTitle></DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <Label className="text-zinc-400 text-sm">Team-Name</Label>
                    <Input data-testid="team-name-input" value={newTeam.name} onChange={e => setNewTeam({...newTeam, name: e.target.value})} placeholder="z.B. Team Alpha" className="bg-zinc-900 border-white/10 text-white mt-1" />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-sm">Tag (optional)</Label>
                    <Input data-testid="team-tag-input" value={newTeam.tag} onChange={e => setNewTeam({...newTeam, tag: e.target.value})} placeholder="z.B. ALPHA" className="bg-zinc-900 border-white/10 text-white mt-1" />
                  </div>
                  <Button data-testid="submit-create-team" onClick={handleCreate} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">Team erstellen</Button>
                </div>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {loading ? (
          <div className="flex justify-center py-16"><div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" /></div>
        ) : teams.length === 0 ? (
          <div className="text-center py-24 glass rounded-xl border border-white/5">
            <Users className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
            <p className="text-zinc-500">Noch keine Teams</p>
            <p className="text-xs text-zinc-600 mt-1">Erstelle ein Team oder tritt einem bei</p>
          </div>
        ) : (
          <div className="space-y-4">
            {teams.map((team, i) => (
              <motion.div key={team.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.05 }}
                data-testid={`team-card-${i}`}
                className="glass rounded-xl border border-white/5 hover:border-yellow-500/20 transition-all overflow-hidden"
              >
                <div className="p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-lg bg-yellow-500/10 flex items-center justify-center">
                        <Users className="w-5 h-5 text-yellow-500" />
                      </div>
                      <div>
                        <h3 className="font-['Barlow_Condensed'] text-xl font-bold text-white">{team.name}</h3>
                        {team.tag && <span className="text-xs text-zinc-500 font-mono">[{team.tag}]</span>}
                      </div>
                      {isOwner(team) && <Badge className="bg-yellow-500/10 text-yellow-500 text-xs">Owner</Badge>}
                    </div>
                    <div className="flex items-center gap-2">
                      {isOwner(team) && (
                        <>
                          <Button variant="ghost" size="sm" className="text-zinc-500 hover:text-white" onClick={() => toggleExpand(team.id)}>
                            {expandedTeam === team.id ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                          </Button>
                          <Button data-testid={`invite-member-${team.id}`} variant="outline" size="sm"
                            className="border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10 gap-1"
                            onClick={() => { setSelectedTeam(team); setInviteOpen(true); }}>
                            <UserPlus className="w-3 h-3" />Einladen
                          </Button>
                          <Button variant="outline" size="sm" className="border-cyan-500/30 text-cyan-500 hover:bg-cyan-500/10 gap-1"
                            onClick={() => { setSelectedTeam(team); setSubTeamOpen(true); }}>
                            <Plus className="w-3 h-3" />Sub-Team
                          </Button>
                          <Button data-testid={`delete-team-${team.id}`} variant="ghost" size="sm"
                            className="text-red-500 hover:text-red-400 hover:bg-red-500/10"
                            onClick={() => handleDelete(team.id)}>
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        </>
                      )}
                    </div>
                  </div>

                  {/* Join Code & Team ID (owner only) */}
                  {isOwner(team) && team.join_code && (
                    <div className="flex flex-wrap gap-3 mb-4 p-3 rounded-lg bg-zinc-900/50 border border-white/5">
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-500">Team-ID:</span>
                        <code className="text-xs text-yellow-500 font-mono">{team.id}</code>
                        <button onClick={() => copyToClipboard(team.id)} className="text-zinc-600 hover:text-white"><Copy className="w-3 h-3" /></button>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-zinc-500">Code:</span>
                        <code className="text-sm text-yellow-500 font-mono font-bold tracking-widest">{team.join_code}</code>
                        <button onClick={() => copyToClipboard(team.join_code)} className="text-zinc-600 hover:text-white"><Copy className="w-3 h-3" /></button>
                        <button onClick={() => handleRegenerateCode(team.id)} className="text-zinc-600 hover:text-yellow-500"><RefreshCw className="w-3 h-3" /></button>
                      </div>
                    </div>
                  )}

                  {/* Members */}
                  <div className="space-y-1">
                    <span className="text-xs text-zinc-500 uppercase tracking-wider">Mitglieder ({team.members?.length || 0})</span>
                    <div className="flex flex-wrap gap-2 mt-1">
                      {team.members?.map(m => (
                        <div key={m.id} className="flex items-center gap-2 bg-zinc-900 rounded-lg px-3 py-1.5 border border-white/5">
                          <img src={`https://api.dicebear.com/7.x/avataaars/svg?seed=${m.username}`} className="w-5 h-5 rounded-full" alt="" />
                          <span className="text-sm text-white">{m.username}</span>
                          {m.id === team.owner_id && <Crown className="w-3 h-3 text-yellow-500" title="Owner" />}
                          {m.role === "leader" && m.id !== team.owner_id && <Shield className="w-3 h-3 text-cyan-500" title="Leader" />}
                          {isOwner(team) && m.id !== user.id && (
                            <div className="flex gap-1 ml-1">
                              {team.leader_ids?.includes(m.id) ? (
                                <button onClick={() => handleDemoteLeader(team.id, m.id)} className="text-cyan-500 hover:text-zinc-400 text-xs" title="Leader entfernen">
                                  <Shield className="w-3 h-3" />
                                </button>
                              ) : (
                                <button onClick={() => handlePromoteLeader(team.id, m.id)} className="text-zinc-600 hover:text-cyan-500 text-xs" title="Zum Leader machen">
                                  <Shield className="w-3 h-3" />
                                </button>
                              )}
                              <button onClick={() => handleRemoveMember(team.id, m.id)} className="text-zinc-600 hover:text-red-500">
                                <X className="w-3 h-3" />
                              </button>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Sub-Teams */}
                {expandedTeam === team.id && (
                  <div className="border-t border-white/5 p-4 bg-zinc-950/50">
                    <h4 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Sub-Teams</h4>
                    {(subTeams[team.id] || []).length === 0 ? (
                      <p className="text-xs text-zinc-600">Keine Sub-Teams</p>
                    ) : (
                      <div className="space-y-2">
                        {subTeams[team.id].map(st => (
                          <div key={st.id} className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/50 border border-white/5">
                            <div className="flex items-center gap-2">
                              <Users className="w-4 h-4 text-cyan-500" />
                              <span className="text-sm text-white font-semibold">{st.name}</span>
                              {st.tag && <span className="text-xs text-zinc-500 font-mono">[{st.tag}]</span>}
                              <span className="text-xs text-zinc-600">{st.members?.length || 0} Mitglieder</span>
                            </div>
                            {isOwner(team) && (
                              <Button variant="ghost" size="sm" className="text-red-500 hover:text-red-400 h-6" onClick={() => handleDelete(st.id)}>
                                <Trash2 className="w-3 h-3" />
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </motion.div>
            ))}
          </div>
        )}

        {/* Invite Dialog */}
        <Dialog open={inviteOpen} onOpenChange={setInviteOpen}>
          <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-sm">
            <DialogHeader><DialogTitle className="font-['Barlow_Condensed'] text-xl text-white">Mitglied einladen</DialogTitle></DialogHeader>
            <div className="space-y-4 mt-4">
              <div>
                <Label className="text-zinc-400 text-sm">E-Mail des Spielers</Label>
                <Input data-testid="invite-email-input" type="email" value={inviteEmail} onChange={e => setInviteEmail(e.target.value)} placeholder="spieler@email.de" className="bg-zinc-900 border-white/10 text-white mt-1" />
              </div>
              <Button data-testid="submit-invite" onClick={handleInvite} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">Einladen</Button>
            </div>
          </DialogContent>
        </Dialog>

        {/* Sub-Team Dialog */}
        <Dialog open={subTeamOpen} onOpenChange={setSubTeamOpen}>
          <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-sm">
            <DialogHeader><DialogTitle className="font-['Barlow_Condensed'] text-xl text-white">Sub-Team erstellen</DialogTitle></DialogHeader>
            <div className="space-y-4 mt-4">
              <div>
                <Label className="text-zinc-400 text-sm">Sub-Team Name</Label>
                <Input value={newSubTeam.name} onChange={e => setNewSubTeam({...newSubTeam, name: e.target.value})} placeholder="z.B. Season 1 Squad" className="bg-zinc-900 border-white/10 text-white mt-1" />
              </div>
              <div>
                <Label className="text-zinc-400 text-sm">Tag (optional)</Label>
                <Input value={newSubTeam.tag} onChange={e => setNewSubTeam({...newSubTeam, tag: e.target.value})} placeholder="z.B. S1" className="bg-zinc-900 border-white/10 text-white mt-1" />
              </div>
              <Button onClick={handleCreateSubTeam} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">Sub-Team erstellen</Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}

import { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams, Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Users, Trophy, Zap, UserCheck, CreditCard, Play, Shield, Check, X as XIcon, MessageSquare, AlertTriangle, Copy, Code } from "lucide-react";
import BracketView from "@/components/BracketView";
import CommentSection from "@/components/CommentSection";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

const statusColors = {
  registration: "bg-blue-500/10 text-blue-400 border-blue-500/20",
  checkin: "bg-amber-500/10 text-amber-400 border-amber-500/20",
  live: "bg-red-500/10 text-red-400 border-red-500/20",
  completed: "bg-zinc-500/10 text-zinc-500 border-zinc-500/20",
};
const statusLabels = {
  registration: "Registrierung offen",
  checkin: "Check-in aktiv",
  live: "LIVE",
  completed: "Abgeschlossen",
};

function MarkdownRules({ text }) {
  if (!text) return null;
  const lines = text.split("\n");

  const renderInlineBold = (line) => {
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    return parts.map((part, idx) => {
      const match = part.match(/^\*\*(.+)\*\*$/);
      if (match) return <strong key={idx} className="text-white">{match[1]}</strong>;
      return <span key={idx}>{part}</span>;
    });
  };

  return (
    <div className="prose-sm text-zinc-400 space-y-2">
      {lines.map((line, i) => {
        if (line.startsWith("### ")) return <h4 key={i} className="text-white font-semibold text-sm mt-3">{line.slice(4)}</h4>;
        if (line.startsWith("## ")) return <h3 key={i} className="text-white font-bold text-base mt-4">{line.slice(3)}</h3>;
        if (line.startsWith("# ")) return <h2 key={i} className="text-white font-bold text-lg mt-4">{line.slice(2)}</h2>;
        if (line.startsWith("- ") || line.startsWith("* ")) return <li key={i} className="ml-4 text-sm text-zinc-400 list-disc">{renderInlineBold(line.slice(2))}</li>;
        if (line.match(/^\d+\.\s/)) return <li key={i} className="ml-4 text-sm text-zinc-400 list-decimal">{renderInlineBold(line.replace(/^\d+\.\s/, ""))}</li>;
        if (line.startsWith("> ")) return <blockquote key={i} className="border-l-2 border-yellow-500/50 pl-3 text-sm italic text-zinc-500">{renderInlineBold(line.slice(2))}</blockquote>;
        if (line.startsWith("---")) return <hr key={i} className="border-white/5 my-3" />;
        if (line.trim() === "") return <div key={i} className="h-2" />;
        return <p key={i} className="text-sm text-zinc-400">{renderInlineBold(line)}</p>;
      })}
    </div>
  );
}

export default function TournamentDetailPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const { user, isAdmin } = useAuth();
  const [tournament, setTournament] = useState(null);
  const [registrations, setRegistrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [regOpen, setRegOpen] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);
  const [resolveOpen, setResolveOpen] = useState(false);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [scoreForm, setScoreForm] = useState({ score1: 0, score2: 0 });
  const [resolveForm, setResolveForm] = useState({ score1: 0, score2: 0, disqualify_team_id: null });
  const [submissions, setSubmissions] = useState({});

  const [teamName, setTeamName] = useState("");
  const [players, setPlayers] = useState([{ name: "", email: "" }]);

  const fetchData = useCallback(async () => {
    try {
      const [tRes, rRes] = await Promise.all([
        axios.get(`${API}/tournaments/${id}`),
        axios.get(`${API}/tournaments/${id}/registrations`),
      ]);
      setTournament(tRes.data);
      setRegistrations(rRes.data);
    } catch {
      toast.error("Turnier nicht gefunden");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { fetchData(); }, [fetchData]);

  useEffect(() => {
    const sessionId = searchParams.get("session_id");
    if (sessionId) {
      const pollPayment = async (attempts = 0) => {
        if (attempts >= 5) return;
        try {
          const res = await axios.get(`${API}/payments/status/${sessionId}`);
          if (res.data.payment_status === "paid") {
            toast.success("Zahlung erfolgreich! Du bist registriert.");
            fetchData();
            return;
          }
        } catch { /* ignore */ }
        setTimeout(() => pollPayment(attempts + 1), 2000);
      };
      pollPayment();
    }
  }, [searchParams, fetchData]);

  const fetchSubmissions = async (matchId) => {
    try {
      const res = await axios.get(`${API}/tournaments/${id}/matches/${matchId}/submissions`);
      setSubmissions(prev => ({ ...prev, [matchId]: res.data }));
    } catch { /* ignore */ }
  };

  const handleRegister = async () => {
    if (!teamName.trim()) { toast.error("Team-Name ist erforderlich"); return; }
    if (players.length !== tournament.team_size) { toast.error(`Genau ${tournament.team_size} Spieler erforderlich`); return; }
    if (players.some(p => !p.name.trim() || !p.email.trim())) { toast.error("Alle Spieler-Daten ausfüllen"); return; }
    try {
      const res = await axios.post(`${API}/tournaments/${id}/register`, { team_name: teamName, players });
      toast.success("Registrierung erfolgreich!");
      setRegOpen(false);
      setTeamName("");
      setPlayers([{ name: "", email: "" }]);
      if (tournament.entry_fee > 0) {
        try {
          const payRes = await axios.post(`${API}/payments/create-checkout`, {
            tournament_id: id, registration_id: res.data.id, origin_url: window.location.origin,
          });
          window.location.href = payRes.data.url;
        } catch { toast.error("Zahlungsfehler. Bitte versuche es erneut."); }
      }
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || "Registrierung fehlgeschlagen"); }
  };

  const handleCheckin = async (regId) => {
    try {
      await axios.post(`${API}/tournaments/${id}/checkin/${regId}`);
      toast.success("Check-in erfolgreich!");
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || "Check-in fehlgeschlagen"); }
  };

  const handleGenerateBracket = async () => {
    try {
      await axios.post(`${API}/tournaments/${id}/generate-bracket`);
      toast.success("Bracket generiert!");
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || "Bracket konnte nicht generiert werden"); }
  };

  const handleSubmitScore = async () => {
    if (!selectedMatch) return;
    try {
      const res = await axios.post(`${API}/tournaments/${id}/matches/${selectedMatch.id}/submit-score`, scoreForm);
      toast.success(res.data.message);
      setScoreOpen(false);
      fetchData();
    } catch (e) { toast.error(e.response?.data?.detail || "Fehler beim Einreichen"); }
  };

  const handleAdminResolve = async () => {
    if (!selectedMatch) return;
    try {
      await axios.put(`${API}/tournaments/${id}/matches/${selectedMatch.id}/resolve`, resolveForm);
      toast.success("Ergebnis durch Admin festgelegt!");
      setResolveOpen(false);
      fetchData();
    } catch (e) { toast.error("Fehler beim Auflösen"); }
  };

  const handleAdminScoreUpdate = async () => {
    if (!selectedMatch) return;
    try {
      await axios.put(`${API}/tournaments/${id}/matches/${selectedMatch.id}/score`, scoreForm);
      toast.success("Ergebnis aktualisiert!");
      setScoreOpen(false);
      fetchData();
    } catch (e) { toast.error("Fehler beim Aktualisieren"); }
  };

  const openScoreDialog = (match) => {
    setSelectedMatch(match);
    setScoreForm({ score1: match.score1 || 0, score2: match.score2 || 0 });
    fetchSubmissions(match.id);
    setScoreOpen(true);
  };

  const openResolveDialog = (match) => {
    setSelectedMatch(match);
    setResolveForm({ score1: match.score1 || 0, score2: match.score2 || 0, disqualify_team_id: null });
    fetchSubmissions(match.id);
    setResolveOpen(true);
  };

  const handleStatusChange = async (newStatus) => {
    try {
      await axios.put(`${API}/tournaments/${id}`, { status: newStatus });
      toast.success(`Status geändert: ${statusLabels[newStatus] || newStatus}`);
      fetchData();
    } catch { toast.error("Statusänderung fehlgeschlagen"); }
  };

  const addPlayer = () => setPlayers([...players, { name: "", email: "" }]);
  const removePlayer = (idx) => setPlayers(players.filter((_, i) => i !== idx));
  const updatePlayer = (idx, field, value) => {
    const updated = [...players];
    updated[idx][field] = value;
    setPlayers(updated);
  };

  const copyToClipboard = (text) => { navigator.clipboard.writeText(text); toast.success("Kopiert!"); };

  if (loading) return (
    <div className="pt-20 min-h-screen flex items-center justify-center">
      <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (!tournament) return (
    <div className="pt-20 min-h-screen flex items-center justify-center">
      <p className="text-zinc-500">Turnier nicht gefunden</p>
    </div>
  );

  const canRegister = tournament.status === "registration" || tournament.status === "checkin";
  const isFull = (tournament.registered_count || 0) >= tournament.max_participants;

  const getAllMatches = () => {
    if (!tournament.bracket) return [];
    const bt = tournament.bracket.type;
    if (bt === "single_elimination" || bt === "round_robin") {
      return tournament.bracket.rounds?.flatMap(r => r.matches) || [];
    }
    if (bt === "double_elimination") {
      const wb = tournament.bracket.winners_bracket?.rounds?.flatMap(r => r.matches) || [];
      const lb = tournament.bracket.losers_bracket?.rounds?.flatMap(r => r.matches) || [];
      const gf = tournament.bracket.grand_final ? [tournament.bracket.grand_final] : [];
      return [...wb, ...lb, ...gf];
    }
    return [];
  };

  const embedCode = `<iframe src="${window.location.origin}/widget/${id}" width="100%" height="400" frameborder="0" style="border-radius:12px;overflow:hidden;"></iframe>`;

  return (
    <div data-testid="tournament-detail-page" className="pt-20 min-h-screen">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Header */}
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
          <div className="flex flex-wrap items-center gap-3 mb-3">
            <Badge className={`text-xs border ${statusColors[tournament.status]}`}>
              {statusLabels[tournament.status] || tournament.status}
            </Badge>
            <span className="text-xs text-zinc-500 font-mono uppercase">{tournament.bracket_type?.replace("_", " ")}</span>
            <span className="text-xs text-zinc-600 font-mono">Bo{tournament.best_of}</span>
          </div>
          <h1 data-testid="tournament-name" className="font-['Barlow_Condensed'] text-3xl sm:text-5xl font-extrabold text-white uppercase tracking-tight">
            {tournament.name}
          </h1>
          <div className="flex flex-wrap items-center gap-4 mt-3 text-sm text-zinc-400">
            <span className="flex items-center gap-1"><Zap className="w-4 h-4 text-yellow-500" />{tournament.game_name}</span>
            <span>{tournament.game_mode}</span>
            <span className="flex items-center gap-1"><Users className="w-4 h-4" />{tournament.registered_count || 0}/{tournament.max_participants}</span>
            {tournament.entry_fee > 0 && (
              <span className="flex items-center gap-1 text-yellow-500 font-mono"><CreditCard className="w-4 h-4" />${tournament.entry_fee.toFixed(2)}</span>
            )}
          </div>
        </motion.div>

        {/* Action buttons */}
        <div className="flex flex-wrap gap-2 mb-6">
          {/* Admin-only: Status changes */}
          {isAdmin && tournament.status === "registration" && (
            <Button data-testid="start-checkin-btn" variant="outline" className="border-amber-500/30 text-amber-400 hover:bg-amber-500/10" onClick={() => handleStatusChange("checkin")}>
              <UserCheck className="w-4 h-4 mr-2" />Check-in starten
            </Button>
          )}
          {isAdmin && (tournament.status === "checkin" || tournament.status === "registration") && registrations.length >= 2 && (
            <Button data-testid="generate-bracket-btn" className="bg-yellow-500 text-black hover:bg-yellow-400 font-semibold active:scale-95 transition-transform" onClick={handleGenerateBracket}>
              <Play className="w-4 h-4 mr-2" />Bracket generieren
            </Button>
          )}
          {/* Everyone: Registration */}
          {canRegister && !isFull && (
            <Dialog open={regOpen} onOpenChange={setRegOpen}>
              <DialogTrigger asChild>
                <Button data-testid="register-btn" className="bg-green-600 text-white hover:bg-green-500 font-semibold">
                  <Users className="w-4 h-4 mr-2" />Registrieren
                </Button>
              </DialogTrigger>
              <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-md max-h-[90vh] overflow-y-auto">
                <DialogHeader>
                  <DialogTitle className="font-['Barlow_Condensed'] text-xl text-white">Für Turnier registrieren</DialogTitle>
                </DialogHeader>
                <div className="space-y-4 mt-4">
                  <div>
                    <Label className="text-zinc-400 text-sm">Team-Name</Label>
                    <Input data-testid="reg-team-name" value={teamName} onChange={e => setTeamName(e.target.value)} placeholder="Team-Name eingeben" className="bg-zinc-900 border-white/10 text-white mt-1" />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-sm">Spieler ({tournament.team_size} benötigt)</Label>
                    {players.map((p, idx) => (
                      <div key={idx} className="flex gap-2 mt-2">
                        <Input data-testid={`reg-player-name-${idx}`} value={p.name} onChange={e => updatePlayer(idx, "name", e.target.value)} placeholder="Name" className="bg-zinc-900 border-white/10 text-white flex-1" />
                        <Input data-testid={`reg-player-email-${idx}`} value={p.email} onChange={e => updatePlayer(idx, "email", e.target.value)} placeholder="E-Mail" className="bg-zinc-900 border-white/10 text-white flex-1" />
                        {players.length > 1 && (
                          <Button variant="ghost" size="sm" onClick={() => removePlayer(idx)} className="text-red-500 hover:text-red-400 px-2"><XIcon className="w-4 h-4" /></Button>
                        )}
                      </div>
                    ))}
                    {players.length < tournament.team_size && (
                      <Button variant="ghost" size="sm" onClick={addPlayer} className="mt-2 text-yellow-500">+ Spieler hinzufügen</Button>
                    )}
                  </div>
                  {tournament.entry_fee > 0 && (
                    <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20">
                      <p className="text-sm text-yellow-500 flex items-center gap-2">
                        <CreditCard className="w-4 h-4" />Startgebühr: ${tournament.entry_fee.toFixed(2)} - Du wirst zur Zahlung weitergeleitet
                      </p>
                    </div>
                  )}
                  <Button data-testid="submit-registration-btn" onClick={handleRegister} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">
                    {tournament.entry_fee > 0 ? "Registrieren & Bezahlen" : "Jetzt registrieren"}
                  </Button>
                </div>
              </DialogContent>
            </Dialog>
          )}
        </div>

        {/* Tabs */}
        <Tabs defaultValue="bracket" className="mt-6">
          <TabsList className="bg-zinc-900/50 border border-white/5">
            <TabsTrigger data-testid="tab-bracket" value="bracket" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
              <Trophy className="w-4 h-4 mr-2" />Bracket
            </TabsTrigger>
            <TabsTrigger data-testid="tab-participants" value="participants" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
              <Users className="w-4 h-4 mr-2" />Teilnehmer
            </TabsTrigger>
            <TabsTrigger data-testid="tab-info" value="info" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
              <Shield className="w-4 h-4 mr-2" />Info & Regeln
            </TabsTrigger>
            <TabsTrigger data-testid="tab-comments" value="comments" className="data-[state=active]:bg-yellow-500/10 data-[state=active]:text-yellow-500">
              <MessageSquare className="w-4 h-4 mr-2" />Kommentare
            </TabsTrigger>
          </TabsList>

          <TabsContent value="bracket" className="mt-6">
            {tournament.bracket ? (
              <div className="glass rounded-xl p-6 border border-white/5">
                <BracketView bracket={tournament.bracket} />
                {/* Score entry section */}
                {tournament.status === "live" && (
                  <div className="mt-8 border-t border-white/5 pt-6">
                    <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white mb-1">Ergebnisse</h3>
                    <p className="text-xs text-zinc-500 mb-4">
                      {isAdmin ? "Admin: Du kannst Ergebnisse direkt setzen oder Streitfälle lösen." : "Beide Teams müssen das gleiche Ergebnis eintragen. Bei Unstimmigkeiten entscheidet der Admin."}
                    </p>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {getAllMatches().filter(m => m.team1_name !== "TBD" && m.team2_name !== "TBD" && m.team1_name !== "BYE" && m.team2_name !== "BYE").map(match => {
                        const subs = submissions[match.id] || [];
                        const isDisputed = subs.some(s => s.status === "disputed");
                        const isCompleted = match.status === "completed";
                        return (
                          <div key={match.id} data-testid={`match-card-${match.id}`}
                            className={`p-3 rounded-lg border transition-all ${isDisputed ? "bg-red-500/5 border-red-500/20" : isCompleted ? "bg-zinc-900/30 border-white/5" : "bg-zinc-900 border-white/5 hover:border-yellow-500/30"}`}
                          >
                            <div className="flex items-center justify-between mb-2">
                              <div className="text-sm text-white flex-1">
                                <div className={match.winner_id === match.team1_id ? "text-yellow-500 font-bold" : ""}>{match.team1_name}</div>
                                <div className="text-zinc-600 text-xs">vs</div>
                                <div className={match.winner_id === match.team2_id ? "text-yellow-500 font-bold" : ""}>{match.team2_name}</div>
                              </div>
                              {isCompleted && (
                                <div className="text-right font-mono text-sm">
                                  <div className={match.winner_id === match.team1_id ? "text-yellow-500 font-bold" : "text-zinc-500"}>{match.score1}</div>
                                  <div className="text-zinc-700">-</div>
                                  <div className={match.winner_id === match.team2_id ? "text-yellow-500 font-bold" : "text-zinc-500"}>{match.score2}</div>
                                </div>
                              )}
                            </div>
                            {isDisputed && (
                              <div className="flex items-center gap-1 text-red-400 text-xs mb-2">
                                <AlertTriangle className="w-3 h-3" />Ergebnisse stimmen nicht überein!
                              </div>
                            )}
                            <div className="flex gap-1">
                              {!isCompleted && user && (
                                <Button data-testid={`submit-score-${match.id}`} size="sm" className="flex-1 bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20 text-xs h-7"
                                  onClick={() => openScoreDialog(match)}>
                                  Ergebnis eintragen
                                </Button>
                              )}
                              {isAdmin && isDisputed && (
                                <Button data-testid={`resolve-score-${match.id}`} size="sm" className="flex-1 bg-red-500/10 text-red-400 hover:bg-red-500/20 text-xs h-7"
                                  onClick={() => openResolveDialog(match)}>
                                  Streit lösen
                                </Button>
                              )}
                              {isAdmin && !isCompleted && (
                                <Button size="sm" variant="ghost" className="text-zinc-500 hover:text-white text-xs h-7 px-2"
                                  onClick={() => { setSelectedMatch(match); setScoreForm({ score1: match.score1 || 0, score2: match.score2 || 0 }); setScoreOpen(true); }}>
                                  Admin
                                </Button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="glass rounded-xl p-12 text-center border border-white/5">
                <Trophy className="w-12 h-12 text-zinc-700 mx-auto mb-4" />
                <p className="text-zinc-500">Bracket wurde noch nicht generiert</p>
                <p className="text-xs text-zinc-600 mt-1">Mindestens 2 Teilnehmer benötigt</p>
              </div>
            )}
          </TabsContent>

          <TabsContent value="participants" className="mt-6">
            <div className="glass rounded-xl p-6 border border-white/5">
              {registrations.length === 0 ? (
                <p className="text-zinc-500 text-center py-8">Noch keine Teilnehmer registriert</p>
              ) : (
                <div className="space-y-2">
                  {registrations.map((reg, i) => (
                    <motion.div key={reg.id} initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.05 }}
                      data-testid={`participant-${i}`}
                      className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/50 border border-white/5"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-yellow-500/10 flex items-center justify-center text-yellow-500 font-mono text-sm font-bold">{reg.seed || i + 1}</div>
                        <div>
                          <div className="text-sm font-semibold text-white">{reg.team_name}</div>
                          <div className="text-xs text-zinc-500">{reg.players?.map(p => p.name).join(", ")}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {reg.payment_status === "paid" && <Badge className="bg-green-500/10 text-green-400 border border-green-500/20 text-xs">Bezahlt</Badge>}
                        {reg.payment_status === "pending" && <Badge className="bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs">Ausstehend</Badge>}
                        {reg.checked_in ? (
                          <Badge className="bg-green-500/10 text-green-400 border border-green-500/20 text-xs"><Check className="w-3 h-3 mr-1" />Eingecheckt</Badge>
                        ) : tournament.status === "checkin" && user && (
                          <Button data-testid={`checkin-${reg.id}`} size="sm" variant="outline" className="text-xs border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10" onClick={() => handleCheckin(reg.id)}>Check-in</Button>
                        )}
                      </div>
                    </motion.div>
                  ))}
                </div>
              )}
            </div>
          </TabsContent>

          <TabsContent value="info" className="mt-6">
            <div className="glass rounded-xl p-6 border border-white/5 space-y-6">
              <div className="grid sm:grid-cols-2 gap-6">
                <div>
                  <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white mb-3">Details</h3>
                  <div className="space-y-2 text-sm">
                    {[
                      ["Spiel", tournament.game_name],
                      ["Modus", tournament.game_mode],
                      ["Team-Größe", tournament.team_size],
                      ["Bracket-Typ", tournament.bracket_type?.replace("_", " ")],
                      ["Best of", tournament.best_of],
                    ].map(([label, value]) => (
                      <div key={label} className="flex justify-between py-2 border-b border-white/5">
                        <span className="text-zinc-500">{label}</span>
                        <span className="text-white capitalize">{value}</span>
                      </div>
                    ))}
                    <div className="flex justify-between py-2">
                      <span className="text-zinc-500">Startgebühr</span>
                      <span className={`font-mono ${tournament.entry_fee > 0 ? "text-yellow-500" : "text-green-500"}`}>
                        {tournament.entry_fee > 0 ? `$${tournament.entry_fee.toFixed(2)}` : "Kostenlos"}
                      </span>
                    </div>
                  </div>
                </div>
                <div>
                  {tournament.description && (
                    <div className="mb-4">
                      <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white mb-2">Beschreibung</h3>
                      <p className="text-sm text-zinc-400 whitespace-pre-wrap">{tournament.description}</p>
                    </div>
                  )}
                  {tournament.rules && (
                    <div>
                      <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white mb-2">Regelwerk</h3>
                      <MarkdownRules text={tournament.rules} />
                    </div>
                  )}
                  {tournament.prize_pool && (
                    <div className="mt-4 p-4 rounded-lg bg-yellow-500/5 border border-yellow-500/20">
                      <h4 className="text-xs text-yellow-500 uppercase tracking-wider mb-1">Preisgeld</h4>
                      <p className="text-lg font-bold text-yellow-500 font-mono">{tournament.prize_pool}</p>
                    </div>
                  )}
                </div>
              </div>

              {/* Embed Widget Code */}
              <div className="border-t border-white/5 pt-6">
                <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white mb-2 flex items-center gap-2">
                  <Code className="w-5 h-5 text-yellow-500" />Widget einbetten
                </h3>
                <p className="text-xs text-zinc-500 mb-3">Kopiere diesen Code, um das Turnier-Bracket auf deiner Webseite einzubetten:</p>
                <div className="relative">
                  <pre className="bg-zinc-900 rounded-lg p-4 text-xs text-zinc-400 overflow-x-auto border border-white/5 font-mono">{embedCode}</pre>
                  <Button data-testid="copy-embed-code" variant="ghost" size="sm" className="absolute top-2 right-2 text-zinc-500 hover:text-white"
                    onClick={() => copyToClipboard(embedCode)}>
                    <Copy className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </div>
          </TabsContent>

          <TabsContent value="comments" className="mt-6">
            <div className="glass rounded-xl p-6 border border-white/5">
              <CommentSection targetType="tournament" targetId={id} />
            </div>
          </TabsContent>
        </Tabs>

        {/* Score Submit Dialog (for players) */}
        <Dialog open={scoreOpen} onOpenChange={setScoreOpen}>
          <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-sm">
            <DialogHeader>
              <DialogTitle className="font-['Barlow_Condensed'] text-xl text-white">
                {isAdmin ? "Ergebnis setzen (Admin)" : "Ergebnis eintragen"}
              </DialogTitle>
            </DialogHeader>
            {selectedMatch && (
              <div className="space-y-4 mt-4">
                {/* Show existing submissions */}
                {submissions[selectedMatch.id]?.length > 0 && (
                  <div className="p-3 rounded-lg bg-zinc-900 border border-white/5 space-y-2">
                    <span className="text-xs text-zinc-500 uppercase">Bisherige Einreichungen:</span>
                    {submissions[selectedMatch.id].map(s => (
                      <div key={s.id || s.side} className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">{s.submitted_by_name} ({s.side})</span>
                        <span className="font-mono text-white">{s.score1} : {s.score2}</span>
                        {s.status === "disputed" && <Badge className="bg-red-500/10 text-red-400 text-[10px]">Streit</Badge>}
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-4">
                  <div className="flex-1 text-center">
                    <p className="text-sm text-white font-semibold mb-2">{selectedMatch.team1_name}</p>
                    <Input data-testid="score-team1" type="number" min="0" value={scoreForm.score1}
                      onChange={e => setScoreForm({ ...scoreForm, score1: parseInt(e.target.value) || 0 })}
                      className="bg-zinc-900 border-white/10 text-white text-center text-2xl font-mono h-14" />
                  </div>
                  <span className="text-zinc-600 font-bold text-lg">vs</span>
                  <div className="flex-1 text-center">
                    <p className="text-sm text-white font-semibold mb-2">{selectedMatch.team2_name}</p>
                    <Input data-testid="score-team2" type="number" min="0" value={scoreForm.score2}
                      onChange={e => setScoreForm({ ...scoreForm, score2: parseInt(e.target.value) || 0 })}
                      className="bg-zinc-900 border-white/10 text-white text-center text-2xl font-mono h-14" />
                  </div>
                </div>
                <Button data-testid="submit-score-btn" onClick={isAdmin ? handleAdminScoreUpdate : handleSubmitScore}
                  className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">
                  {isAdmin ? "Ergebnis setzen (Admin)" : "Ergebnis einreichen"}
                </Button>
                {!isAdmin && (
                  <p className="text-[11px] text-zinc-600 text-center">Beide Teams müssen das gleiche Ergebnis eintragen, um es zu bestätigen.</p>
                )}
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Resolve Dispute Dialog (admin only) */}
        <Dialog open={resolveOpen} onOpenChange={setResolveOpen}>
          <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-md">
            <DialogHeader>
              <DialogTitle className="font-['Barlow_Condensed'] text-xl text-white flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-red-400" />Streit lösen
              </DialogTitle>
            </DialogHeader>
            {selectedMatch && (
              <div className="space-y-4 mt-4">
                {/* Show conflicting submissions */}
                {submissions[selectedMatch.id]?.length > 0 && (
                  <div className="p-3 rounded-lg bg-red-500/5 border border-red-500/20 space-y-2">
                    <span className="text-xs text-red-400 uppercase font-semibold">Widersprüchliche Ergebnisse:</span>
                    {submissions[selectedMatch.id].map(s => (
                      <div key={s.id || s.side} className="flex items-center justify-between text-sm">
                        <span className="text-zinc-400">{s.submitted_by_name} ({s.side})</span>
                        <span className="font-mono text-white font-bold">{s.score1} : {s.score2}</span>
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex items-center gap-4">
                  <div className="flex-1 text-center">
                    <p className="text-sm text-white font-semibold mb-2">{selectedMatch.team1_name}</p>
                    <Input type="number" min="0" value={resolveForm.score1}
                      onChange={e => setResolveForm({ ...resolveForm, score1: parseInt(e.target.value) || 0 })}
                      className="bg-zinc-900 border-white/10 text-white text-center text-2xl font-mono h-14" />
                  </div>
                  <span className="text-zinc-600 font-bold text-lg">vs</span>
                  <div className="flex-1 text-center">
                    <p className="text-sm text-white font-semibold mb-2">{selectedMatch.team2_name}</p>
                    <Input type="number" min="0" value={resolveForm.score2}
                      onChange={e => setResolveForm({ ...resolveForm, score2: parseInt(e.target.value) || 0 })}
                      className="bg-zinc-900 border-white/10 text-white text-center text-2xl font-mono h-14" />
                  </div>
                </div>
                <div>
                  <Label className="text-zinc-400 text-xs">Disqualifizierung (optional)</Label>
                  <div className="flex gap-2 mt-1">
                    <Button size="sm" variant={resolveForm.disqualify_team_id === selectedMatch.team1_id ? "default" : "outline"}
                      className={resolveForm.disqualify_team_id === selectedMatch.team1_id ? "bg-red-500 text-white" : "border-white/10 text-zinc-400"}
                      onClick={() => setResolveForm({ ...resolveForm, disqualify_team_id: resolveForm.disqualify_team_id === selectedMatch.team1_id ? null : selectedMatch.team1_id })}>
                      {selectedMatch.team1_name} DQ
                    </Button>
                    <Button size="sm" variant={resolveForm.disqualify_team_id === selectedMatch.team2_id ? "default" : "outline"}
                      className={resolveForm.disqualify_team_id === selectedMatch.team2_id ? "bg-red-500 text-white" : "border-white/10 text-zinc-400"}
                      onClick={() => setResolveForm({ ...resolveForm, disqualify_team_id: resolveForm.disqualify_team_id === selectedMatch.team2_id ? null : selectedMatch.team2_id })}>
                      {selectedMatch.team2_name} DQ
                    </Button>
                  </div>
                </div>
                <Button onClick={handleAdminResolve} className="w-full bg-red-500 text-white hover:bg-red-400 font-semibold">
                  Endgültiges Ergebnis festlegen
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}

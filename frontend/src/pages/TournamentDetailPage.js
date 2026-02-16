import { useState, useEffect, useCallback } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { Users, Trophy, Zap, UserCheck, CreditCard, Play, Shield, Check, X as XIcon, MessageSquare } from "lucide-react";
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

export default function TournamentDetailPage() {
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const [tournament, setTournament] = useState(null);
  const [registrations, setRegistrations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [regOpen, setRegOpen] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);
  const [selectedMatch, setSelectedMatch] = useState(null);
  const [scoreForm, setScoreForm] = useState({ score1: 0, score2: 0 });

  // Registration form
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
    } catch (e) {
      toast.error("Turnier nicht gefunden");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Poll payment status on return from Stripe
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
        } catch (e) { /* ignore */ }
        setTimeout(() => pollPayment(attempts + 1), 2000);
      };
      pollPayment();
    }
  }, [searchParams, fetchData]);

  const handleRegister = async () => {
    if (!teamName.trim()) { toast.error("Team-Name ist erforderlich"); return; }
    if (players.some(p => !p.name.trim() || !p.email.trim())) { toast.error("Alle Spieler-Daten ausfüllen"); return; }
    try {
      const res = await axios.post(`${API}/tournaments/${id}/register`, { team_name: teamName, players });
      toast.success("Registrierung erfolgreich!");
      setRegOpen(false);
      setTeamName("");
      setPlayers([{ name: "", email: "" }]);

      // If paid tournament, initiate payment
      if (tournament.entry_fee > 0) {
        try {
          const payRes = await axios.post(`${API}/payments/create-checkout`, {
            tournament_id: id,
            registration_id: res.data.id,
            origin_url: window.location.origin,
          });
          window.location.href = payRes.data.url;
        } catch (e) {
          toast.error("Zahlungsfehler. Bitte versuche es erneut.");
        }
      }
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Registrierung fehlgeschlagen");
    }
  };

  const handleCheckin = async (regId) => {
    try {
      await axios.post(`${API}/tournaments/${id}/checkin/${regId}`);
      toast.success("Check-in erfolgreich!");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Check-in fehlgeschlagen");
    }
  };

  const handleGenerateBracket = async () => {
    try {
      await axios.post(`${API}/tournaments/${id}/generate-bracket`);
      toast.success("Bracket generiert!");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Bracket konnte nicht generiert werden");
    }
  };

  const handleUpdateScore = async () => {
    if (!selectedMatch) return;
    try {
      await axios.put(`${API}/tournaments/${id}/matches/${selectedMatch.id}/score`, scoreForm);
      toast.success("Ergebnis aktualisiert!");
      setScoreOpen(false);
      fetchData();
    } catch (e) {
      toast.error("Fehler beim Aktualisieren");
    }
  };

  const openScoreDialog = (match) => {
    setSelectedMatch(match);
    setScoreForm({ score1: match.score1 || 0, score2: match.score2 || 0 });
    setScoreOpen(true);
  };

  const handleStatusChange = async (newStatus) => {
    try {
      await axios.put(`${API}/tournaments/${id}`, { status: newStatus });
      toast.success(`Status geändert: ${statusLabels[newStatus] || newStatus}`);
      fetchData();
    } catch (e) {
      toast.error("Statusänderung fehlgeschlagen");
    }
  };

  const addPlayer = () => setPlayers([...players, { name: "", email: "" }]);
  const removePlayer = (idx) => setPlayers(players.filter((_, i) => i !== idx));
  const updatePlayer = (idx, field, value) => {
    const updated = [...players];
    updated[idx][field] = value;
    setPlayers(updated);
  };

  if (loading) {
    return (
      <div className="pt-20 min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!tournament) {
    return (
      <div className="pt-20 min-h-screen flex items-center justify-center">
        <p className="text-zinc-500">Turnier nicht gefunden</p>
      </div>
    );
  }

  const canRegister = tournament.status === "registration" || tournament.status === "checkin";
  const isFull = (tournament.registered_count || 0) >= tournament.max_participants;

  // Get all matches from bracket for score editing
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

        {/* Admin actions */}
        <div className="flex flex-wrap gap-2 mb-6">
          {tournament.status === "registration" && (
            <Button data-testid="start-checkin-btn" variant="outline" className="border-amber-500/30 text-amber-400 hover:bg-amber-500/10" onClick={() => handleStatusChange("checkin")}>
              <UserCheck className="w-4 h-4 mr-2" />Check-in starten
            </Button>
          )}
          {(tournament.status === "checkin" || tournament.status === "registration") && registrations.length >= 2 && (
            <Button data-testid="generate-bracket-btn" className="bg-yellow-500 text-black hover:bg-yellow-400 font-semibold active:scale-95 transition-transform" onClick={handleGenerateBracket}>
              <Play className="w-4 h-4 mr-2" />Bracket generieren
            </Button>
          )}
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
                    <Input
                      data-testid="reg-team-name"
                      value={teamName}
                      onChange={e => setTeamName(e.target.value)}
                      placeholder="Team-Name eingeben"
                      className="bg-zinc-900 border-white/10 text-white mt-1"
                    />
                  </div>
                  <div>
                    <Label className="text-zinc-400 text-sm">Spieler ({tournament.team_size} benötigt)</Label>
                    {players.map((p, idx) => (
                      <div key={idx} className="flex gap-2 mt-2">
                        <Input
                          data-testid={`reg-player-name-${idx}`}
                          value={p.name}
                          onChange={e => updatePlayer(idx, "name", e.target.value)}
                          placeholder="Name"
                          className="bg-zinc-900 border-white/10 text-white flex-1"
                        />
                        <Input
                          data-testid={`reg-player-email-${idx}`}
                          value={p.email}
                          onChange={e => updatePlayer(idx, "email", e.target.value)}
                          placeholder="E-Mail"
                          className="bg-zinc-900 border-white/10 text-white flex-1"
                        />
                        {players.length > 1 && (
                          <Button variant="ghost" size="sm" onClick={() => removePlayer(idx)} className="text-red-500 hover:text-red-400 px-2">
                            <XIcon className="w-4 h-4" />
                          </Button>
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
                        <CreditCard className="w-4 h-4" />
                        Startgebühr: ${tournament.entry_fee.toFixed(2)} - Du wirst zur Zahlung weitergeleitet
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
              <Shield className="w-4 h-4 mr-2" />Info
            </TabsTrigger>
          </TabsList>

          <TabsContent value="bracket" className="mt-6">
            {tournament.bracket ? (
              <div className="glass rounded-xl p-6 border border-white/5">
                <BracketView bracket={tournament.bracket} isAdmin={true} />
                {/* Score update section */}
                {tournament.status === "live" && (
                  <div className="mt-8 border-t border-white/5 pt-6">
                    <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white mb-4">Ergebnisse eintragen</h3>
                    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
                      {getAllMatches().filter(m => m.status !== "completed" && m.team1_name !== "TBD" && m.team2_name !== "TBD" && m.team1_name !== "BYE" && m.team2_name !== "BYE").map(match => (
                        <button
                          key={match.id}
                          data-testid={`edit-score-${match.id}`}
                          onClick={() => openScoreDialog(match)}
                          className="flex items-center justify-between p-3 rounded-lg bg-zinc-900 border border-white/5 hover:border-yellow-500/30 transition-all text-left"
                        >
                          <div className="text-sm">
                            <div className="text-white">{match.team1_name}</div>
                            <div className="text-zinc-500">vs</div>
                            <div className="text-white">{match.team2_name}</div>
                          </div>
                          <Zap className="w-4 h-4 text-yellow-500" />
                        </button>
                      ))}
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
                    <motion.div
                      key={reg.id}
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      data-testid={`participant-${i}`}
                      className="flex items-center justify-between p-3 rounded-lg bg-zinc-900/50 border border-white/5"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 rounded bg-yellow-500/10 flex items-center justify-center text-yellow-500 font-mono text-sm font-bold">
                          {reg.seed || i + 1}
                        </div>
                        <div>
                          <div className="text-sm font-semibold text-white">{reg.team_name}</div>
                          <div className="text-xs text-zinc-500">{reg.players?.map(p => p.name).join(", ")}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {reg.payment_status === "paid" && (
                          <Badge className="bg-green-500/10 text-green-400 border border-green-500/20 text-xs">Bezahlt</Badge>
                        )}
                        {reg.payment_status === "pending" && (
                          <Badge className="bg-amber-500/10 text-amber-400 border border-amber-500/20 text-xs">Ausstehend</Badge>
                        )}
                        {reg.checked_in ? (
                          <Badge className="bg-green-500/10 text-green-400 border border-green-500/20 text-xs">
                            <Check className="w-3 h-3 mr-1" />Eingecheckt
                          </Badge>
                        ) : (
                          tournament.status === "checkin" && (
                            <Button
                              data-testid={`checkin-${reg.id}`}
                              size="sm"
                              variant="outline"
                              className="text-xs border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10"
                              onClick={() => handleCheckin(reg.id)}
                            >
                              Check-in
                            </Button>
                          )
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
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-zinc-500">Spiel</span>
                      <span className="text-white">{tournament.game_name}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-zinc-500">Modus</span>
                      <span className="text-white">{tournament.game_mode}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-zinc-500">Team-Größe</span>
                      <span className="text-white">{tournament.team_size}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-zinc-500">Bracket-Typ</span>
                      <span className="text-white capitalize">{tournament.bracket_type?.replace("_", " ")}</span>
                    </div>
                    <div className="flex justify-between py-2 border-b border-white/5">
                      <span className="text-zinc-500">Best of</span>
                      <span className="text-white font-mono">{tournament.best_of}</span>
                    </div>
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
                      <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-white mb-2">Regeln</h3>
                      <p className="text-sm text-zinc-400 whitespace-pre-wrap">{tournament.rules}</p>
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
            </div>
          </TabsContent>
        </Tabs>

        {/* Score Update Dialog */}
        <Dialog open={scoreOpen} onOpenChange={setScoreOpen}>
          <DialogContent className="bg-zinc-950 border-white/10 text-white max-w-sm">
            <DialogHeader>
              <DialogTitle className="font-['Barlow_Condensed'] text-xl text-white">Ergebnis eintragen</DialogTitle>
            </DialogHeader>
            {selectedMatch && (
              <div className="space-y-4 mt-4">
                <div className="flex items-center gap-4">
                  <div className="flex-1 text-center">
                    <p className="text-sm text-white font-semibold mb-2">{selectedMatch.team1_name}</p>
                    <Input
                      data-testid="score-team1"
                      type="number"
                      min="0"
                      value={scoreForm.score1}
                      onChange={e => setScoreForm({ ...scoreForm, score1: parseInt(e.target.value) || 0 })}
                      className="bg-zinc-900 border-white/10 text-white text-center text-2xl font-mono h-14"
                    />
                  </div>
                  <span className="text-zinc-600 font-bold text-lg">vs</span>
                  <div className="flex-1 text-center">
                    <p className="text-sm text-white font-semibold mb-2">{selectedMatch.team2_name}</p>
                    <Input
                      data-testid="score-team2"
                      type="number"
                      min="0"
                      value={scoreForm.score2}
                      onChange={e => setScoreForm({ ...scoreForm, score2: parseInt(e.target.value) || 0 })}
                      className="bg-zinc-900 border-white/10 text-white text-center text-2xl font-mono h-14"
                    />
                  </div>
                </div>
                <Button data-testid="submit-score-btn" onClick={handleUpdateScore} className="w-full bg-yellow-500 text-black hover:bg-yellow-400 font-semibold">
                  Ergebnis speichern
                </Button>
              </div>
            )}
          </DialogContent>
        </Dialog>
      </div>
    </div>
  );
}

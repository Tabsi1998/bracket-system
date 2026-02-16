import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { motion } from "framer-motion";
import { toast } from "sonner";
import { ArrowLeft, Trophy, Gamepad2, Shield } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

const bracketTypes = [
  { value: "single_elimination", label: "Single Elimination" },
  { value: "double_elimination", label: "Double Elimination" },
  { value: "round_robin", label: "Round Robin" },
  { value: "group_playoffs", label: "Gruppenphase + Playoffs" },
  { value: "league", label: "Liga (Spieltage + Tabelle)" },
  { value: "group_stage", label: "Gruppenphase" },
  { value: "swiss_system", label: "Swiss System" },
  { value: "ladder_system", label: "Ladder System" },
  { value: "king_of_the_hill", label: "King of the Hill" },
  { value: "battle_royale", label: "Battle Royale" },
];

export default function CreateTournamentPage() {
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const [games, setGames] = useState([]);
  const [selectedGame, setSelectedGame] = useState(null);
  const [form, setForm] = useState({
    name: "",
    game_id: "",
    game_mode: "",
    participant_mode: "team",
    team_size: 1,
    max_participants: 8,
    bracket_type: "single_elimination",
    require_admin_score_approval: false,
    best_of: 1,
    entry_fee: 0,
    currency: "usd",
    prize_pool: "",
    description: "",
    rules: "",
    start_date: "",
    group_size: 4,
    advance_per_group: 2,
    swiss_rounds: 5,
    battle_royale_group_size: 4,
    battle_royale_advance: 2,
    matchday_interval_days: 7,
    matchday_window_days: 7,
    points_win: 3,
    points_draw: 1,
    points_loss: 0,
    tiebreakers: "points,score_diff,score_for,team_name",
  });
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    axios.get(`${API}/games`).then(r => setGames(r.data)).catch(() => {});
  }, []);

  const handleGameSelect = (gameId) => {
    const game = games.find(g => g.id === gameId);
    setSelectedGame(game);
    setForm({ ...form, game_id: gameId, game_mode: "", team_size: 1 });
  };

  const handleModeSelect = (modeName) => {
    const mode = selectedGame?.modes?.find(m => m.name === modeName);
    setForm({
      ...form,
      game_mode: modeName,
      team_size: form.participant_mode === "solo" ? 1 : (mode?.team_size || 1),
    });
  };

  const handleSubmit = async () => {
    if (!form.name.trim()) { toast.error("Turniername ist erforderlich"); return; }
    if (!form.game_id) { toast.error("Bitte wähle ein Spiel"); return; }
    if (!form.game_mode) { toast.error("Bitte wähle einen Spielmodus"); return; }
    setSubmitting(true);
    try {
      const parsedTieBreakers = String(form.tiebreakers || "")
        .split(",")
        .map((x) => x.trim().toLowerCase())
        .filter(Boolean);
      const payload = {
        ...form,
        team_size: form.participant_mode === "solo" ? 1 : form.team_size,
        matchday_interval_days: Math.max(1, parseInt(form.matchday_interval_days, 10) || 7),
        matchday_window_days: Math.max(1, parseInt(form.matchday_window_days, 10) || 7),
        points_win: Math.max(0, parseInt(form.points_win, 10) || 0),
        points_draw: Math.max(0, parseInt(form.points_draw, 10) || 0),
        points_loss: Math.max(0, parseInt(form.points_loss, 10) || 0),
        tiebreakers: parsedTieBreakers.length > 0 ? parsedTieBreakers : ["points", "score_diff", "score_for", "team_name"],
        require_admin_score_approval:
          form.bracket_type === "battle_royale" ? true : form.require_admin_score_approval,
      };
      const res = await axios.post(`${API}/tournaments`, payload);
      toast.success("Turnier erstellt!");
      navigate(`/tournaments/${res.data.id}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Fehler beim Erstellen");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div data-testid="create-tournament-page" className="pt-20 min-h-screen">
      {!isAdmin ? (
        <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
          <Shield className="w-16 h-16 text-red-500/30" />
          <p className="text-zinc-500 text-lg">Nur Admins können Turniere erstellen</p>
          <Button variant="outline" onClick={() => navigate("/")} className="border-white/10 text-white">Zurück</Button>
        </div>
      ) : (
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Button variant="ghost" onClick={() => navigate(-1)} className="text-zinc-400 hover:text-white mb-6 gap-2">
          <ArrowLeft className="w-4 h-4" />Zurück
        </Button>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="font-['Barlow_Condensed'] text-3xl sm:text-4xl font-bold text-white uppercase tracking-tight mb-8 flex items-center gap-3">
            <Trophy className="w-8 h-8 text-yellow-500" />
            Turnier erstellen
          </h1>

          <div className="space-y-8">
            {/* Basic Info */}
            <div className="glass rounded-xl p-6 border border-white/5 space-y-4">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase tracking-wider">Grundinfos</h2>
              <div>
                <Label className="text-zinc-400 text-sm">Turniername *</Label>
                <Input
                  data-testid="tournament-name-input"
                  value={form.name}
                  onChange={e => setForm({ ...form, name: e.target.value })}
                  placeholder="z.B. CoD 5v5 Championship"
                  className="bg-zinc-900 border-white/10 text-white mt-1"
                />
              </div>
              <div>
                <Label className="text-zinc-400 text-sm">Beschreibung</Label>
                <Textarea
                  data-testid="tournament-desc-input"
                  value={form.description}
                  onChange={e => setForm({ ...form, description: e.target.value })}
                  placeholder="Beschreibe dein Turnier..."
                  className="bg-zinc-900 border-white/10 text-white mt-1 min-h-[80px]"
                />
              </div>
            </div>

            {/* Game Selection */}
            <div className="glass rounded-xl p-6 border border-white/5 space-y-4">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase tracking-wider flex items-center gap-2">
                <Gamepad2 className="w-5 h-5 text-yellow-500" />
                Spiel & Modus
              </h2>
              <div>
                <Label className="text-zinc-400 text-sm">Spiel auswählen *</Label>
                <Select value={form.game_id} onValueChange={handleGameSelect}>
                  <SelectTrigger data-testid="game-select" className="bg-zinc-900 border-white/10 text-white mt-1">
                    <SelectValue placeholder="Spiel wählen..." />
                  </SelectTrigger>
                  <SelectContent className="bg-zinc-950 border-white/10">
                    {games.map(g => (
                      <SelectItem key={g.id} value={g.id}>{g.name} ({g.short_name})</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {selectedGame && selectedGame.modes && selectedGame.modes.length > 0 && (
                <div>
                  <Label className="text-zinc-400 text-sm">Spielmodus *</Label>
                  <div className="grid grid-cols-3 sm:grid-cols-5 gap-2 mt-2">
                    {selectedGame.modes.map(mode => (
                      <button
                        key={mode.name}
                        data-testid={`mode-${mode.name}`}
                        onClick={() => handleModeSelect(mode.name)}
                        className={`p-3 rounded-lg border text-sm font-semibold transition-all ${
                          form.game_mode === mode.name
                            ? "border-yellow-500 bg-yellow-500/10 text-yellow-500"
                            : "border-white/10 bg-zinc-900 text-zinc-400 hover:border-white/20"
                        }`}
                      >
                        {mode.name}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Tournament Settings */}
            <div className="glass rounded-xl p-6 border border-white/5 space-y-4">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase tracking-wider">Einstellungen</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <Label className="text-zinc-400 text-sm">Max. Teilnehmer</Label>
                  <Select value={String(form.max_participants)} onValueChange={v => setForm({ ...form, max_participants: parseInt(v) })}>
                    <SelectTrigger data-testid="max-participants-select" className="bg-zinc-900 border-white/10 text-white mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-white/10">
                      {[4, 8, 16, 32, 64, 128].map(n => (
                        <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Teilnehmer-Modus</Label>
                  <Select value={form.participant_mode} onValueChange={v => setForm({ ...form, participant_mode: v, team_size: v === "solo" ? 1 : form.team_size })}>
                    <SelectTrigger className="bg-zinc-900 border-white/10 text-white mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-white/10">
                      <SelectItem value="team">Team</SelectItem>
                      <SelectItem value="solo">Einzelspieler</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Bracket-Typ</Label>
                  <Select value={form.bracket_type} onValueChange={v => setForm({ ...form, bracket_type: v })}>
                    <SelectTrigger data-testid="bracket-type-select" className="bg-zinc-900 border-white/10 text-white mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-white/10">
                      {bracketTypes.map(bt => (
                        <SelectItem key={bt.value} value={bt.value}>{bt.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                {(form.bracket_type === "group_stage" || form.bracket_type === "group_playoffs") && (
                  <div>
                    <Label className="text-zinc-400 text-sm">Gruppengröße</Label>
                    <Select value={String(form.group_size)} onValueChange={v => setForm({ ...form, group_size: parseInt(v, 10) || 4 })}>
                      <SelectTrigger className="bg-zinc-900 border-white/10 text-white mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-950 border-white/10">
                        {[2, 3, 4, 5, 6, 8].map(n => (
                          <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {form.bracket_type === "group_playoffs" && (
                  <div>
                    <Label className="text-zinc-400 text-sm">Aufsteiger pro Gruppe</Label>
                    <Select value={String(form.advance_per_group)} onValueChange={v => setForm({ ...form, advance_per_group: parseInt(v, 10) || 2 })}>
                      <SelectTrigger className="bg-zinc-900 border-white/10 text-white mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-950 border-white/10">
                        {[1, 2, 3, 4].map(n => (
                          <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {form.bracket_type === "swiss_system" && (
                  <div>
                    <Label className="text-zinc-400 text-sm">Swiss-Runden</Label>
                    <Select value={String(form.swiss_rounds)} onValueChange={v => setForm({ ...form, swiss_rounds: parseInt(v, 10) || 5 })}>
                      <SelectTrigger className="bg-zinc-900 border-white/10 text-white mt-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-zinc-950 border-white/10">
                        {[3, 4, 5, 6, 7, 8, 9].map(n => (
                          <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
                {form.bracket_type === "battle_royale" && (
                  <>
                    <div>
                      <Label className="text-zinc-400 text-sm">Heat-Größe</Label>
                      <Select value={String(form.battle_royale_group_size)} onValueChange={v => setForm({ ...form, battle_royale_group_size: parseInt(v, 10) || 4 })}>
                        <SelectTrigger className="bg-zinc-900 border-white/10 text-white mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-zinc-950 border-white/10">
                          {[3, 4, 5, 6, 8, 10, 12].map(n => (
                            <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                    <div>
                      <Label className="text-zinc-400 text-sm">Aufsteiger pro Heat</Label>
                      <Select value={String(form.battle_royale_advance)} onValueChange={v => setForm({ ...form, battle_royale_advance: parseInt(v, 10) || 2 })}>
                        <SelectTrigger className="bg-zinc-900 border-white/10 text-white mt-1">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-zinc-950 border-white/10">
                          {[1, 2, 3, 4, 5, 6].map(n => (
                            <SelectItem key={n} value={String(n)}>{n}</SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </>
                )}
                <div>
                  <Label className="text-zinc-400 text-sm">Admin-Freigabe für Ergebnisse</Label>
                  <Select
                    value={String(form.bracket_type === "battle_royale" ? true : form.require_admin_score_approval)}
                    onValueChange={v => setForm({ ...form, require_admin_score_approval: v === "true" })}
                    disabled={form.bracket_type === "battle_royale"}
                  >
                    <SelectTrigger className="bg-zinc-900 border-white/10 text-white mt-1 disabled:opacity-70">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-white/10">
                      <SelectItem value="false">Nein, Team-Eingaben bestätigen direkt</SelectItem>
                      <SelectItem value="true">Ja, Admin muss freigeben</SelectItem>
                    </SelectContent>
                  </Select>
                  {form.bracket_type === "battle_royale" && (
                    <p className="text-[11px] text-zinc-600 mt-1">Bei Battle Royale ist die Admin-Freigabe immer aktiv.</p>
                  )}
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Best of</Label>
                  <Select value={String(form.best_of)} onValueChange={v => setForm({ ...form, best_of: parseInt(v) })}>
                    <SelectTrigger data-testid="best-of-select" className="bg-zinc-900 border-white/10 text-white mt-1">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-zinc-950 border-white/10">
                      {[1, 3, 5, 7].map(n => (
                        <SelectItem key={n} value={String(n)}>Best of {n}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Startdatum</Label>
                  <Input
                    data-testid="start-date-input"
                    type="datetime-local"
                    value={form.start_date}
                    onChange={e => setForm({ ...form, start_date: e.target.value })}
                    className="bg-zinc-900 border-white/10 text-white mt-1"
                  />
                </div>
                {["league", "round_robin", "group_stage", "group_playoffs"].includes(form.bracket_type) && (
                  <>
                    <div>
                      <Label className="text-zinc-400 text-sm">Spieltag-Intervall (Tage)</Label>
                      <Input
                        type="number"
                        min="1"
                        value={form.matchday_interval_days}
                        onChange={e => setForm({ ...form, matchday_interval_days: parseInt(e.target.value, 10) || 7 })}
                        className="bg-zinc-900 border-white/10 text-white mt-1"
                      />
                    </div>
                    <div>
                      <Label className="text-zinc-400 text-sm">Spieltag-Fenster (Tage)</Label>
                      <Input
                        type="number"
                        min="1"
                        value={form.matchday_window_days}
                        onChange={e => setForm({ ...form, matchday_window_days: parseInt(e.target.value, 10) || 7 })}
                        className="bg-zinc-900 border-white/10 text-white mt-1"
                      />
                    </div>
                  </>
                )}
              </div>
              {["league", "round_robin", "group_stage", "group_playoffs", "swiss_system", "ladder_system", "king_of_the_hill", "battle_royale"].includes(form.bracket_type) && (
                <div className="border-t border-white/5 pt-4">
                  <h3 className="text-sm text-zinc-300 font-semibold mb-3">Punktesystem & Tie-Break</h3>
                  <div className="grid sm:grid-cols-4 gap-4">
                    <div>
                      <Label className="text-zinc-400 text-sm">Punkte Sieg</Label>
                      <Input
                        type="number"
                        min="0"
                        value={form.points_win}
                        onChange={e => setForm({ ...form, points_win: parseInt(e.target.value, 10) || 0 })}
                        className="bg-zinc-900 border-white/10 text-white mt-1"
                      />
                    </div>
                    <div>
                      <Label className="text-zinc-400 text-sm">Punkte Unentschieden</Label>
                      <Input
                        type="number"
                        min="0"
                        value={form.points_draw}
                        onChange={e => setForm({ ...form, points_draw: parseInt(e.target.value, 10) || 0 })}
                        className="bg-zinc-900 border-white/10 text-white mt-1"
                      />
                    </div>
                    <div>
                      <Label className="text-zinc-400 text-sm">Punkte Niederlage</Label>
                      <Input
                        type="number"
                        min="0"
                        value={form.points_loss}
                        onChange={e => setForm({ ...form, points_loss: parseInt(e.target.value, 10) || 0 })}
                        className="bg-zinc-900 border-white/10 text-white mt-1"
                      />
                    </div>
                    <div className="sm:col-span-1">
                      <Label className="text-zinc-400 text-sm">Tie-Break Reihenfolge</Label>
                      <Input
                        value={form.tiebreakers}
                        onChange={e => setForm({ ...form, tiebreakers: e.target.value })}
                        placeholder="points,score_diff,score_for,team_name"
                        className="bg-zinc-900 border-white/10 text-white mt-1"
                      />
                    </div>
                  </div>
                  <p className="text-[11px] text-zinc-600 mt-2">
                    Erlaubte Werte: points, score_diff, score_for, wins, draws, losses, played, team_name
                  </p>
                </div>
              )}
            </div>

            {/* Pricing */}
            <div className="glass rounded-xl p-6 border border-white/5 space-y-4">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase tracking-wider">Preise & Gebühren</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <div>
                  <Label className="text-zinc-400 text-sm">Startgebühr (USD)</Label>
                  <Input
                    data-testid="entry-fee-input"
                    type="number"
                    min="0"
                    step="0.01"
                    value={form.entry_fee}
                    onChange={e => setForm({ ...form, entry_fee: parseFloat(e.target.value) || 0 })}
                    placeholder="0 = Kostenlos"
                    className="bg-zinc-900 border-white/10 text-white mt-1"
                  />
                </div>
                <div>
                  <Label className="text-zinc-400 text-sm">Preisgeld</Label>
                  <Input
                    data-testid="prize-pool-input"
                    value={form.prize_pool}
                    onChange={e => setForm({ ...form, prize_pool: e.target.value })}
                    placeholder="z.B. $500 + Trophäe"
                    className="bg-zinc-900 border-white/10 text-white mt-1"
                  />
                </div>
              </div>
            </div>

            {/* Rules */}
            <div className="glass rounded-xl p-6 border border-white/5 space-y-4">
              <h2 className="font-['Barlow_Condensed'] text-lg font-bold text-white uppercase tracking-wider">Regeln</h2>
              <Textarea
                data-testid="rules-input"
                value={form.rules}
                onChange={e => setForm({ ...form, rules: e.target.value })}
                placeholder="Turnierregeln eingeben... (Markdown unterstützt: # Überschrift, - Liste, **fett**)"
                className="bg-zinc-900 border-white/10 text-white min-h-[120px]"
              />
            </div>

            <Button
              data-testid="create-tournament-submit"
              onClick={handleSubmit}
              disabled={submitting}
              className="w-full bg-yellow-500 text-black hover:bg-yellow-400 h-12 text-base font-bold uppercase tracking-wide active:scale-95 transition-transform"
            >
              {submitting ? "Wird erstellt..." : "Turnier erstellen"}
            </Button>
          </div>
        </motion.div>
      </div>
      )}
    </div>
  );
}

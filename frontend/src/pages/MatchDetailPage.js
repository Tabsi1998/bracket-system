import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { toast } from "sonner";
import { Calendar, Clock, MessageSquare, Settings2, Trophy } from "lucide-react";
import CommentSection from "@/components/CommentSection";
import { useAuth } from "@/context/AuthContext";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

const safePrettyJson = (value) => {
  try {
    return JSON.stringify(value || {}, null, 2);
  } catch {
    return "{}";
  }
};

export default function MatchDetailPage() {
  const { id, matchId } = useParams();
  const { user, isAdmin } = useAuth();
  const [loading, setLoading] = useState(true);
  const [matchData, setMatchData] = useState(null);
  const [scheduleItems, setScheduleItems] = useState([]);
  const [setupState, setSetupState] = useState(null);
  const [template, setTemplate] = useState({});
  const [proposalTime, setProposalTime] = useState("");
  const [setupJson, setSetupJson] = useState("{}");
  const [setupNote, setSetupNote] = useState("");
  const [resolveJson, setResolveJson] = useState("{}");
  const [resolveNote, setResolveNote] = useState("");
  const [scoreForm, setScoreForm] = useState({ score1: 0, score2: 0 });
  const [mapVetoState, setMapVetoState] = useState(null);
  const [mapVetoLoading, setMapVetoLoading] = useState(false);

  const fetchMapVeto = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/matches/${matchId}/map-veto`);
      setMapVetoState(res.data);
    } catch {
      setMapVetoState(null);
    }
  }, [matchId]);

  const fetchData = useCallback(async () => {
    try {
      const [detailRes, scheduleRes, setupRes] = await Promise.all([
        axios.get(`${API}/matches/${matchId}`),
        axios.get(`${API}/matches/${matchId}/schedule`),
        axios.get(`${API}/matches/${matchId}/setup`),
      ]);
      setMatchData(detailRes.data);
      setScheduleItems(Array.isArray(scheduleRes.data) ? scheduleRes.data : []);
      const setupPayload = (setupRes.data || {}).setup || null;
      const setupTemplate = (setupRes.data || {}).template || {};
      setSetupState(setupPayload);
      setTemplate(setupTemplate);
      const effectiveSetup = setupPayload?.final_setup && Object.keys(setupPayload?.final_setup || {}).length
        ? setupPayload.final_setup
        : setupTemplate;
      const jsonString = safePrettyJson(effectiveSetup);
      setSetupJson(jsonString);
      setResolveJson(jsonString);

      const match = (detailRes.data || {}).match || {};
      setScoreForm({
        score1: Number(match.score1 || 0),
        score2: Number(match.score2 || 0),
      });
      
      // Fetch map veto state
      fetchMapVeto();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Match konnte nicht geladen werden");
    } finally {
      setLoading(false);
    }
  }, [matchId, fetchMapVeto]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleMapVetoAction = async (action, mapId) => {
    setMapVetoLoading(true);
    try {
      const res = await axios.post(`${API}/matches/${matchId}/map-veto`, {
        action,
        map_id: mapId,
      });
      setMapVetoState(res.data);
      toast.success(`Map ${action === "ban" ? "gebannt" : "gepickt"}: ${mapId}`);
    } catch (e) {
      toast.error(e.response?.data?.detail || "Aktion fehlgeschlagen");
    } finally {
      setMapVetoLoading(false);
    }
  };

  const parsedSetup = useMemo(() => {
    try {
      return JSON.parse(setupJson || "{}");
    } catch {
      return null;
    }
  }, [setupJson]);

  const parsedResolve = useMemo(() => {
    try {
      return JSON.parse(resolveJson || "{}");
    } catch {
      return null;
    }
  }, [resolveJson]);

  const submitScheduleProposal = async () => {
    if (!proposalTime) {
      toast.error("Bitte Termin auswählen");
      return;
    }
    try {
      const iso = new Date(proposalTime).toISOString();
      await axios.post(`${API}/matches/${matchId}/schedule`, { proposed_time: iso });
      toast.success("Zeitvorschlag gespeichert");
      setProposalTime("");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Zeitvorschlag fehlgeschlagen");
    }
  };

  const acceptProposal = async (proposalId) => {
    try {
      await axios.put(`${API}/matches/${matchId}/schedule/${proposalId}/accept`);
      toast.success("Termin bestätigt");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Termin konnte nicht bestätigt werden");
    }
  };

  const submitSetup = async () => {
    if (!parsedSetup || typeof parsedSetup !== "object" || Array.isArray(parsedSetup)) {
      toast.error("Setup JSON ist ungültig");
      return;
    }
    try {
      await axios.post(`${API}/matches/${matchId}/setup`, { settings: parsedSetup, note: setupNote });
      toast.success("Match-Setup eingereicht");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Setup konnte nicht eingereicht werden");
    }
  };

  const resolveSetup = async () => {
    if (!parsedResolve || typeof parsedResolve !== "object" || Array.isArray(parsedResolve)) {
      toast.error("Resolve JSON ist ungültig");
      return;
    }
    try {
      await axios.put(`${API}/matches/${matchId}/setup/resolve`, { settings: parsedResolve, note: resolveNote });
      toast.success("Setup durch Admin freigegeben");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Setup Resolve fehlgeschlagen");
    }
  };

  const submitScore = async () => {
    try {
      if (isAdmin) {
        await axios.put(`${API}/tournaments/${id}/matches/${matchId}/score`, scoreForm);
      } else {
        await axios.post(`${API}/tournaments/${id}/matches/${matchId}/submit-score`, scoreForm);
      }
      toast.success("Ergebnis gespeichert");
      fetchData();
    } catch (e) {
      toast.error(e.response?.data?.detail || "Ergebnis konnte nicht gespeichert werden");
    }
  };

  if (loading) {
    return (
      <div className="pt-20 min-h-screen flex items-center justify-center">
        <div className="w-8 h-8 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!matchData) {
    return (
      <div className="pt-20 min-h-screen flex items-center justify-center text-zinc-500">
        Match nicht gefunden
      </div>
    );
  }

  const match = matchData.match || {};
  const tournament = matchData.tournament || {};
  const context = matchData.context || {};
  const viewer = matchData.viewer || {};
  const schedule = matchData.schedule || {};
  const setupStatus = setupState?.status || "pending";
  const canEditSetup = Boolean(user && (viewer.side === "team1" || viewer.side === "team2"));
  const canScore = Boolean(user && match.status !== "completed" && !match.participants);

  return (
    <div className="pt-20 min-h-screen">
      <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-6">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs text-zinc-500 uppercase">Match Hub</p>
            <h1 className="font-['Barlow_Condensed'] text-3xl font-bold text-white uppercase tracking-tight">
              {match.team1_name || "TBD"} vs {match.team2_name || "TBD"}
            </h1>
            <p className="text-sm text-zinc-400 mt-1">{tournament.name}</p>
            <p className="text-xs text-zinc-500 mt-1">
              {match.round_name || context.round_name || `Runde ${match.round || "-"}`}
              {match.matchday ? ` | Spieltag ${match.matchday}` : ""}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Badge className="bg-zinc-900 border border-white/10 text-zinc-300 text-xs">{match.status || "pending"}</Badge>
            <Link to={`/tournaments/${id}`}>
              <Button variant="outline" className="border-white/20 text-zinc-200 hover:bg-white/5">Zurück zum Turnier</Button>
            </Link>
          </div>
        </div>

        <div className="grid lg:grid-cols-2 gap-6">
          <div className="glass rounded-xl border border-white/5 p-5 space-y-4">
            <h2 className="font-['Barlow_Condensed'] text-xl text-white uppercase flex items-center gap-2">
              <Calendar className="w-4 h-4 text-yellow-500" />Terminabstimmung
            </h2>
            <div className="text-sm text-zinc-400">
              Geplanter Termin: {schedule.scheduled_for ? new Date(schedule.scheduled_for).toLocaleString("de-DE") : "Noch offen"}
            </div>
            {(schedule.window_start || schedule.window_end) && (
              <div className="text-xs text-zinc-500">
                Spieltagsfenster: {schedule.window_start ? new Date(schedule.window_start).toLocaleDateString("de-DE") : "?"}
                {" - "}
                {schedule.window_end ? new Date(schedule.window_end).toLocaleDateString("de-DE") : "?"}
              </div>
            )}
            {!schedule.scheduled_for && (
              <div className="text-xs text-amber-400">
                Termin ist noch offen. Bitte im Team abstimmen und Vorschlag akzeptieren.
              </div>
            )}
            <div className="flex gap-2">
              <Input
                type="datetime-local"
                value={proposalTime}
                onChange={(e) => setProposalTime(e.target.value)}
                className="bg-zinc-900 border-white/10 text-white"
              />
              <Button className="bg-yellow-500 text-black hover:bg-yellow-400" onClick={submitScheduleProposal}>
                Vorschlagen
              </Button>
            </div>
            <div className="space-y-2 max-h-56 overflow-y-auto">
              {scheduleItems.map((s) => (
                <div key={s.id} className="rounded-lg border border-white/5 p-3 bg-zinc-900/40">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm text-zinc-300 flex items-center gap-2">
                      <Clock className="w-3 h-3 text-yellow-500" />
                      {s.proposed_time ? new Date(s.proposed_time).toLocaleString("de-DE") : "-"}
                    </div>
                    <Badge className="text-[10px] bg-zinc-800 text-zinc-300">{s.status}</Badge>
                  </div>
                  <div className="text-xs text-zinc-600 mt-1">von {s.proposed_by_name || "Unbekannt"}</div>
                  {s.status === "pending" && (
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 border-yellow-500/30 text-yellow-500 hover:bg-yellow-500/10"
                      onClick={() => acceptProposal(s.id)}
                    >
                      Termin akzeptieren
                    </Button>
                  )}
                </div>
              ))}
              {scheduleItems.length === 0 && <p className="text-xs text-zinc-600">Noch keine Vorschläge</p>}
            </div>
          </div>

          <div className="glass rounded-xl border border-white/5 p-5 space-y-4">
            <h2 className="font-['Barlow_Condensed'] text-xl text-white uppercase flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-cyan-400" />Map Veto
            </h2>
            {mapVetoState?.map_pool?.length > 0 ? (
              <>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-zinc-400">Status:</span>
                  <Badge className={mapVetoState?.status === "completed" ? "bg-green-500/10 text-green-400" : mapVetoState?.status === "in_progress" ? "bg-blue-500/10 text-blue-400" : "bg-amber-500/10 text-amber-400"}>
                    {mapVetoState?.status === "completed" ? "Abgeschlossen" : mapVetoState?.status === "in_progress" ? "Läuft" : "Ausstehend"}
                  </Badge>
                </div>
                
                {mapVetoState?.status !== "completed" && (
                  <div className="p-3 rounded-lg bg-zinc-900/50 border border-white/5">
                    <p className="text-xs text-zinc-400 mb-2">
                      Aktueller Zug: <span className="text-white font-semibold">{mapVetoState?.current_turn === "team1" ? mapVetoState?.team1_name : mapVetoState?.team2_name}</span>
                    </p>
                    <p className="text-xs text-zinc-500">
                      Aktion: <span className={mapVetoState?.current_action === "ban" ? "text-red-400" : "text-green-400"}>
                        {mapVetoState?.current_action === "ban" ? "Map bannen" : "Map picken"}
                      </span>
                    </p>
                  </div>
                )}
                
                <div className="space-y-2">
                  <p className="text-xs text-zinc-500 uppercase tracking-wider">Map-Pool</p>
                  <div className="grid grid-cols-2 gap-2">
                    {mapVetoState?.map_pool?.map((mapId) => {
                      const isBanned = mapVetoState?.banned_maps?.includes(mapId);
                      const isPicked = mapVetoState?.picked_maps?.includes(mapId);
                      const isAvailable = !isBanned && !isPicked;
                      
                      return (
                        <div
                          key={mapId}
                          className={`rounded-lg p-3 border transition-all ${
                            isBanned ? "bg-red-500/5 border-red-500/20 opacity-50" :
                            isPicked ? "bg-green-500/10 border-green-500/30" :
                            "bg-zinc-900/50 border-white/5 hover:border-yellow-500/30"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className={`text-sm ${isBanned ? "line-through text-zinc-600" : isPicked ? "text-green-400 font-semibold" : "text-white"}`}>
                              {mapId.split("-").pop()?.replace(/_/g, " ") || mapId}
                            </span>
                            {isBanned && <Badge className="text-[9px] bg-red-500/10 text-red-400">Gebannt</Badge>}
                            {isPicked && <Badge className="text-[9px] bg-green-500/10 text-green-400">Gepickt</Badge>}
                          </div>
                          {isAvailable && mapVetoState?.status !== "completed" && (
                            <div className="flex gap-1 mt-2">
                              {mapVetoState?.current_action === "ban" && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="text-[10px] h-6 border-red-500/30 text-red-400 hover:bg-red-500/10"
                                  onClick={() => handleMapVetoAction("ban", mapId)}
                                  disabled={mapVetoLoading}
                                >
                                  Bannen
                                </Button>
                              )}
                              {mapVetoState?.current_action === "pick" && (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  className="text-[10px] h-6 border-green-500/30 text-green-400 hover:bg-green-500/10"
                                  onClick={() => handleMapVetoAction("pick", mapId)}
                                  disabled={mapVetoLoading}
                                >
                                  Picken
                                </Button>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
                
                {mapVetoState?.picked_maps?.length > 0 && (
                  <div className="border-t border-white/5 pt-3">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Ausgewählte Maps</p>
                    <div className="flex gap-2 flex-wrap">
                      {mapVetoState.picked_maps.map((mapId, idx) => (
                        <Badge key={mapId} className="bg-green-500/10 text-green-400 border border-green-500/20">
                          Map {idx + 1}: {mapId.split("-").pop()?.replace(/_/g, " ") || mapId}
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
                
                {mapVetoState?.history?.length > 0 && (
                  <div className="border-t border-white/5 pt-3">
                    <p className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Veto-Verlauf</p>
                    <div className="space-y-1 max-h-32 overflow-y-auto">
                      {mapVetoState.history.map((entry, idx) => (
                        <div key={idx} className="text-[11px] text-zinc-500">
                          <span className="text-zinc-400">{entry.user_name || entry.team}</span>
                          {" "}
                          <span className={entry.action === "ban" ? "text-red-400" : "text-green-400"}>
                            {entry.action === "ban" ? "bannte" : "pickte"}
                          </span>
                          {" "}
                          <span className="text-white">{entry.map_id.split("-").pop() || entry.map_id}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="text-sm text-zinc-500">Kein Map-Pool für dieses Turnier definiert.</p>
            )}
          </div>

          <div className="glass rounded-xl border border-white/5 p-5 space-y-4">
            <h2 className="font-['Barlow_Condensed'] text-xl text-white uppercase flex items-center gap-2">
              <Settings2 className="w-4 h-4 text-yellow-500" />Match Setup
            </h2>
            <div className="text-sm text-zinc-400">
              Status: <span className="text-white">{setupStatus}</span>
            </div>
            <div>
              <Label className="text-zinc-400 text-xs">Template / Setup (JSON)</Label>
              <Textarea
                value={setupJson}
                onChange={(e) => setSetupJson(e.target.value)}
                className="bg-zinc-900 border-white/10 text-white min-h-[180px] font-mono text-xs mt-1"
              />
              {!parsedSetup && <p className="text-[11px] text-red-400 mt-1">Ungültiges JSON</p>}
            </div>
            <div>
              <Label className="text-zinc-400 text-xs">Notiz</Label>
              <Input
                value={setupNote}
                onChange={(e) => setSetupNote(e.target.value)}
                className="bg-zinc-900 border-white/10 text-white mt-1"
                placeholder="Optional"
              />
            </div>
            {canEditSetup && (
              <Button className="bg-yellow-500 text-black hover:bg-yellow-400" onClick={submitSetup}>
                Setup einreichen
              </Button>
            )}
            {isAdmin && (
              <div className="border-t border-white/5 pt-4 space-y-2">
                <Label className="text-zinc-400 text-xs">Admin Resolve JSON</Label>
                <Textarea
                  value={resolveJson}
                  onChange={(e) => setResolveJson(e.target.value)}
                  className="bg-zinc-900 border-white/10 text-white min-h-[140px] font-mono text-xs"
                />
                <Input
                  value={resolveNote}
                  onChange={(e) => setResolveNote(e.target.value)}
                  className="bg-zinc-900 border-white/10 text-white"
                  placeholder="Admin Notiz"
                />
                <Button variant="outline" className="border-cyan-500/30 text-cyan-400 hover:bg-cyan-500/10" onClick={resolveSetup}>
                  Setup finalisieren (Admin)
                </Button>
              </div>
            )}
            <div className="text-[11px] text-zinc-600">
              Template Keys: {Object.keys(template || {}).length ? Object.keys(template || {}).join(", ") : "Keine vordefinierten Keys"}
            </div>
          </div>
        </div>

        <div className="glass rounded-xl border border-white/5 p-5 space-y-4">
          <h2 className="font-['Barlow_Condensed'] text-xl text-white uppercase flex items-center gap-2">
            <Trophy className="w-4 h-4 text-yellow-500" />Ergebnis
          </h2>
          <div className="grid sm:grid-cols-[1fr_auto_1fr_auto] gap-3 items-end">
            <div>
              <Label className="text-zinc-400 text-xs">{match.team1_name || "Team 1"}</Label>
              <Input
                type="number"
                min="0"
                value={scoreForm.score1}
                onChange={(e) => setScoreForm((prev) => ({ ...prev, score1: parseInt(e.target.value, 10) || 0 }))}
                className="bg-zinc-900 border-white/10 text-white mt-1"
              />
            </div>
            <div className="text-zinc-500 text-sm pb-2">vs</div>
            <div>
              <Label className="text-zinc-400 text-xs">{match.team2_name || "Team 2"}</Label>
              <Input
                type="number"
                min="0"
                value={scoreForm.score2}
                onChange={(e) => setScoreForm((prev) => ({ ...prev, score2: parseInt(e.target.value, 10) || 0 }))}
                className="bg-zinc-900 border-white/10 text-white mt-1"
              />
            </div>
            <Button
              disabled={!canScore}
              className="bg-yellow-500 text-black hover:bg-yellow-400 disabled:opacity-50"
              onClick={submitScore}
            >
              Speichern
            </Button>
          </div>
          {!canScore && <p className="text-xs text-zinc-600">Ergebnis ist bereits abgeschlossen oder für diesen Match-Typ nicht editierbar.</p>}
        </div>

        <div className="glass rounded-xl border border-white/5 p-5">
          <h2 className="font-['Barlow_Condensed'] text-xl text-white uppercase flex items-center gap-2 mb-4">
            <MessageSquare className="w-4 h-4 text-yellow-500" />Match Kommentare
          </h2>
          <CommentSection targetType="match" targetId={matchId} />
        </div>
      </div>
    </div>
  );
}

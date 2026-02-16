import { useState, useEffect } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Trophy, Users, Zap, CalendarRange } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;
const ALLOWED_VIEWS = ["bracket", "standings", "matchdays"];

const statusLabels = { registration: "Registrierung", checkin: "Check-in", live: "LIVE", completed: "Abgeschlossen" };

function WidgetBracket({ bracket }) {
  if (!bracket || !bracket.rounds) return null;
  return (
    <div className="overflow-x-auto pb-2">
      <div className="flex gap-6 min-w-max">
        {bracket.rounds.map(round => (
          <div key={round.round} className="min-w-[180px]">
            <div className="text-xs text-zinc-500 text-center mb-2 font-mono">{round.name}</div>
            <div className="space-y-2">
              {round.matches.map(m => (
                <div key={m.id} className="rounded border border-zinc-700 overflow-hidden text-xs">
                  <div className={`flex justify-between px-2 py-1 ${m.winner_id === m.team1_id ? "bg-yellow-500/10 text-yellow-400 font-bold" : "bg-zinc-900 text-zinc-300"}`}>
                    <span className="truncate">{m.team1_name}</span><span className="font-mono">{m.score1}</span>
                  </div>
                  <div className="h-px bg-zinc-800" />
                  <div className={`flex justify-between px-2 py-1 ${m.winner_id === m.team2_id ? "bg-yellow-500/10 text-yellow-400 font-bold" : "bg-zinc-900 text-zinc-300"}`}>
                    <span className="truncate">{m.team2_name}</span><span className="font-mono">{m.score2}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StandingsTable({ rows }) {
  if (!rows?.length) return <p className="text-xs text-zinc-600">Keine Tabellenwerte vorhanden.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="text-zinc-500 border-b border-zinc-800">
            <th className="text-left py-2 px-2">#</th>
            <th className="text-left py-2 px-2">Team</th>
            <th className="text-right py-2 px-2">Sp</th>
            <th className="text-right py-2 px-2">S</th>
            <th className="text-right py-2 px-2">U</th>
            <th className="text-right py-2 px-2">N</th>
            <th className="text-right py-2 px-2">Pkt</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.registration_id}-${row.rank}`} className="border-b border-zinc-900 text-zinc-300">
              <td className="py-2 px-2">{row.rank}</td>
              <td className="py-2 px-2">{row.team_name}</td>
              <td className="py-2 px-2 text-right">{row.played}</td>
              <td className="py-2 px-2 text-right">{row.wins}</td>
              <td className="py-2 px-2 text-right">{row.draws}</td>
              <td className="py-2 px-2 text-right">{row.losses}</td>
              <td className="py-2 px-2 text-right font-semibold text-yellow-500">{row.points}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function WidgetPage() {
  const { tournamentId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const view = ALLOWED_VIEWS.includes((searchParams.get("view") || "").toLowerCase())
    ? (searchParams.get("view") || "").toLowerCase()
    : "bracket";
  const activeMatchday = parseInt(searchParams.get("matchday") || "0", 10) || null;

  useEffect(() => {
    const params = new URLSearchParams();
    params.set("view", view);
    if (view === "matchdays" && activeMatchday) {
      params.set("matchday", String(activeMatchday));
    }
    setLoading(true);
    axios
      .get(`${API}/widget/tournament/${tournamentId}?${params.toString()}`)
      .then((r) => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [tournamentId, view, activeMatchday]);

  const switchView = (nextView) => {
    const params = new URLSearchParams(searchParams);
    params.set("view", nextView);
    if (nextView !== "matchdays") {
      params.delete("matchday");
    } else if (!params.get("matchday")) {
      params.set("matchday", "1");
    }
    setSearchParams(params, { replace: true });
  };

  const switchMatchday = (day) => {
    const params = new URLSearchParams(searchParams);
    params.set("view", "matchdays");
    params.set("matchday", String(day));
    setSearchParams(params, { replace: true });
  };

  if (loading) return (
    <div className="flex items-center justify-center h-screen bg-[#050505]">
      <div className="w-6 h-6 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
  if (!data) {
    return (
      <div className="flex items-center justify-center h-screen bg-[#050505] text-zinc-500 text-sm">
        Widget konnte nicht geladen werden
      </div>
    );
  }

  const { tournament: t, registrations } = data;
  const matchdays = data.matchdays || [];
  const selectedMatchday = data.selected_matchday || (activeMatchday ? matchdays.find((d) => d.matchday === activeMatchday) : null);
  const shownMatchday = selectedMatchday || matchdays[0];

  return (
    <div data-testid="widget-page" className="bg-[#050505] text-white p-4 min-h-screen font-sans">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="font-['Barlow_Condensed'] text-xl font-bold uppercase tracking-tight">{t.name}</h2>
          <div className="flex items-center gap-2 text-xs text-zinc-500 mt-1">
            <Zap className="w-3 h-3 text-yellow-500" />{t.game_name} - {t.game_mode}
            <span className="flex items-center gap-1"><Users className="w-3 h-3" />{registrations.length}/{t.max_participants}</span>
          </div>
        </div>
        <Badge className={`text-xs border ${t.status === "live" ? "bg-red-500/10 text-red-400 border-red-500/20" : "bg-blue-500/10 text-blue-400 border-blue-500/20"}`}>
          {statusLabels[t.status] || t.status}
        </Badge>
      </div>

      <div className="flex items-center gap-2 mb-3">
        {ALLOWED_VIEWS.map((viewKey) => (
          <button
            key={viewKey}
            onClick={() => switchView(viewKey)}
            className={`px-2.5 py-1 text-[11px] rounded border transition ${
              view === viewKey
                ? "border-yellow-500/40 text-yellow-500 bg-yellow-500/10"
                : "border-zinc-700 text-zinc-400 hover:border-zinc-500"
            }`}
          >
            {viewKey}
          </button>
        ))}
      </div>

      {view === "bracket" && (
        t.bracket ? (
          <WidgetBracket bracket={t.bracket.type === "double_elimination" ? t.bracket.winners_bracket : t.bracket} />
        ) : (
          <div className="text-center py-8">
            <Trophy className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
            <p className="text-xs text-zinc-600">Bracket noch nicht generiert</p>
          </div>
        )
      )}

      {view === "standings" && (
        <div className="space-y-3">
          {data.standings?.type === "group_stage" || data.standings?.type === "group_playoffs" ? (
            (data.standings?.groups || []).map((group) => (
              <div key={group.id} className="rounded border border-zinc-800 p-2">
                <div className="text-xs text-cyan-400 mb-2">{group.name}</div>
                <StandingsTable rows={group.standings || []} />
              </div>
            ))
          ) : (
            <StandingsTable rows={data.standings?.standings || []} />
          )}
          {data.standings_error && (
            <p className="text-xs text-red-400">{data.standings_error}</p>
          )}
        </div>
      )}

      {view === "matchdays" && (
        <div className="space-y-3">
          {matchdays.length > 0 ? (
            <>
              <div className="flex gap-1 overflow-x-auto pb-1">
                {matchdays.map((day) => (
                  <button
                    key={`day-${day.matchday}`}
                    onClick={() => switchMatchday(day.matchday)}
                    className={`text-[11px] px-2 py-1 rounded border transition ${
                      shownMatchday?.matchday === day.matchday
                        ? "border-yellow-500/40 text-yellow-500 bg-yellow-500/10"
                        : "border-zinc-700 text-zinc-400"
                    }`}
                  >
                    ST {day.matchday}
                  </button>
                ))}
              </div>
              {shownMatchday && (
                <div className="rounded border border-zinc-800 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs text-white font-semibold">{shownMatchday.name}</div>
                    <div className="text-[10px] text-zinc-500 flex items-center gap-1">
                      <CalendarRange className="w-3 h-3" />
                      {shownMatchday.window_start ? new Date(shownMatchday.window_start).toLocaleDateString("de-DE") : "-"} - {shownMatchday.window_end ? new Date(shownMatchday.window_end).toLocaleDateString("de-DE") : "-"}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    {(shownMatchday.matches || []).map((m) => (
                      <div key={m.id} className="text-xs rounded bg-zinc-900/70 border border-zinc-800 px-2 py-1.5 flex items-center justify-between gap-2">
                        <span className="text-zinc-300 truncate">{m.team1_name} vs {m.team2_name}</span>
                        <span className="text-zinc-500 font-mono">{m.score1}:{m.score2}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <p className="text-xs text-zinc-600">Keine Spieltage verfügbar.</p>
          )}
        </div>
      )}

      {/* Participants */}
      {!t.bracket && registrations.length > 0 && view === "bracket" && (
        <div className="mt-4">
          <h3 className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Teilnehmer</h3>
          <div className="grid grid-cols-2 gap-1">
            {registrations.map((r, i) => (
              <div key={r.id} className="text-xs text-zinc-400 bg-zinc-900/50 rounded px-2 py-1">
                <span className="text-zinc-600 font-mono mr-1">{i + 1}.</span>{r.team_name}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="mt-4 pt-3 border-t border-zinc-800 text-center">
        <span className="text-[10px] text-zinc-700 font-mono">Powered by ARENA eSports</span>
      </div>
    </div>
  );
}

import { useState, useEffect } from "react";
import { useParams } from "react-router-dom";
import { Badge } from "@/components/ui/badge";
import { Trophy, Users, Zap } from "lucide-react";
import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL || ""}/api`;

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

export default function WidgetPage() {
  const { tournamentId } = useParams();
  const [data, setData] = useState(null);

  useEffect(() => {
    axios.get(`${API}/widget/tournament/${tournamentId}`).then(r => setData(r.data)).catch(() => {});
  }, [tournamentId]);

  if (!data) return (
    <div className="flex items-center justify-center h-screen bg-[#050505]">
      <div className="w-6 h-6 border-2 border-yellow-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );

  const { tournament: t, registrations } = data;

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

      {/* Bracket */}
      {t.bracket ? (
        <WidgetBracket bracket={t.bracket.type === "double_elimination" ? t.bracket.winners_bracket : t.bracket} />
      ) : (
        <div className="text-center py-8">
          <Trophy className="w-8 h-8 text-zinc-700 mx-auto mb-2" />
          <p className="text-xs text-zinc-600">Bracket noch nicht generiert</p>
        </div>
      )}

      {/* Participants */}
      {!t.bracket && registrations.length > 0 && (
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

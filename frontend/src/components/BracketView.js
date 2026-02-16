import { motion } from "framer-motion";

const MatchNode = ({ match }) => {
  const isCompleted = match.status === "completed";
  const isTeam1Winner = match.winner_id && match.winner_id === match.team1_id;
  const isTeam2Winner = match.winner_id && match.winner_id === match.team2_id;
  const isBye = match.team1_name === "BYE" || match.team2_name === "BYE";
  const isDisqualified = match.disqualified;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 300, damping: 30 }}
      data-testid={`match-node-${match.id}`}
      className={`w-52 rounded-lg overflow-hidden border transition-all duration-300 ${
        isCompleted ? "border-zinc-700" : "border-white/10 hover:border-yellow-500/40"
      } ${isBye ? "opacity-50" : ""}`}
    >
      <div className={`flex items-center justify-between px-3 py-2 text-sm ${
        isTeam1Winner ? "bg-yellow-500/10 border-l-2 border-l-yellow-500" :
        isDisqualified === match.team1_id ? "bg-red-500/5 border-l-2 border-l-red-500" :
        "bg-zinc-900 border-l-2 border-l-transparent"
      }`}>
        <span className="truncate flex-1 flex items-center gap-2">
          {match.team1_logo_url ? (
            <img src={match.team1_logo_url} alt="" className="w-4 h-4 rounded object-cover border border-white/10" />
          ) : null}
          <span className={`truncate ${
            isTeam1Winner ? "text-yellow-500 font-bold" :
            isDisqualified === match.team1_id ? "text-red-500 line-through" :
            match.team1_name === "TBD" || match.team1_name === "BYE" ? "text-zinc-600 italic" : "text-white"
          }`}>
            {match.team1_name}{match.team1_tag ? ` [${match.team1_tag}]` : ""}
          </span>
        </span>
        <span className={`font-mono text-xs w-6 text-center ${isTeam1Winner ? "text-yellow-500 font-bold" : "text-zinc-500"}`}>
          {match.team1_name !== "BYE" && match.team1_name !== "TBD" ? match.score1 : "-"}
        </span>
      </div>
      <div className="h-px bg-zinc-800" />
      <div className={`flex items-center justify-between px-3 py-2 text-sm ${
        isTeam2Winner ? "bg-yellow-500/10 border-l-2 border-l-yellow-500" :
        isDisqualified === match.team2_id ? "bg-red-500/5 border-l-2 border-l-red-500" :
        "bg-zinc-900 border-l-2 border-l-transparent"
      }`}>
        <span className="truncate flex-1 flex items-center gap-2">
          {match.team2_logo_url ? (
            <img src={match.team2_logo_url} alt="" className="w-4 h-4 rounded object-cover border border-white/10" />
          ) : null}
          <span className={`truncate ${
            isTeam2Winner ? "text-yellow-500 font-bold" :
            isDisqualified === match.team2_id ? "text-red-500 line-through" :
            match.team2_name === "TBD" || match.team2_name === "BYE" ? "text-zinc-600 italic" : "text-white"
          }`}>
            {match.team2_name}{match.team2_tag ? ` [${match.team2_tag}]` : ""}
          </span>
        </span>
        <span className={`font-mono text-xs w-6 text-center ${isTeam2Winner ? "text-yellow-500 font-bold" : "text-zinc-500"}`}>
          {match.team2_name !== "BYE" && match.team2_name !== "TBD" ? match.score2 : "-"}
        </span>
      </div>
    </motion.div>
  );
};

const BezierConnectors = ({ roundIndex, matchCount, nextMatchCount, containerHeight }) => {
  if (nextMatchCount === 0 || matchCount < 2) return null;
  const paths = [];
  const w = 48;
  const step = containerHeight / matchCount;
  const nextStep = containerHeight / nextMatchCount;

  for (let i = 0; i < matchCount; i += 2) {
    if (i + 1 >= matchCount) break;
    const y1 = step * i + step / 2;
    const y2 = step * (i + 1) + step / 2;
    const nextIdx = Math.floor(i / 2);
    const yTarget = nextStep * nextIdx + nextStep / 2;
    const cp = w * 0.6;

    // Top match to middle
    paths.push(
      <path key={`t-${roundIndex}-${i}`}
        d={`M 0 ${y1} C ${cp} ${y1}, ${w - cp} ${yTarget}, ${w} ${yTarget}`}
        fill="none" stroke="rgba(234,179,8,0.15)" strokeWidth="2" />
    );
    // Bottom match to middle
    paths.push(
      <path key={`b-${roundIndex}-${i}`}
        d={`M 0 ${y2} C ${cp} ${y2}, ${w - cp} ${yTarget}, ${w} ${yTarget}`}
        fill="none" stroke="rgba(234,179,8,0.15)" strokeWidth="2" />
    );
    // Glow dot at junction
    paths.push(
      <circle key={`dot-${roundIndex}-${i}`} cx={w} cy={yTarget} r="2.5" fill="rgba(234,179,8,0.3)" />
    );
  }

  return (
    <svg width={w} height={containerHeight} className="flex-shrink-0" style={{ minHeight: containerHeight }}>
      {paths}
    </svg>
  );
};

export default function BracketView({ bracket }) {
  if (!bracket || !bracket.rounds || bracket.rounds.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-zinc-600">
        <p>Bracket noch nicht generiert</p>
      </div>
    );
  }

  const bracketType = bracket.type || "single_elimination";

  if (bracketType === "round_robin") return <RoundRobinView bracket={bracket} />;
  if (bracketType === "league") return <RoundRobinView bracket={bracket} />;
  if (bracketType === "double_elimination") return <DoubleEliminationView bracket={bracket} />;
  if (bracketType === "group_stage") return <GroupStageView bracket={bracket} />;

  const rounds = bracket.rounds;
  const matchHeight = 56;
  const baseGap = 16;
  const firstRoundH = rounds[0].matches.length * (matchHeight + baseGap) - baseGap;
  const containerHeight = Math.max(firstRoundH, 200);

  return (
    <div data-testid="bracket-view" className="bracket-scroll overflow-x-auto pb-4">
      <div className="flex items-start gap-0 min-w-max">
        {rounds.map((round, roundIdx) => {
          const nextMatchCount = roundIdx < rounds.length - 1 ? rounds[roundIdx + 1].matches.length : 0;

          return (
            <div key={round.round} className="flex items-start">
              <div className="flex flex-col" style={{ minWidth: 220 }}>
                <div className="text-center mb-4">
                  <span className="text-xs text-zinc-500 uppercase tracking-wider font-mono">{round.name}</span>
                </div>
                <div className="flex flex-col justify-around" style={{ minHeight: containerHeight }}>
                  {round.matches.map((match) => (
                    <div key={match.id} className="px-2">
                      <MatchNode match={match} />
                    </div>
                  ))}
                </div>
              </div>
              {roundIdx < rounds.length - 1 && (
                <div className="flex items-center" style={{ minHeight: containerHeight, paddingTop: 32 }}>
                  <BezierConnectors
                    roundIndex={roundIdx}
                    matchCount={round.matches.length}
                    nextMatchCount={nextMatchCount}
                    containerHeight={containerHeight}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DoubleEliminationView({ bracket }) {
  const wb = bracket.winners_bracket;
  const lb = bracket.losers_bracket;
  const gf = bracket.grand_final;

  return (
    <div data-testid="bracket-view-double" className="space-y-8 pb-4">
      <div>
        <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-yellow-500 uppercase mb-4 tracking-wider">
          Winners Bracket
        </h3>
        <BracketView bracket={wb} />
      </div>
      {lb && lb.rounds && lb.rounds.length > 0 && (
        <div>
          <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-cyan-500 uppercase mb-4 tracking-wider">
            Losers Bracket
          </h3>
          <BracketView bracket={lb} />
        </div>
      )}
      {gf && (
        <div>
          <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-purple-500 uppercase mb-4 tracking-wider">
            Grand Final
          </h3>
          <div className="flex justify-center">
            <MatchNode match={gf} />
          </div>
        </div>
      )}
    </div>
  );
}

function RoundRobinView({ bracket }) {
  const allMatches = bracket.rounds?.flatMap(r => r.matches) || [];

  return (
    <div data-testid="bracket-view-rr" className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {allMatches.map(match => (
          <MatchNode key={match.id} match={match} />
        ))}
      </div>
    </div>
  );
}

function GroupStageView({ bracket }) {
  const groups = bracket.groups || [];
  if (groups.length === 0) {
    return (
      <div className="flex items-center justify-center py-12 text-zinc-600">
        <p>Keine Gruppen vorhanden</p>
      </div>
    );
  }
  return (
    <div data-testid="bracket-view-groups" className="space-y-6">
      {groups.map((group) => (
        <div key={group.id} className="rounded-xl border border-white/5 p-4">
          <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-cyan-400 uppercase tracking-wider mb-3">
            {group.name}
          </h3>
          <RoundRobinView bracket={{ type: "round_robin", rounds: group.rounds || [] }} />
        </div>
      ))}
    </div>
  );
}

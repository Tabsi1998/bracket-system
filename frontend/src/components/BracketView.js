import { motion } from "framer-motion";

const MatchNode = ({ match, onScoreUpdate, isAdmin }) => {
  const isCompleted = match.status === "completed";
  const isTeam1Winner = match.winner_id && match.winner_id === match.team1_id;
  const isTeam2Winner = match.winner_id && match.winner_id === match.team2_id;
  const isBye = match.team1_name === "BYE" || match.team2_name === "BYE";

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
      {/* Team 1 */}
      <div
        className={`flex items-center justify-between px-3 py-2 text-sm ${
          isTeam1Winner
            ? "bg-yellow-500/10 border-l-2 border-l-yellow-500"
            : "bg-zinc-900 border-l-2 border-l-transparent"
        }`}
      >
        <span className={`truncate flex-1 ${
          isTeam1Winner ? "text-yellow-500 font-bold" : match.team1_name === "TBD" || match.team1_name === "BYE" ? "text-zinc-600 italic" : "text-white"
        }`}>
          {match.team1_name}
        </span>
        <span className={`font-mono text-xs w-6 text-center ${isTeam1Winner ? "text-yellow-500 font-bold" : "text-zinc-500"}`}>
          {match.team1_name !== "BYE" && match.team1_name !== "TBD" ? match.score1 : "-"}
        </span>
      </div>

      {/* Divider */}
      <div className="h-px bg-zinc-800" />

      {/* Team 2 */}
      <div
        className={`flex items-center justify-between px-3 py-2 text-sm ${
          isTeam2Winner
            ? "bg-yellow-500/10 border-l-2 border-l-yellow-500"
            : "bg-zinc-900 border-l-2 border-l-transparent"
        }`}
      >
        <span className={`truncate flex-1 ${
          isTeam2Winner ? "text-yellow-500 font-bold" : match.team2_name === "TBD" || match.team2_name === "BYE" ? "text-zinc-600 italic" : "text-white"
        }`}>
          {match.team2_name}
        </span>
        <span className={`font-mono text-xs w-6 text-center ${isTeam2Winner ? "text-yellow-500 font-bold" : "text-zinc-500"}`}>
          {match.team2_name !== "BYE" && match.team2_name !== "TBD" ? match.score2 : "-"}
        </span>
      </div>
    </motion.div>
  );
};

const ConnectorLines = ({ roundIndex, matchCount, nextMatchCount, matchHeight, gap }) => {
  if (nextMatchCount === 0) return null;
  const lines = [];
  const totalH = matchCount * (matchHeight + gap) - gap;

  for (let i = 0; i < matchCount; i += 2) {
    if (i + 1 >= matchCount) break;
    const y1 = i * (matchHeight + gap) + matchHeight / 2;
    const y2 = (i + 1) * (matchHeight + gap) + matchHeight / 2;
    const midY = (y1 + y2) / 2;

    lines.push(
      <g key={`conn-${roundIndex}-${i}`}>
        {/* Horizontal from match 1 */}
        <line x1="0" y1={y1} x2="15" y2={y1} stroke="#27272A" strokeWidth="2" />
        {/* Vertical connector */}
        <line x1="15" y1={y1} x2="15" y2={y2} stroke="#27272A" strokeWidth="2" />
        {/* Horizontal from match 2 */}
        <line x1="0" y1={y2} x2="15" y2={y2} stroke="#27272A" strokeWidth="2" />
        {/* Horizontal to next round */}
        <line x1="15" y1={midY} x2="40" y2={midY} stroke="#27272A" strokeWidth="2" />
      </g>
    );
  }

  return (
    <svg
      width="40"
      height={totalH}
      className="flex-shrink-0"
      style={{ minHeight: totalH }}
    >
      {lines}
    </svg>
  );
};

export default function BracketView({ bracket, onScoreUpdate, isAdmin }) {
  if (!bracket || !bracket.rounds || bracket.rounds.length === 0) {
    return (
      <div className="flex items-center justify-center py-16 text-zinc-600">
        <p>Bracket noch nicht generiert</p>
      </div>
    );
  }

  const bracketType = bracket.type || "single_elimination";

  if (bracketType === "round_robin") {
    return <RoundRobinView bracket={bracket} onScoreUpdate={onScoreUpdate} isAdmin={isAdmin} />;
  }

  if (bracketType === "double_elimination") {
    return <DoubleEliminationView bracket={bracket} onScoreUpdate={onScoreUpdate} isAdmin={isAdmin} />;
  }

  // Single Elimination
  const rounds = bracket.rounds;
  const matchHeight = 56;
  const baseGap = 16;

  return (
    <div data-testid="bracket-view" className="bracket-scroll overflow-x-auto pb-4">
      <div className="flex items-start gap-0 min-w-max">
        {rounds.map((round, roundIdx) => {
          const gapMultiplier = Math.pow(2, roundIdx);
          const gap = baseGap * gapMultiplier;
          const totalHeight = round.matches.length * (matchHeight + gap) - gap;
          const nextMatchCount = roundIdx < rounds.length - 1 ? rounds[roundIdx + 1].matches.length : 0;

          return (
            <div key={round.round} className="flex items-start">
              <div className="flex flex-col" style={{ minWidth: 220 }}>
                {/* Round header */}
                <div className="text-center mb-4">
                  <span className="text-xs text-zinc-500 uppercase tracking-wider font-mono">
                    {round.name}
                  </span>
                </div>
                {/* Matches */}
                <div
                  className="flex flex-col justify-around"
                  style={{ minHeight: rounds[0].matches.length * (matchHeight + baseGap) - baseGap }}
                >
                  {round.matches.map((match) => (
                    <div key={match.id} className="px-2">
                      <MatchNode match={match} onScoreUpdate={onScoreUpdate} isAdmin={isAdmin} />
                    </div>
                  ))}
                </div>
              </div>
              {/* Connector */}
              {roundIdx < rounds.length - 1 && (
                <div className="flex items-center" style={{ minHeight: rounds[0].matches.length * (matchHeight + baseGap) - baseGap }}>
                  <div className="flex flex-col justify-around h-full">
                    <ConnectorLines
                      roundIndex={roundIdx}
                      matchCount={round.matches.length}
                      nextMatchCount={nextMatchCount}
                      matchHeight={matchHeight}
                      gap={gap}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function DoubleEliminationView({ bracket, onScoreUpdate, isAdmin }) {
  const wb = bracket.winners_bracket;
  const lb = bracket.losers_bracket;
  const gf = bracket.grand_final;

  return (
    <div data-testid="bracket-view-double" className="space-y-8 pb-4">
      <div>
        <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-yellow-500 uppercase mb-4 tracking-wider">
          Winners Bracket
        </h3>
        <BracketView bracket={wb} onScoreUpdate={onScoreUpdate} isAdmin={isAdmin} />
      </div>
      {lb && lb.rounds && lb.rounds.length > 0 && (
        <div>
          <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-cyan-500 uppercase mb-4 tracking-wider">
            Losers Bracket
          </h3>
          <BracketView bracket={lb} onScoreUpdate={onScoreUpdate} isAdmin={isAdmin} />
        </div>
      )}
      {gf && (
        <div>
          <h3 className="font-['Barlow_Condensed'] text-lg font-bold text-purple-500 uppercase mb-4 tracking-wider">
            Grand Final
          </h3>
          <div className="flex justify-center">
            <MatchNode match={gf} onScoreUpdate={onScoreUpdate} isAdmin={isAdmin} />
          </div>
        </div>
      )}
    </div>
  );
}

function RoundRobinView({ bracket, onScoreUpdate, isAdmin }) {
  const allMatches = bracket.rounds?.flatMap(r => r.matches) || [];

  return (
    <div data-testid="bracket-view-rr" className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {allMatches.map(match => (
          <MatchNode key={match.id} match={match} onScoreUpdate={onScoreUpdate} isAdmin={isAdmin} />
        ))}
      </div>
    </div>
  );
}

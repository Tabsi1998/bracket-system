import { useState } from "react";
import { Server } from "lucide-react";
import { resolveMediaUrl } from "@/lib/api";

export function GameServerIcon({ server }) {
  const [failed, setFailed] = useState([]);
  const candidates = server.show_game_icon === false ? [] : [server.server_icon_url, server.game?.logo_url];
  const icon = candidates.filter(Boolean).map(resolveMediaUrl).find((url) => !failed.includes(url));
  return (
    <div className="w-14 h-14 rounded-sm border border-white/10 bg-black/30 flex items-center justify-center overflow-hidden shrink-0" data-testid="server-game-icon">
      {icon ? <img src={icon} alt={`${server.game?.name || server.game_name || "Server"}-Logo`} loading="lazy" referrerPolicy="no-referrer"
        onError={() => setFailed((current) => [...current, icon])} className="w-full h-full object-contain p-2" />
        : <Server aria-label="Server-Symbol" className="w-6 h-6 text-[#29B6E8]" />}
    </div>
  );
}

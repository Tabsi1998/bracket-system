import { FaDiscord, FaInstagram, FaTwitch, FaYoutube, FaGlobe } from "react-icons/fa";
import { FaXTwitter } from "react-icons/fa6";

const SOCIAL_CONFIG = [
  { key: "discord_url", label: "Discord", icon: FaDiscord, textClass: "text-[#5865F2]", borderClass: "hover:border-[#5865F2]/50" },
  { key: "website_url", label: "Website", icon: FaGlobe, textClass: "text-zinc-300", borderClass: "hover:border-zinc-400/50" },
  { key: "twitter_url", label: "X/Twitter", icon: FaXTwitter, textClass: "text-zinc-200", borderClass: "hover:border-zinc-400/50" },
  { key: "instagram_url", label: "Instagram", icon: FaInstagram, textClass: "text-[#E4405F]", borderClass: "hover:border-[#E4405F]/50" },
  { key: "twitch_url", label: "Twitch", icon: FaTwitch, textClass: "text-[#9146FF]", borderClass: "hover:border-[#9146FF]/50" },
  { key: "youtube_url", label: "YouTube", icon: FaYoutube, textClass: "text-[#FF0000]", borderClass: "hover:border-[#FF0000]/50" },
];

export default function SocialLinks({ entity = {}, compact = false, iconOnly = false }) {
  const items = SOCIAL_CONFIG
    .map((cfg) => ({ ...cfg, url: entity?.[cfg.key] || "" }))
    .filter((item) => item.url);

  if (!items.length) return null;

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <a
            key={`${item.key}-${item.url}`}
            href={item.url}
            target="_blank"
            rel="noreferrer noopener"
            title={item.label}
            className={`inline-flex items-center gap-2 rounded border border-white/10 bg-zinc-900/70 transition-colors ${
              compact ? "px-2 py-1 text-[11px]" : "px-3 py-2 text-xs"
            } ${item.borderClass}`}
          >
            <Icon className={`${compact ? "text-sm" : "text-lg"} ${item.textClass}`} />
            {!iconOnly && <span className="text-zinc-200">{item.label}</span>}
          </a>
        );
      })}
    </div>
  );
}

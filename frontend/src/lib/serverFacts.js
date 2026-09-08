// Die Statusabfrage liefert je Spiel unterschiedliche Zusatzangaben. Statt pro
// Spiel eine Sonderbehandlung zu bauen, werden die Schlüssel übersetzt, die
// tatsächlich etwas aussagen — vorhanden ist eben, was der Server mitschickt.

const RULE_LABELS = {
  // 7 Days To Die
  GameDifficulty: "Schwierigkeit",
  GameMode: "Spielmodus",
  DayCount: "Welttag",
  CurrentServerTime: "Weltzeit",
  ServerMaxPlayerCount: "Maximale Spieler",
  // Rust
  build: "Build",
  "world.size": "Kartengröße",
  "world.seed": "Karten-Seed",
  // ARK und Unreal-Titel
  DayTime_s: "Weltzeit",
  SESSIONISPVE_i: "Modus",
  // Valheim und weitere
  world: "Welt",
};

const VALUE_FORMATTERS = {
  SESSIONISPVE_i: (value) => (String(value) === "1" ? "PvE" : "PvP"),
  "world.size": (value) => `${value}`,
};

const MAX_TAGS = 6;

export function ruleFacts(rules) {
  if (!rules || typeof rules !== "object") return [];
  return Object.entries(RULE_LABELS)
    .filter(([key]) => {
      const value = rules[key];
      return value !== undefined && value !== null && String(value).trim() !== "";
    })
    .map(([key, label]) => {
      const raw = rules[key];
      const format = VALUE_FORMATTERS[key];
      return { label, value: format ? format(raw) : String(raw) };
    });
}

export function serverTags(server) {
  const tags = Array.isArray(server?.server_tags) ? server.server_tags : [];
  return tags.filter((tag) => typeof tag === "string" && tag.trim()).slice(0, MAX_TAGS);
}

export function protectionLabel(server) {
  if (server?.password_protected === true) return "Passwortgeschützt";
  return null;
}

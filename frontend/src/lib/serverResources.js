export const serverResourceLabels = { modloader: "Modloader", modpack: "Modpaket", config: "Konfiguration", guide: "Anleitung" };

export function safeResourceUrl(value) {
  // eslint-disable-next-line no-control-regex -- rejecting control characters is the point here
  if (typeof value !== "string" || /[\s\\\u0000-\u001f]/.test(value)) return "";
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password ? url.href : "";
  } catch { return ""; }
}

import { protectionLabel, ruleFacts, serverTags } from "./serverFacts";

// Die Serverkarte zeigt nur, was der jeweilige Server tatsächlich mitschickt.
// Fehlende Angaben dürfen weder leere Zeilen noch Platzhalter erzeugen.

test("bekannte Regeln werden übersetzt", () => {
  const facts = ruleFacts({ GameDifficulty: "3", DayCount: "42" });

  expect(facts).toEqual([
    { label: "Schwierigkeit", value: "3" },
    { label: "Welttag", value: "42" },
  ]);
});

test("unbekannte Regeln werden nicht angezeigt", () => {
  expect(ruleFacts({ IrgendeinInternerSchluessel: "x" })).toEqual([]);
});

test("leere Werte erzeugen keine Zeile", () => {
  expect(ruleFacts({ GameDifficulty: "", DayCount: "   ", build: null })).toEqual([]);
});

test("PvE-Kennzeichen wird lesbar gemacht", () => {
  expect(ruleFacts({ SESSIONISPVE_i: "1" })).toEqual([{ label: "Modus", value: "PvE" }]);
  expect(ruleFacts({ SESSIONISPVE_i: "0" })).toEqual([{ label: "Modus", value: "PvP" }]);
});

test("fehlende Regeln ergeben eine leere Liste statt eines Fehlers", () => {
  expect(ruleFacts(undefined)).toEqual([]);
  expect(ruleFacts(null)).toEqual([]);
  expect(ruleFacts("kaputt")).toEqual([]);
});

test("Server-Merkmale werden begrenzt, damit die Karte nicht überläuft", () => {
  const tags = serverTags({ server_tags: ["a", "b", "c", "d", "e", "f", "g", "h"] });

  expect(tags).toHaveLength(6);
  expect(tags[0]).toBe("a");
});

test("leere oder fehlende Merkmale ergeben eine leere Liste", () => {
  expect(serverTags({ server_tags: ["", "  "] })).toEqual([]);
  expect(serverTags({})).toEqual([]);
  expect(serverTags(null)).toEqual([]);
});

test("Passwortschutz wird nur bei echtem Kennzeichen gemeldet", () => {
  expect(protectionLabel({ password_protected: true })).toBe("Passwortgeschützt");
  expect(protectionLabel({ password_protected: false })).toBeNull();
  expect(protectionLabel({})).toBeNull();
});

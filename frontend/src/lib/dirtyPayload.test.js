import { buildDirtyPayload, hasPayloadChanges, sameValue } from "./dirtyPayload";

// Diese Funktionen entscheiden, was beim Speichern eines Turniers oder der
// Systemeinstellungen tatsaechlich an die API geht. Ein Fehler hier heisst
// entweder verlorene Aenderungen oder ungewolltes Ueberschreiben.

test("nur geaenderte Felder landen im Payload", () => {
  const payload = buildDirtyPayload(
    { name: "Winter Cup", max_teams: 16, description: "gleich" },
    { name: "Sommer Cup", max_teams: 16, description: "gleich" }
  );

  expect(payload).toEqual({ name: "Winter Cup" });
});

test("ohne Aenderung bleibt der Payload leer", () => {
  const original = { name: "Cup", tags: ["a", "b"] };
  const payload = buildDirtyPayload({ name: "Cup", tags: ["a", "b"] }, original);

  expect(payload).toEqual({});
  expect(hasPayloadChanges(payload)).toBe(false);
});

test("ein Feld auf null zu setzen gilt als Aenderung", () => {
  const payload = buildDirtyPayload({ start_date: null }, { start_date: "2026-09-01T18:00:00Z" });

  expect(payload).toEqual({ start_date: null });
  expect(hasPayloadChanges(payload)).toBe(true);
});

test("undefined wird uebersprungen und loescht nichts versehentlich", () => {
  const payload = buildDirtyPayload({ name: "Cup", start_date: undefined }, { name: "Alt", start_date: "2026-09-01" });

  expect(payload).toEqual({ name: "Cup" });
  expect("start_date" in payload).toBe(false);
});

test("neue Felder ohne Vorgaenger gelten als Aenderung", () => {
  expect(buildDirtyPayload({ prize_pool: "500" }, {})).toEqual({ prize_pool: "500" });
});

test("Schluesselreihenfolge in Objekten macht keinen Unterschied", () => {
  const payload = buildDirtyPayload(
    { rules: { schedule_mode: "hybrid", event_mode: "local" } },
    { rules: { event_mode: "local", schedule_mode: "hybrid" } }
  );

  expect(payload).toEqual({});
});

test("Reihenfolge in Listen ist dagegen eine echte Aenderung", () => {
  const payload = buildDirtyPayload({ seeds: ["b", "a"] }, { seeds: ["a", "b"] });

  expect(payload).toEqual({ seeds: ["b", "a"] });
});

test("verschachtelte Aenderungen werden erkannt", () => {
  const payload = buildDirtyPayload(
    { settings: { limits: { teams: 32 } } },
    { settings: { limits: { teams: 16 } } }
  );

  expect(payload).toEqual({ settings: { limits: { teams: 32 } } });
});

test("null und undefined gelten als derselbe Wert", () => {
  // Beide werden vor dem Vergleich zu null normalisiert. Wichtig zu wissen:
  // ein Wechsel von "nicht gesetzt" auf null erzeugt bewusst keinen Schreibvorgang.
  expect(sameValue(null, undefined)).toBe(true);
  expect(buildDirtyPayload({ note: null }, { note: undefined })).toEqual({});
});

test("Zahl und Zahl als Text sind nicht dasselbe", () => {
  expect(sameValue(16, "16")).toBe(false);
  expect(buildDirtyPayload({ max_teams: "16" }, { max_teams: 16 })).toEqual({ max_teams: "16" });
});

test("leere oder fehlende Eingaben ergeben einen leeren Payload", () => {
  expect(buildDirtyPayload(null, { a: 1 })).toEqual({});
  expect(buildDirtyPayload(undefined)).toEqual({});
  expect(buildDirtyPayload({}, undefined)).toEqual({});
});

test("hasPayloadChanges vertraegt fehlende Eingaben", () => {
  expect(hasPayloadChanges(null)).toBe(false);
  expect(hasPayloadChanges(undefined)).toBe(false);
  expect(hasPayloadChanges({ name: "Cup" })).toBe(true);
});

import {
  formatDate,
  formatDateTime,
  fromDateTimeLocal,
  getRegistrationState,
  hasOnlineRegistration,
  normalizeDateTimeFields,
  toDateTimeLocalInput,
} from "./datetime";

// getRegistrationState entscheidet, ob sich jemand anmelden darf.
// normalizeDateTimeFields wandelt Formulareingaben vor dem Speichern um.

describe("Formatierung", () => {
  test("leere Werte bekommen den Platzhalter", () => {
    expect(formatDateTime(null)).toBe("TBD");
    expect(formatDate(undefined)).toBe("TBD");
    expect(formatDateTime("", { fallback: "offen" })).toBe("offen");
  });

  test("unlesbare Werte werden unveraendert durchgereicht statt zu crashen", () => {
    expect(formatDateTime("kein datum")).toBe("kein datum");
    expect(formatDate("kein datum")).toBe("kein datum");
  });
});

describe("Formularfelder", () => {
  test("Eingabe und Rueckwandlung ergeben denselben Zeitpunkt", () => {
    const input = toDateTimeLocalInput("2026-09-08T20:30:00Z");
    expect(input).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    expect(new Date(fromDateTimeLocal(input)).getTime()).toBe(new Date("2026-09-08T20:30:00Z").getTime());
  });

  test("ungueltige Eingaben ergeben null statt eines kaputten Datums", () => {
    expect(fromDateTimeLocal("")).toBeNull();
    expect(fromDateTimeLocal("morgen")).toBeNull();
    expect(toDateTimeLocalInput("morgen")).toBe("");
    expect(toDateTimeLocalInput(null)).toBe("");
  });

  test("gesetzte Felder werden nach ISO umgewandelt", () => {
    const payload = normalizeDateTimeFields(
      { start_date: "2026-09-08T20:30", name: "Cup" },
      ["start_date"]
    );

    expect(payload.start_date).toBe(new Date("2026-09-08T20:30").toISOString());
    expect(payload.name).toBe("Cup");
  });

  test("geleerte Felder werden zu null, fehlende bleiben abwesend", () => {
    const payload = normalizeDateTimeFields(
      { start_date: "", other: "x" },
      ["start_date", "end_date"]
    );

    expect(payload.start_date).toBeNull();
    expect("end_date" in payload).toBe(false);
  });
});

describe("Anmeldestatus", () => {
  const future = new Date(Date.now() + 86400000).toISOString();
  const past = new Date(Date.now() - 86400000).toISOString();

  test("ohne Turnier ist keine Anmeldung moeglich", () => {
    expect(getRegistrationState(null).canRegister).toBe(false);
  });

  test("Entwuerfe sind nicht anmeldbar", () => {
    const state = getRegistrationState({ status: "draft" });
    expect(state.canRegister).toBe(false);
    expect(state.state).toBe("draft");
  });

  test("deaktivierte und Nur-Einladung-Turniere sind gesperrt", () => {
    expect(getRegistrationState({ status: "registration_open", registration_enabled: false }).canRegister).toBe(false);
    expect(getRegistrationState({ status: "registration_open", is_invite_only: true }).canRegister).toBe(false);
  });

  test("offen im Zeitfenster", () => {
    const state = getRegistrationState({
      status: "registration_open",
      registration_open_from: past,
      registration_open_until: future,
    });

    expect(state.canRegister).toBe(true);
    expect(state.state).toBe("open");
  });

  test("vor dem Start noch nicht offen", () => {
    const state = getRegistrationState({ status: "registration_open", registration_open_from: future });

    expect(state.canRegister).toBe(false);
    expect(state.state).toBe("scheduled");
  });

  test("nach dem Ende geschlossen", () => {
    const state = getRegistrationState({ status: "registration_open", registration_open_until: past });

    expect(state.canRegister).toBe(false);
    expect(state.state).toBe("closed");
  });

  test("ein anderer Status als registration_open bleibt geschlossen", () => {
    expect(getRegistrationState({ status: "live" }).canRegister).toBe(false);
    expect(getRegistrationState({ status: "completed" }).canRegister).toBe(false);
  });

  test("das Substantiv der Beschriftung ist anpassbar", () => {
    expect(getRegistrationState({ status: "live" }, "Einreichung").label).toContain("Einreichung");
  });
});

describe("Online-Anmeldung", () => {
  test("braucht beide Schalter und mindestens einen Zeitpunkt", () => {
    expect(hasOnlineRegistration({
      online_registration_enabled: true,
      registration_enabled: true,
      registration_open_from: "2026-09-01T10:00:00Z",
    })).toBe(true);

    expect(hasOnlineRegistration({ online_registration_enabled: true, registration_enabled: true })).toBe(false);
    expect(hasOnlineRegistration({ online_registration_enabled: false, registration_enabled: true, registration_open_from: "x" })).toBe(false);
    expect(hasOnlineRegistration(null)).toBe(false);
  });
});

import type { AxiosRequestConfig } from "axios";

// Der API-Client ist der gemeinsame Datenweg aller Screens. Zwei Dinge muessen
// stimmen: eine abgelaufene Sitzung wird still erneuert statt den Nutzer
// auszusperren, und wenn offline auf alte Daten zurueckgefallen wird, muss das
// erkennbar bleiben - sonst zeigt ein Screen veraltete Staende als aktuell an.

const mockGetStaleCache = jest.fn();
const mockSetCached = jest.fn(async (..._args: unknown[]) => {});
const mockBuildCacheKey = jest.fn((..._args: unknown[]) => "cache-key");

jest.mock("./cache", () => ({
  buildCacheKey: (...args: unknown[]) => mockBuildCacheKey(...args),
  getStaleCache: (...args: unknown[]) => mockGetStaleCache(...args),
  setCached: (...args: unknown[]) => mockSetCached(...args),
  invalidateCache: jest.fn(async () => {}),
  clearAllCache: jest.fn(async () => {}),
}));

// eslint-disable-next-line @typescript-eslint/no-var-requires
const { api, configureAuthBridge, responseFromCache } = require("./api");

type Handler = (config: AxiosRequestConfig) => Promise<unknown> | unknown;

let handler: Handler;
const persistSession = jest.fn(async () => {});
const clearSession = jest.fn(async () => {});
let tokens = { accessToken: "access-alt", refreshToken: "refresh-alt", userId: "u-1" };

function networkError(config: AxiosRequestConfig) {
  // Axios haengt bei echten Netzfehlern die Config an; ohne sie findet der
  // Interceptor den Cache-Schluessel nicht.
  const error: Error & { code?: string; config?: unknown; isAxiosError?: boolean } = new Error("Network Error");
  error.code = "ERR_NETWORK";
  error.config = config;
  error.isAxiosError = true;
  return error;
}

function httpError(status: number, config: AxiosRequestConfig) {
  const error: Error & { response?: unknown; config?: unknown; isAxiosError?: boolean } = new Error(`HTTP ${status}`);
  error.response = { status, data: {}, headers: {}, config };
  error.config = config;
  error.isAxiosError = true;
  return error;
}

beforeEach(() => {
  jest.clearAllMocks();
  tokens = { accessToken: "access-alt", refreshToken: "refresh-alt", userId: "u-1" };
  configureAuthBridge({
    readTokens: () => tokens,
    persistSession,
    clearSession,
  });
  // Der Adapter ersetzt das Netzwerk: jeder Testfall beschreibt, was der Server
  // auf welchen Aufruf antwortet.
  api.defaults.adapter = async (config: AxiosRequestConfig) => handler(config);
});

test("eine abgelaufene Sitzung wird erneuert und der Aufruf wiederholt", async () => {
  const seen: string[] = [];
  handler = async (config) => {
    const url = String(config.url);
    seen.push(url);
    if (url.includes("/auth/mobile/refresh")) {
      return { data: { user: { id: "u-1" }, access_token: "access-neu", refresh_token: "refresh-neu" }, status: 200, headers: {}, config };
    }
    if (seen.filter((entry) => entry === url).length === 1) throw httpError(401, config);
    return { data: { ok: true }, status: 200, headers: {}, config };
  };

  const { data } = await api.get("/dashboard");

  expect(data).toEqual({ ok: true });
  expect(seen).toContain("/auth/mobile/refresh");
  expect(persistSession).toHaveBeenCalledWith(expect.objectContaining({ access_token: "access-neu" }));
});

test("scheitert die Erneuerung, wird die Sitzung beendet statt endlos zu versuchen", async () => {
  handler = async (config) => {
    if (String(config.url).includes("/auth/mobile/refresh")) throw httpError(401, config);
    throw httpError(401, config);
  };

  await expect(api.get("/dashboard")).rejects.toBeTruthy();
  expect(clearSession).toHaveBeenCalled();
  expect(persistSession).not.toHaveBeenCalled();
});

test("ein 401 beim Anmelden loest keinen Erneuerungsversuch aus", async () => {
  const seen: string[] = [];
  handler = async (config) => {
    seen.push(String(config.url));
    throw httpError(401, config);
  };

  await expect(api.post("/auth/mobile/login", {})).rejects.toBeTruthy();

  expect(seen.filter((url) => url.includes("/auth/mobile/refresh"))).toHaveLength(0);
});

test("mehrere gleichzeitige 401er teilen sich eine einzige Erneuerung", async () => {
  let refreshCalls = 0;
  const retried = new Set<string>();
  handler = async (config) => {
    const url = String(config.url);
    if (url.includes("/auth/mobile/refresh")) {
      refreshCalls += 1;
      await new Promise((resolve) => setTimeout(resolve, 10));
      return { data: { user: { id: "u-1" }, access_token: "access-neu", refresh_token: "refresh-neu" }, status: 200, headers: {}, config };
    }
    if (!retried.has(url)) {
      retried.add(url);
      throw httpError(401, config);
    }
    return { data: { url }, status: 200, headers: {}, config };
  };

  await Promise.all([api.get("/dashboard"), api.get("/notifications"), api.get("/teams")]);

  expect(refreshCalls).toBe(1);
});

test("offline wird auf zwischengespeicherte Daten zurueckgegriffen - erkennbar markiert", async () => {
  mockGetStaleCache.mockResolvedValue({ stand: "von gestern" });
  handler = async (config) => {
    throw networkError(config);
  };

  const response = await api.get("/dashboard");

  expect(response.data).toEqual({ stand: "von gestern" });
  expect(responseFromCache(response)).toBe(true);
});

test("frische Antworten sind nicht als Cache markiert", async () => {
  handler = async (config) => ({ data: { ok: true }, status: 200, headers: {}, config });

  const response = await api.get("/dashboard");

  expect(responseFromCache(response)).toBe(false);
});

test("offline ohne Zwischenspeicher meldet den Fehler weiter", async () => {
  mockGetStaleCache.mockResolvedValue(null);
  handler = async (config) => {
    throw networkError(config);
  };

  await expect(api.get("/dashboard")).rejects.toBeTruthy();
});

test("erfolgreiche GET-Antworten werden zwischengespeichert", async () => {
  handler = async (config) => ({ data: { ok: true }, status: 200, headers: {}, config });

  await api.get("/dashboard");

  expect(mockSetCached).toHaveBeenCalled();
});

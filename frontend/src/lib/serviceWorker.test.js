// @vitest-environment node
import { readFileSync } from "node:fs";
import vm from "node:vm";
import { describe, expect, test, vi } from "vitest";

const source = readFileSync(new URL("../../public/service-worker.js", import.meta.url), "utf8");

function worker(fetchResult = vi.fn()) {
  const handlers = {};
  const cache = { match: vi.fn(), put: vi.fn(), keys: vi.fn(async () => []), addAll: vi.fn() };
  const caches = {
    open: vi.fn(async () => cache),
    keys: vi.fn(async () => ["tls-static-v1", "tls-static-build-new", "unrelated-cache"]),
    delete: vi.fn(async () => true),
  };
  const self = { location: { origin: "https://club.example" },
    addEventListener: (name, handler) => { handlers[name] = handler; },
    clients: { claim: vi.fn() }, skipWaiting: vi.fn(),
  };
  vm.runInNewContext(source.replace("__TLS_BUILD_ID__", "build-new"), { self, caches, fetch: fetchResult, URL, Response });
  return { handlers, cache, caches, fetchResult };
}

describe("production service worker", () => {
  test("never intercepts authentication API or non-GET requests", () => {
    const runtime = worker();
    for (const request of [
      { url: "https://club.example/api/auth/me", method: "GET", mode: "cors" },
      { url: "https://club.example/verify-email", method: "POST", mode: "navigate" },
    ]) {
      const respondWith = vi.fn();
      runtime.handlers.fetch({ request, respondWith });
      expect(respondWith).not.toHaveBeenCalled();
    }
  });
  test("verification navigation fetches fresh HTML without persisting token URLs", async () => {
    const runtime = worker(vi.fn(async () => new Response("fresh")));
    const request = { url: "https://club.example/verify-email?token=private", method: "GET", mode: "navigate" };
    let response;
    runtime.handlers.fetch({ request, respondWith: (result) => { response = result; } });
    expect(await (await response).text()).toBe("fresh");
    expect(runtime.fetchResult).toHaveBeenCalledWith(request, { cache: "no-store" });
    expect(runtime.caches.open).not.toHaveBeenCalled();
  });
  test("offline verification displays a connection error instead of stale application HTML", async () => {
    const runtime = worker(vi.fn(async () => { throw new Error("offline"); }));
    let response;
    runtime.handlers.fetch({ request: { url: "https://club.example/verify-email", method: "GET", mode: "navigate" }, respondWith: (result) => { response = result; } });
    expect((await response).status).toBe(503);
    expect(await (await response).text()).toContain("Keine Verbindung");
    expect(runtime.cache.match).not.toHaveBeenCalled();
  });
  test("activation deletes only obsolete TLS cache versions", async () => {
    const runtime = worker();
    let activation;
    runtime.handlers.activate({ waitUntil: (result) => { activation = result; } });
    await activation;
    expect(runtime.caches.delete.mock.calls).toEqual([["tls-static-v1"]]);
  });
});

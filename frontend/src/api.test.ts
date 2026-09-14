import { describe, expect, it } from "vitest";
import { loadLocalApiStatus, localApiBase, type FetchLike } from "./api";

function response(body: object, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("local browser API client", () => {
  it("uses same-origin health and capability routes", async () => {
    const calls: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
    const fetcher: FetchLike = async (path, options) => {
      calls.push([path, options]);
      return String(path).endsWith("/health")
        ? response({ status: "ok", database: "ready" })
        : response({ capabilities: { authentication: { state: "verified" }, stock_snapshot: { state: "unavailable", code: "MARKET_DATA_NOT_SUBSCRIBED" } } });
    };
    const status = await loadLocalApiStatus(fetcher, "/api/v1");
    expect(status.mode).toBe("live");
    expect(calls.map(([path]) => path)).toEqual(["/api/v1/health", "/api/v1/capabilities"]);
    expect(calls.every(([, options]) => options?.credentials === "same-origin")).toBe(true);
    if (status.mode === "live") expect(status.connections.map((item) => item.state)).toEqual(["healthy", "healthy", "unavailable", "degraded"]);
  });

  it("uses mock fallback only when the local API cannot be reached", async () => {
    const unavailable: FetchLike = async () => { throw new TypeError("Failed to fetch"); };
    await expect(loadLocalApiStatus(unavailable, "/api/v1")).resolves.toEqual({ mode: "fallback", reason: "Failed to fetch" });
  });

  it("rejects browser configuration that could send local data off-host", () => {
    expect(() => localApiBase("https://example.test/api")).toThrow("same-origin");
    expect(() => localApiBase("//example.test/api")).toThrow("same-origin");
    expect(localApiBase("/local-api/")).toBe("/local-api");
  });
});

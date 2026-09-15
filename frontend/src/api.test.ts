import { describe, expect, it } from "vitest";
import { ingestionStatus, loadLocalApiStatus, localApiBase, localApi, probeCapabilities, type FetchLike } from "./api";
import { capabilityRows } from "./capabilityView";
import { ingestionRows } from "./ingestionView";

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

  it("posts an explicit same-origin probe and redacts unsupported provider fields", async () => {
    const calls: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
    const fetcher: FetchLike = async (path, options) => {
      calls.push([path, options]);
      return response({
        source: "operator_probe",
        capabilities: {
          authentication: { state: "verified", http_status: 200, evidence_hash: "should-not-reach-ui" },
          account_read: { state: "unavailable", code: "INVALID_TOKEN", raw_error: "secret" },
          stock_snapshot: { state: "unavailable", code: "MARKET_DATA_NOT_SUBSCRIBED" },
          option_snapshot: { state: "unknown", code: "bad provider error" },
        },
      });
    };
    const report = await probeCapabilities(fetcher, "/api/v1");
    expect(calls).toHaveLength(1);
    expect(calls[0][0]).toBe("/api/v1/capabilities/probe");
    expect(calls[0][1]?.method).toBe("POST");
    expect(calls[0][1]?.credentials).toBe("same-origin");
    expect(report.capabilities.authentication).toEqual({ state: "verified", code: null, httpStatus: 200 });
    expect(report.capabilities.account_read).toEqual({ state: "unavailable", code: "INVALID_TOKEN", httpStatus: null });
    expect(report.capabilities.option_snapshot.code).toBeNull();
  });

  it("builds safe capability view rows without values or raw errors", () => {
    const rows = capabilityRows({ source: "operator_probe", capabilities: {
      authentication: { state: "verified", code: null, httpStatus: 200 },
      account_read: { state: "unavailable", code: "INVALID_TOKEN", httpStatus: null },
      stock_snapshot: { state: "unavailable", code: "MARKET_DATA_NOT_SUBSCRIBED", httpStatus: 403 },
      option_snapshot: { state: "unknown", code: null, httpStatus: null },
    } });
    expect(rows).toEqual([
      { label: "Authentication", state: "verified", detail: "HTTP 200" },
      { label: "Account read", state: "unavailable", detail: "INVALID_TOKEN" },
      { label: "Stock snapshots", state: "unavailable", detail: "MARKET_DATA_NOT_SUBSCRIBED" },
      { label: "Option snapshots", state: "unknown", detail: "unknown" },
    ]);
  });

  it("uses explicit same-origin ingestion lifecycle calls and strips raw worker details", async () => {
    const calls: Array<[RequestInfo | URL, RequestInit | undefined]> = [];
    const statusBody = { state: "running", stock_symbols: ["NVDA", "AMD"], option_contracts: ["NVDA-C"], started_at: "2026-09-15T14:00:00+00:00", stopped_at: null, last_stock: { raw_error: "secret" }, last_options: { provider_payload: "private" } };
    const fetcher: FetchLike = async (path, options) => { calls.push([path, options]); return response(statusBody); };
    const initial = await ingestionStatus(fetcher, "/api/v1");
    const started = await localApi.startIngestion(["NVDA"], fetcher, "/api/v1");
    const stopped = await localApi.stopIngestion(fetcher, "/api/v1");
    expect(initial).toEqual({ state: "running", stockSymbolCount: 2, optionContractCount: 1, startedAt: "2026-09-15T14:00:00+00:00", stoppedAt: null });
    expect(started.stockSymbolCount).toBe(2);
    expect(stopped.optionContractCount).toBe(1);
    expect(calls.map(([path]) => path)).toEqual(["/api/v1/ingestion/status", "/api/v1/ingestion/start", "/api/v1/ingestion/stop"]);
    expect(calls.map(([, init]) => init?.method)).toEqual(["GET", "POST", "POST"]);
    expect(calls.every(([, init]) => init?.credentials === "same-origin")).toBe(true);
    expect(calls[1][1]?.body).toBe(JSON.stringify({ stock_symbols: ["NVDA"], option_contracts: [] }));
  });

  it("maps lifecycle status to redacted UI rows", () => {
    expect(ingestionRows({ state: "stopped", stockSymbolCount: 3, optionContractCount: 2, startedAt: null, stoppedAt: "2026-09-15T14:05:00+00:00" })).toEqual([
      { label: "Lifecycle", detail: "stopped" }, { label: "Scope", detail: "3 stocks / 2 option contracts" },
      { label: "Started", detail: "Not started" }, { label: "Stopped", detail: "2026-09-15T14:05:00+00:00" },
    ]);
  });
});

export type ApiConnectionState = "healthy" | "degraded" | "unavailable";

export interface CapabilityValue {
  state: "verified" | "unavailable" | "unknown";
  code?: string | null;
}

export interface LocalApiStatus {
  mode: "live";
  generatedAt: string;
  connections: Array<{ name: string; detail: string; state: ApiConnectionState }>;
}

export interface ApiFallback {
  mode: "fallback";
  reason: string;
}

export type ApiStatus = LocalApiStatus | ApiFallback;
export type FetchLike = (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>;

const DEFAULT_API_BASE = "/api/v1";

declare global {
  interface Window {
    __WHALE_RIDER_API_BASE__?: string;
  }
}

function configuredApiBase(): string | undefined {
  return typeof window === "undefined" ? undefined : window.__WHALE_RIDER_API_BASE__;
}

export function localApiBase(value: string | undefined = configuredApiBase()): string {
  const base = (value || DEFAULT_API_BASE).trim();
  if (!base.startsWith("/") || base.startsWith("//") || base.includes("://") || base.includes("\\")) {
    throw new Error("The local API base must be a same-origin absolute path.");
  }
  return base.replace(/\/+$/, "") || DEFAULT_API_BASE;
}

async function json(fetcher: FetchLike, path: string): Promise<unknown> {
  const response = await fetcher(path, {
    method: "GET",
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`Local API returned HTTP ${response.status}.`);
  return response.json();
}

function healthState(value: unknown): ApiConnectionState {
  return value === "ok" ? "healthy" : value === "degraded" ? "degraded" : "unavailable";
}

function capabilityState(value: unknown): ApiConnectionState {
  return value === "verified" ? "healthy" : value === "unavailable" ? "unavailable" : "degraded";
}

function readCapabilities(body: unknown): Record<string, CapabilityValue> {
  if (!body || typeof body !== "object" || !("capabilities" in body)) throw new Error("Local API returned an invalid capability response.");
  const values = (body as { capabilities: unknown }).capabilities;
  if (!values || typeof values !== "object") throw new Error("Local API returned invalid capabilities.");
  return values as Record<string, CapabilityValue>;
}

export async function loadLocalApiStatus(fetcher: FetchLike = fetch, base = localApiBase()): Promise<ApiStatus> {
  try {
    const [healthBody, capabilityBody] = await Promise.all([json(fetcher, `${base}/health`), json(fetcher, `${base}/capabilities`)]);
    const health = healthBody as { status?: unknown; database?: unknown };
    const capabilities = readCapabilities(capabilityBody);
    const capabilityConnection = (name: string, key: string) => {
      const value = capabilities[key];
      return { name, detail: value?.code ? String(value.code) : value ? `Capability ${value.state}` : "Capability not reported", state: capabilityState(value?.state) };
    };
    return {
      mode: "live",
      generatedAt: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
      connections: [
        { name: "Local service", detail: health.database === "ready" ? "SQLite ready" : "Database unavailable", state: healthState(health.status) },
        capabilityConnection("Webull authentication", "authentication"),
        capabilityConnection("Stock coverage", "stock_snapshot"),
        capabilityConnection("Option coverage", "option_snapshot"),
      ],
    };
  } catch (error) {
    return { mode: "fallback", reason: error instanceof Error ? error.message : "Local API is unavailable." };
  }
}

export interface PositionRecord { instrument_id: string; underlying: string; asset_type: string; quantity: string }
export interface PositionSnapshot { account_id: string; version: number; source: string; complete: boolean; positions: PositionRecord[] }
export interface ExposureItem { underlying: string; known_delta_shares: string; gross_known_delta_shares: string; net_delta_dollars: string | null; gross_delta_dollars: string | null; is_complete: boolean; unknown_instrument_ids: string[] }
export interface ExposureReport { snapshot_version: number; is_complete: boolean; by_underlying: ExposureItem[] }
export interface ImportDraft { import_id: string; account_id: string; expected_position_version: number; status: "review_required" | "ready_for_commit"; row_count: number }
export interface SuggestionCandidate { id: string; action: string; snapshot_version: number; instrument_id?: string; side?: string; quantity?: string }
export interface SuggestionsResponse { status: string; reason?: string; snapshot_version: number; candidates: SuggestionCandidate[] }
export interface RuleDryRun { mode: "dry_run"; code: string; triggered: boolean; notional: string | null; enrichment_only: boolean }
export interface ProbeCapability { state: "verified" | "unavailable" | "unknown"; code: string | null; httpStatus: number | null }
export interface CapabilityProbeReport { source: "operator_probe" | "local_fallback"; capabilities: Record<string, ProbeCapability> }

async function requestJson<T>(path: string, method: "GET" | "POST" | "PATCH", body?: object, fetcher: FetchLike = fetch, base = localApiBase()): Promise<T> {
  const response = await fetcher(`${base}${path}`, { method, credentials: "same-origin", headers: { Accept: "application/json", ...(body ? { "Content-Type": "application/json" } : {}) }, body: body ? JSON.stringify(body) : undefined });
  const payload: unknown = await response.json();
  if (!response.ok) {
    const message = payload && typeof payload === "object" && "detail" in payload ? JSON.stringify((payload as { detail: unknown }).detail) : `HTTP ${response.status}`;
    throw new Error(message);
  }
  return payload as T;
}

export const localApi = {
  simulateRule: (body: object) => requestJson<RuleDryRun>("/rules/simulate", "POST", body),
  createImport: (body: object) => requestJson<ImportDraft>("/imports", "POST", body),
  updateImport: (id: string, body: object) => requestJson<ImportDraft>(`/imports/${encodeURIComponent(id)}/rows`, "PATCH", body),
  commitImport: (id: string) => requestJson<PositionSnapshot>(`/imports/${encodeURIComponent(id)}/commit`, "POST", {}),
  positions: (accountId: string) => requestJson<PositionSnapshot>(`/positions/${encodeURIComponent(accountId)}`, "GET"),
  exposure: (accountId: string) => requestJson<ExposureReport>(`/positions/${encodeURIComponent(accountId)}/exposure`, "GET"),
  suggestions: (accountId: string) => requestJson<SuggestionsResponse>("/suggestions", "POST", { account_id: accountId }),
  probeCapabilities: (fetcher: FetchLike = fetch, base = localApiBase()) => probeCapabilities(fetcher, base),
};

function safeCapability(value: unknown): ProbeCapability {
  if (!value || typeof value !== "object") return { state: "unknown", code: "UNREPORTED", httpStatus: null };
  const record = value as Record<string, unknown>;
  const state = record.state === "verified" || record.state === "unavailable" || record.state === "unknown" ? record.state : "unknown";
  const code = typeof record.code === "string" && /^[A-Z0-9_]{1,80}$/.test(record.code) ? record.code : null;
  const httpStatus = typeof record.http_status === "number" && Number.isInteger(record.http_status) && record.http_status >= 100 && record.http_status <= 599 ? record.http_status : null;
  return { state, code, httpStatus };
}

export async function probeCapabilities(fetcher: FetchLike = fetch, base = localApiBase()): Promise<CapabilityProbeReport> {
  let response: Response;
  try {
    response = await fetcher(`${base}/capabilities/probe`, { method: "POST", credentials: "same-origin", headers: { Accept: "application/json" } });
  } catch {
    throw new Error("Capability probe is unavailable.");
  }
  if (!response.ok) throw new Error(`Capability probe returned HTTP ${response.status}.`);
  let body: unknown;
  try { body = await response.json(); } catch { throw new Error("Capability probe returned invalid JSON."); }
  if (!body || typeof body !== "object" || !("capabilities" in body) || !(body as { capabilities: unknown }).capabilities || typeof (body as { capabilities: unknown }).capabilities !== "object") throw new Error("Capability probe returned an invalid report.");
  const raw = (body as { capabilities: Record<string, unknown> }).capabilities;
  const capabilities: Record<string, ProbeCapability> = {};
  for (const key of ["authentication", "account_read", "stock_snapshot", "option_snapshot"]) capabilities[key] = safeCapability(raw[key]);
  return { source: (body as { source?: unknown }).source === "operator_probe" ? "operator_probe" : "local_fallback", capabilities };
}

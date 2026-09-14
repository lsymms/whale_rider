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

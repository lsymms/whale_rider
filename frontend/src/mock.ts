export type HealthState = "healthy" | "degraded" | "unavailable";

export interface FlowEvent {
  id: string;
  symbol: string;
  instrument: string;
  asset: "Stock" | "Option";
  quantity: string;
  value: string;
  observed: string;
  delay: string;
  relevance: string;
  quality: string;
}

export interface Position {
  instrument: string;
  detail: string;
  quantity: string;
  price: string;
  delta: string;
  deltaDollars: string;
  source: string;
}

export interface ConnectionStatus {
  name: string;
  detail: string;
  state: HealthState;
}

export const mockDashboard = {
  generatedAt: "10:31:04 ET",
  events: [
    {
      id: "WR-1042",
      symbol: "NVDA",
      instrument: "Stock · held underlying",
      asset: "Stock",
      quantity: "80,000 shares × $150.00",
      value: "$12,000,000",
      observed: "10:31:04 ET",
      delay: "received +0.6s",
      relevance: "Held underlying",
      quality: "Execution observed; aggressor unknown",
    },
    {
      id: "WR-1043",
      symbol: "NVDA",
      instrument: "Sep 18, 2026 · 155 CALL",
      asset: "Option",
      quantity: "250 contracts × $5.20 × 100",
      value: "$130,000 premium",
      observed: "10:31:08 ET",
      delay: "observed +8s",
      relevance: "Held underlying",
      quality: "Polled execution; side unknown",
    },
  ] satisfies FlowEvent[],
  positions: [
    { instrument: "NVDA", detail: "Stock", quantity: "+100 shares", price: "$150.00", delta: "1.00", deltaDollars: "$15,000", source: "Reviewed demo" },
    { instrument: "NVDA 155 CALL", detail: "2026-09-18 · multiplier 100", quantity: "+2 contracts", price: "$5.20", delta: "0.55", deltaDollars: "$16,500", source: "Reviewed demo" },
  ] satisfies Position[],
  connections: [
    { name: "Stock coverage", detail: "Synthetic stream", state: "healthy" },
    { name: "Option coverage", detail: "Synthetic polling", state: "degraded" },
    { name: "Position book", detail: "Snapshot v12 · reviewed", state: "healthy" },
    { name: "Telegram delivery", detail: "Not connected in mock mode", state: "unavailable" },
  ] satisfies ConnectionStatus[],
};

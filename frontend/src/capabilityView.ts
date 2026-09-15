import type { CapabilityProbeReport } from "./api";

export interface CapabilityRow { label: string; state: "verified" | "unavailable" | "unknown"; detail: string }

const labels: Array<[string, string]> = [["authentication", "Authentication"], ["account_read", "Account read"], ["stock_snapshot", "Stock snapshots"], ["option_snapshot", "Option snapshots"]];

export function capabilityRows(report: CapabilityProbeReport | null): CapabilityRow[] {
  if (!report) return labels.map(([, label]) => ({ label, state: "unknown", detail: "Probe has not run" }));
  return labels.map(([key, label]) => {
    const value = report.capabilities[key];
    const detail = value.code ?? (value.httpStatus ? `HTTP ${value.httpStatus}` : value.state);
    return { label, state: value.state, detail };
  });
}

import type { IngestionStatus } from "./api";

export interface IngestionRow { label: string; detail: string }

export function ingestionRows(status: IngestionStatus | null): IngestionRow[] {
  if (!status) return [{ label: "Lifecycle", detail: "Status has not been loaded" }];
  return [
    { label: "Lifecycle", detail: status.state },
    { label: "Scope", detail: `${status.stockSymbolCount} stocks / ${status.optionContractCount} option contracts` },
    { label: "Started", detail: status.startedAt ?? "Not started" },
    { label: "Stopped", detail: status.stoppedAt ?? "Not stopped" },
  ];
}

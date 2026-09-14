import { describe, expect, it } from "vitest";
import { mockDashboard } from "./mock";

describe("mock dashboard adapter", () => {
  it("keeps executions, positions, and health states usable by the shell", () => {
    expect(mockDashboard.events).toHaveLength(2);
    expect(mockDashboard.events.every((event) => event.id.startsWith("WR-") && event.quantity.includes("×"))).toBe(true);
    expect(mockDashboard.positions).toHaveLength(2);
    expect(mockDashboard.connections.map((item) => item.state)).toEqual(["healthy", "degraded", "healthy", "unavailable"]);
  });
});

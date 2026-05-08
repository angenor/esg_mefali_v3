import { describe, it, expect, beforeEach, vi, afterEach } from "vitest";
import { TTLLRU } from "../src/shared/lru";

describe("TTLLRU", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("set et get fonctionnent", () => {
    const cache = new TTLLRU<string>(3, 1000);
    cache.set("a", "1");
    expect(cache.get("a")).toBe("1");
  });

  it("retourne null si TTL expiré", () => {
    const cache = new TTLLRU<string>(3, 1000);
    cache.set("a", "1");
    vi.advanceTimersByTime(1500);
    expect(cache.get("a")).toBeNull();
  });

  it("évince la plus ancienne entrée si maxSize dépassé", () => {
    const cache = new TTLLRU<string>(2, 1000);
    cache.set("a", "1");
    cache.set("b", "2");
    cache.set("c", "3");
    expect(cache.size).toBe(2);
    expect(cache.get("a")).toBeNull();
    expect(cache.get("b")).toBe("2");
    expect(cache.get("c")).toBe("3");
  });

  it("met à jour l'ordre LRU sur get", () => {
    const cache = new TTLLRU<string>(2, 1000);
    cache.set("a", "1");
    cache.set("b", "2");
    cache.get("a"); // a re-pushé en queue
    cache.set("c", "3"); // doit éliminer b, pas a
    expect(cache.get("a")).toBe("1");
    expect(cache.get("b")).toBeNull();
  });

  it("delete supprime", () => {
    const cache = new TTLLRU<number>(3, 1000);
    cache.set("k", 42);
    cache.delete("k");
    expect(cache.get("k")).toBeNull();
  });

  it("clear vide tout", () => {
    const cache = new TTLLRU<number>(3, 1000);
    cache.set("a", 1);
    cache.set("b", 2);
    cache.clear();
    expect(cache.size).toBe(0);
  });
});

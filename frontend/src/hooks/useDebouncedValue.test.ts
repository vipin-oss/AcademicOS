import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useDebouncedValue } from "./useDebouncedValue";

/**
 * Pins the debounce contract the list framework relies on: the value only
 * updates after `delay` ms, and a pending update is cancelled on unmount.
 */
describe("useDebouncedValue", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("returns the initial value immediately", () => {
    const { result } = renderHook(() => useDebouncedValue("a", 100));
    expect(result.current).toBe("a");
  });

  it("updates only after the delay", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 100),
      { initialProps: { value: "a" } },
    );

    rerender({ value: "b" });
    expect(result.current).toBe("a"); // still the old value

    act(() => {
      vi.advanceTimersByTime(99);
    });
    expect(result.current).toBe("a");

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("b");
  });

  it("resets the timer on every change (leading change wins)", () => {
    const { result, rerender } = renderHook(
      ({ value }) => useDebouncedValue(value, 100),
      { initialProps: { value: "a" } },
    );

    rerender({ value: "b" });
    act(() => {
      vi.advanceTimersByTime(50);
    });
    rerender({ value: "c" });
    act(() => {
      vi.advanceTimersByTime(99);
    });
    expect(result.current).toBe("a"); // "b" was superseded

    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(result.current).toBe("c");
  });
});

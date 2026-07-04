import "@testing-library/jest-dom/vitest";

// Components that ping the API on mount stub `fetch` per-test (see App.test.tsx).
// jsdom provides a global `fetch` type, so no shim is required here.

// jsdom lacks ResizeObserver, which Recharts' ResponsiveContainer requires.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;

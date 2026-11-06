// Setup de vitest: shim de localStorage para jsdom.
//
// Con esta combinación de versiones en Windows, jsdom expone window.localStorage
// como un objeto VACÍO (sin getItem/setItem/removeItem del prototipo Storage):
// todos los tests de LoginPage fallaban SIEMPRE con
// "localStorage.getItem is not a function", antes de tocar el código de la app.
// Restauramos un Storage funcional (backed por Map) solo si está roto.

const stored = Object.getOwnPropertyDescriptor(window, "localStorage");
if (stored) {
  const current = (window as { localStorage: { getItem?: unknown } | null }).localStorage;
  if (!current || typeof current.getItem !== "function") {
    const map = new Map<string, string>();
    Object.defineProperty(window, "localStorage", {
      configurable: true,
      writable: true,
      value: {
        getItem: (k: string): string | null => (map.has(k) ? (map.get(k) as string) : null),
        setItem: (k: string, v: string): void => void map.set(String(k), String(v)),
        removeItem: (k: string): void => void map.delete(k),
        clear: (): void => void map.clear(),
        key: (i: number): string | null => [...map.keys()][i] ?? null,
        get length(): number {
          return map.size;
        },
      },
    });
  }
}

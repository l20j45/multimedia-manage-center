// request(): mensajes de error legibles cuando FastAPI manda `detail` no-string
// (422 de validación manda lista de {loc,msg} → antes se veía "[object Object]")

import { afterEach, describe, expect, it, vi } from "vitest";
import { request } from "./lib/api";

function fetchCon(status: number, body: unknown) {
  return vi.stubGlobal(
    "fetch",
    vi.fn(async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

describe("api.ts → errorDeRespuesta (detail de FastAPI)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("422 con detail=list[{loc,msg}] → texto legible, no [object Object]", async () => {
    fetchCon(422, {
      detail: [{ loc: ["body", "start"], msg: "Field required", type: "missing" }],
    });
    await expect(request("/media")).rejects.toThrow("start: Field required");
  });

  it("detail=string se pasa tal cual", async () => {
    fetchCon(404, { detail: "No encontrado" });
    await expect(request("/media/1")).rejects.toThrow("No encontrado");
  });

  it("detail=objeto {msg} → mensaje con loc", async () => {
    fetchCon(400, { detail: { loc: ["query", "trash"], msg: "valor inválido" } });
    await expect(request("/media")).rejects.toThrow("query.trash: valor inválido");
  });

  it("sin detail → Error <status>", async () => {
    fetchCon(502, {});
    await expect(request("/media")).rejects.toThrow("Error 502");
  });
});

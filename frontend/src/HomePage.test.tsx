// Tests de la pantalla de biblioteca (vitest + Testing Library).
// Corre con:  pnpm test

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import HomePage from "./pages/HomePage";

const listMedia = vi.fn();
const listTags = vi.fn();
const listCollections = vi.fn();
const addCollectionItem = vi.fn();
const mediaUrl = vi.fn(() => "http://fake/file");

vi.mock("./lib/api", () => ({
  listMedia: (...args: unknown[]) => listMedia(...(args as [])),
  listTags: () => listTags(),
  listCollections: () => listCollections(),
  addCollectionItem: (...args: unknown[]) => addCollectionItem(...(args as [])),
  removeCollectionItem: vi.fn(),
  deleteCollection: vi.fn(),
  collectionItems: vi.fn(),
  mediaUrl: () => mediaUrl(),
  updateMedia: vi.fn(),
  deleteMedia: vi.fn(),
  uploadMedia: vi.fn(),
  updateMe: vi.fn(),
}));

const USER = { id: 1, email: "yo@x.com", name: "Yo", is_active: true };
const ITEM = {
  id: 10,
  kind: "image" as const,
  title: "Intro logo",
  tags: ["intro"],
  filename: "intro.png",
  path: "1/abc.png",
  mime: "image/png",
  size: 1234,
  duration_s: null,
  has_thumb: true,
  created_at: new Date().toISOString(),
};

describe("HomePage (biblioteca)", () => {
  beforeEach(() => {
    listMedia.mockReset();
    listTags.mockReset();
    listCollections.mockReset();
    addCollectionItem.mockReset();
    listTags.mockResolvedValue([]);
    listCollections.mockResolvedValue([]);
    listMedia.mockResolvedValue({ items: [ITEM], total: 1 });
  });

  it("muestra las 4 pestañas del menú", async () => {
    render(<HomePage user={USER} onChange={() => {}} onLogout={() => {}} />);
    for (const label of ["Todos", "Audio", "Imágenes", "Vídeos"]) {
      expect(await screen.findByRole("button", { name: new RegExp(label) })).toBeTruthy();
    }
  });

  it("lista un recurso y muestra su título", async () => {
    render(<HomePage user={USER} onChange={() => {}} onLogout={() => {}} />);
    expect(await screen.findByText("Intro logo")).toBeTruthy();
    expect(listMedia).toHaveBeenCalled();
  });

  it("la búsqueda llama al endpoint con q tras el debounce", async () => {
    const user = userEvent.setup({ delay: null });
    render(<HomePage user={USER} onChange={() => {}} onLogout={() => {}} />);
    const box = await screen.findByPlaceholderText("Buscar por nombre o tag...");
    await user.type(box, "logo");
    // el debounce es de 300ms
    await new Promise((r) => setTimeout(r, 400));
    const calls = listMedia.mock.calls;
    const lastCall = calls[calls.length - 1] as unknown[];
    expect((lastCall?.[0] as { q?: string }).q).toBe("logo");
  });

  it("cambiar de pestaña filtra por kind", async () => {
    const user = userEvent.setup({ delay: null });
    render(<HomePage user={USER} onChange={() => {}} onLogout={() => {}} />);
    await user.click(await screen.findByRole("button", { name: /Audio/ }));
    await new Promise((r) => setTimeout(r, 50));
    const calls = listMedia.mock.calls;
    const lastCall = calls[calls.length - 1] as unknown[];
    expect((lastCall?.[0] as { kind?: string }).kind).toBe("audio");
  });

  it("los chips de tags se muestran y filtran", async () => {
    listTags.mockResolvedValue([{ tag: "intro", count: 3 }]);
    const user = userEvent.setup({ delay: null });
    render(<HomePage user={USER} onChange={() => {}} onLogout={() => {}} />);
    // el chip de la barra y el mini-chip del card matchean el mismo nombre:
    // el filtro es el de la barra (el primero en orden del DOM)
    const chip = (await screen.findAllByRole("button", { name: /intro/ }))[0];
    await user.click(chip);
    await new Promise((r) => setTimeout(r, 50));
    const calls = listMedia.mock.calls;
    const lastCall = calls[calls.length - 1] as unknown[];
    expect((lastCall?.[0] as { tag?: string }).tag).toBe("intro");
  });

  it("seleccionar una colección filtra /media por collection", async () => {
    listCollections.mockResolvedValue([{ id: 7, name: "B-roll", item_count: 2 }]);
    const user = userEvent.setup({ delay: null });
    render(<HomePage user={USER} onChange={() => {}} onLogout={() => {}} />);
    await user.selectOptions(
      await screen.findByRole("combobox", { name: "Seleccionar colección" }),
      "7",
    );
    await new Promise((r) => setTimeout(r, 50));
    const calls = listMedia.mock.calls;
    const lastCall = calls[calls.length - 1] as unknown[];
    expect((lastCall?.[0] as { collection?: number }).collection).toBe(7);
  });

  it("el botón + abre el popover y agrega a la colección elegida", async () => {
    listCollections.mockResolvedValue([{ id: 7, name: "B-roll", item_count: 2 }]);
    addCollectionItem.mockResolvedValue({ id: 7, name: "B-roll", item_count: 3 });
    const user = userEvent.setup({ delay: null });
    render(<HomePage user={USER} onChange={() => {}} onLogout={() => {}} />);
    await user.click(await screen.findByRole("button", { name: /Agregar Intro logo a una colección/ }));
    await user.click(await screen.findByRole("button", { name: "Agregar a B-roll" }));
    await new Promise((r) => setTimeout(r, 50));
    expect(addCollectionItem).toHaveBeenCalledWith(7, ITEM.id);
  });
});

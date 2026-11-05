// Tests del panel de detalle (vitest + Testing Library).

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import DetailPanel from "./pages/DetailPanel";

const updateMedia = vi.fn();

vi.mock("./lib/api", () => ({
  updateMedia: (...args: unknown[]) => updateMedia(...(args as [])),
  mediaUrl: () => "http://fake/file",
  rethumbMedia: vi.fn(),
  compressMedia: vi.fn(),
  jobStatus: vi.fn(),
  trimMedia: vi.fn(),
  extractAudio: vi.fn(),
}));

const ITEM = {
  id: 5,
  kind: "image" as const,
  title: "Meme base",
  tags: ["meme"],
  description: "Una nota",
  meta: { camera: "camara X", proyecto: "Intro" },
  filename: "meme.png",
  path: "1/abc.png",
  mime: "image/png",
  size: 2048,
  duration_s: null,
  has_thumb: true,
  visibility: "private" as const,
  rating: 3,
  deleted: false,
  created_at: "2026-11-04T10:00:00",
};

const NOOP = () => {};

describe("DetailPanel", () => {
  beforeEach(() => {
    updateMedia.mockReset();
    updateMedia.mockResolvedValue(ITEM);
  });

  it("muestra información, propiedades y notas", () => {
    render(<DetailPanel item={ITEM} onClose={NOOP} onChanged={NOOP} onAddToCollectionPicker={NOOP} onTrimCreated={NOOP} />);
    expect(screen.getByText("Meme base")).toBeTruthy();
    expect(screen.getByText("Imagen")).toBeTruthy();
    expect(screen.getAllByText(/meme/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/camara X/i).length).toBeGreaterThan(0);
    expect(screen.getByDisplayValue("Una nota")).toBeTruthy();
  });

  it("añade un tag con Enter vía PATCH", async () => {
    const user = userEvent.setup({ delay: null });
    render(<DetailPanel item={ITEM} onClose={NOOP} onChanged={NOOP} onAddToCollectionPicker={NOOP} onTrimCreated={NOOP} />);
    const input = screen.getByLabelText("Añadir tag");
    await user.type(input, "nuevo");
    await user.keyboard("{Enter}");
    expect(updateMedia).toHaveBeenCalledWith(5, { tags: ["meme", "nuevo"] });
  });

  it("quita un tag al hacer clic en el chip", async () => {
    const user = userEvent.setup({ delay: null });
    render(<DetailPanel item={ITEM} onClose={NOOP} onChanged={NOOP} onAddToCollectionPicker={NOOP} onTrimCreated={NOOP} />);
    await user.click(screen.getAllByRole("button", { name: /Quitar tag meme/ })[0]);
    expect(updateMedia).toHaveBeenCalledWith(5, { tags: [] });
  });

  it("guarda notas con el botón", async () => {
    const user = userEvent.setup({ delay: null });
    render(<DetailPanel item={ITEM} onClose={NOOP} onChanged={NOOP} onAddToCollectionPicker={NOOP} onTrimCreated={NOOP} />);
    const notes = screen.getByDisplayValue("Una nota");
    await user.clear(notes);
    await user.type(notes, "Nueva nota");
    await user.click(screen.getByRole("button", { name: /Guardar notas/ }));
    expect(updateMedia).toHaveBeenCalledWith(5, { description: "Nueva nota" });
  });
});

// Tests del panel de administración (solo super admin).
// Corre con:  pnpm test

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import AdminPanel from "./pages/AdminPanel";

const overview = vi.fn();
const patchUser = vi.fn();
const setRegistration = vi.fn();

vi.mock("./lib/api", () => ({
  adminOverview: () => overview(),
  adminPatchUser: (...a: unknown[]) => patchUser(...(a as [])),
  adminSetRegistration: (...a: unknown[]) => setRegistration(...(a as [])),
}));

const USERS = [
  { id: 1, email: "admin@x.com", name: "Admin", is_active: true, is_admin: true, created_at: "2026-01-01" },
  { id: 2, email: "user@x.com", name: "User", is_active: true, is_admin: false, created_at: "2026-01-02" },
];

describe("AdminPanel", () => {
  it("cuenta los usuarios y muestra la lista con su rol", async () => {
    overview.mockResolvedValue({
      users: USERS,
      total: 2,
      active_count: 2,
      registration_open: true,
    });

    render(<AdminPanel me={{ id: 1, email: "admin@x.com", name: "Admin", is_active: true, is_admin: true }} onClose={() => {}} />);

    await screen.findByText("admin@x.com");
    // tarifas: "2 usuarios · 2 activos" en el resumen
    const nums = screen.getAllByText((_, el) => el?.classList.contains("admin-stat-num") ?? false);
    expect(nums.map((n) => n.textContent).sort()).toEqual(["2", "2"]);
    expect(screen.getByText("user@x.com")).toBeTruthy();
  });

  it("cierra y abre el registro con el botón", async () => {
    overview.mockResolvedValue({
      users: USERS,
      total: 2,
      active_count: 2,
      registration_open: true,
    });
    setRegistration.mockResolvedValue({ open: false });

    render(<AdminPanel me={{ id: 1, email: "admin@x.com", name: "Admin", is_active: true, is_admin: true }} onClose={() => {}} />);

    const button = await screen.findByText(/Registro: abierto/);
    await userEvent.click(button);
    await waitFor(() => expect(setRegistration).toHaveBeenCalledWith(false));
    expect(await screen.findByText(/Registro: cerrado/)).toBeTruthy();
  });

  it("permite activar/desactivar una cuenta ajena", async () => {
    overview.mockResolvedValue({
      users: USERS,
      total: 2,
      active_count: 2,
      registration_open: true,
    });
    patchUser.mockResolvedValue({ ...USERS[1], is_active: false });

    render(<AdminPanel me={{ id: 1, email: "admin@x.com", name: "Admin", is_active: true, is_admin: true }} onClose={() => {}} />);

    const user = await screen.findByText("user@x.com");
    const row = user.closest(".admin-user") as HTMLElement;
    await userEvent.click(within(row).getByText("Desactivar"));
    await waitFor(() => expect(patchUser).toHaveBeenCalledWith(2, { is_active: false }));
  });
});

// Tests del panel de equipos (crear, invitar, salir/disolver).
// Corre con:  pnpm test

import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import TeamsPanel from "./pages/TeamsPanel";

const listTeams = vi.fn();
const createTeam = vi.fn();
const teamDetailFn = vi.fn();
const addTeamMemberFn = vi.fn();
const deleteTeamFn = vi.fn();
const leaveTeamFn = vi.fn();

vi.mock("./lib/api", () => ({
  listTeams: () => listTeams(),
  createTeam: (...a: unknown[]) => createTeam(...(a as [])),
  teamDetail: (...a: unknown[]) => teamDetailFn(...(a as [])),
  addTeamMember: (...a: unknown[]) => addTeamMemberFn(...(a as [])),
  removeTeamMember: vi.fn(),
  deleteTeam: (...a: unknown[]) => deleteTeamFn(...(a as [])),
  leaveTeam: (...a: unknown[]) => leaveTeamFn(...(a as [])),
}));

const ME = { id: 1, email: "owner@x.com", name: "Owner", is_active: true, is_admin: true };

describe("TeamsPanel", () => {
  it("crea un equipo y muestra el formulario de invitación", async () => {
    listTeams.mockResolvedValue([
      { id: 7, name: "Postproducción", owner_id: 1, role: "owner", member_count: 1 },
    ]);
    createTeam.mockResolvedValue({
      id: 9, name: "Color & Sound", owner_id: 1, role: "owner", member_count: 1,
    });
    teamDetailFn.mockResolvedValue({
      id: 9, name: "Color & Sound", owner_id: 1, role: "owner",
      members: [{ user_id: 1, email: "owner@x.com", name: "Owner", role: "owner", is_active: true }],
    });

    render(<TeamsPanel me={ME} onClose={() => {}} />);

    await screen.findByText("Postproducción");
    await userEvent.type(screen.getByPlaceholderText(/Nombre del equipo/), "Color & Sound");
    await userEvent.click(screen.getByRole("button", { name: "Crear equipo" }));

    await waitFor(() => expect(createTeam).toHaveBeenCalledWith("Color & Sound"));
    expect(await screen.findByText(/Miembros de «Color & Sound»/)).toBeTruthy();
    // el owner puede invitar: aparece el campo de correo
    expect(screen.getByPlaceholderText(/usuario registrado/)).toBeTruthy();
  });

  it("un member solo puede salir del equipo (no disolverlo)", async () => {
    listTeams.mockResolvedValue([
      { id: 7, name: "Postproducción", owner_id: 99, role: "member", member_count: 4 },
    ]);

    render(<TeamsPanel me={{ ...ME, id: 2, email: "mate@x.com" }} onClose={() => {}} />);

    const row = (await screen.findByText("Postproducción")).closest(".admin-user") as HTMLElement;
    expect(within(row).getByText("Salir")).toBeTruthy();
    expect(within(row).queryByText("Disolver")).toBeNull();
  });
});

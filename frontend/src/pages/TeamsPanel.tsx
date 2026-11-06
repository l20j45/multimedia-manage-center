import { useCallback, useEffect, useState } from "react";
import {
  addTeamMember,
  createTeam,
  deleteTeam,
  leaveTeam,
  listTeams,
  removeTeamMember,
  teamDetail,
  type Team,
  type TeamDetail,
  type User,
} from "../lib/api";

/** Panel de equipos: crear, invitar, quitar, salir o disolver. */
export default function TeamsPanel({ me, onClose }: { me: User; onClose: () => void }) {
  const [teams, setTeams] = useState<Team[]>([]);
  const [openTeam, setOpenTeam] = useState<TeamDetail | null>(null);
  const [newTeamName, setNewTeamName] = useState("");
  const [inviteEmail, setInviteEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const list = await listTeams();
      setTeams(list);
      if (openTeam) {
        try {
          setOpenTeam(await teamDetail(openTeam.id));
        } catch {
          setOpenTeam(null); // lo disolvieron o me salí: cierro detalle
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar equipos");
    }
  }, [openTeam]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    setBusy(true);
    try {
      const team = await createTeam(newTeamName.trim());
      setNewTeamName("");
      setMsg(`Equipo «${team.name}» creado`);
      await load();
      setOpenTeam(await teamDetail(team.id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo crear el equipo");
    } finally {
      setBusy(false);
    }
  }

  async function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!openTeam) return;
    setError("");
    setMsg("");
    setBusy(true);
    try {
      const member = await addTeamMember(openTeam.id, inviteEmail.trim());
      setInviteEmail("");
      setMsg(`Invitado: ${member.email}`);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo invitar");
    } finally {
      setBusy(false);
    }
  }

  async function act(fn: () => Promise<unknown>, ok: string) {
    setError("");
    setMsg("");
    setBusy(true);
    try {
      await fn();
      setMsg(ok);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo completar la acción");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="card admin-card" onClick={(e) => e.stopPropagation()}>
      <h2>👥 Equipos</h2>
      <p className="sub">
        Crea equipos y comparte tus recursos con ellos (los subidos con visibilidad
        «equipo» se ven solo entre compañeros de equipo).
      </p>

      <form className="team-create" onSubmit={handleCreate}>
        <input
          placeholder="Nombre del equipo (ej. Postproducción)"
          value={newTeamName}
          maxLength={120}
          required
          onChange={(e) => setNewTeamName(e.target.value)}
        />
        <button className="primary" disabled={busy || !newTeamName.trim()}>
          Crear equipo
        </button>
      </form>

      {msg && <p className="ok">{msg}</p>}
      {error && <p className="error">{error}</p>}

      {teams.length === 0 && !openTeam && (
        <p className="sub">Aún no perteneces a ningún equipo. Crea el primero arriba 👆</p>
      )}

      <div className="admin-user-list">
        {teams.map((t) => (
          <div className="admin-user" key={t.id}>
            <div className="admin-user-info">
              <button
                type="button"
                className="team-name"
                onClick={async () => {
                  setError("");
                  try {
                    setOpenTeam(await teamDetail(t.id));
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "No se pudo abrir el equipo");
                  }
                }}
              >
                {t.name}
              </button>
              <span className="admin-user-sub">
                {t.member_count} miembro(s) · {t.role === "owner" ? "dueño" : "miembro"}
              </span>
            </div>
            <div className="admin-user-actions">
              {t.role === "owner" ? (
                <button
                  className="link tiny danger"
                  type="button"
                  disabled={busy}
                  onClick={() =>
                    act(
                      () => deleteTeam(t.id),
                      `Equipo «${t.name}» disuelto (tus recursos siguen intactos)`,
                    )
                  }
                >
                  Disolver
                </button>
              ) : (
                <button
                  className="link tiny"
                  type="button"
                  disabled={busy}
                  onClick={() => act(() => leaveTeam(t.id), `Saliste de «${t.name}»`)}
                >
                  Salir
                </button>
              )}
            </div>
          </div>
        ))}
      </div>

      {openTeam && (
        <div className="detail-section">
          <p className="snav-label">Miembros de «{openTeam.name}»</p>
          {openTeam.members.map((m) => (
            <div className="admin-user" key={m.user_id}>
              <div className="admin-user-info">
                <span className="admin-user-email">
                  {m.email}
                  {m.role === "owner" && <span className="chip chip-admin">dueño</span>}
                  {m.user_id === me.id && <span className="chip chip-off">tú</span>}
                </span>
                <span className="admin-user-sub">{m.name ?? "sin nombre"}</span>
              </div>
              <div className="admin-user-actions">
                {openTeam.role === "owner" && m.role !== "owner" && (
                  <button
                    className="link tiny danger"
                    type="button"
                    disabled={busy}
                    onClick={() =>
                      act(
                        () => removeTeamMember(openTeam.id, m.user_id),
                        `${m.email} quitado del equipo`,
                      )
                    }
                  >
                    Quitar
                  </button>
                )}
              </div>
            </div>
          ))}
          {openTeam.role === "owner" && (
            <form className="team-create" onSubmit={handleInvite}>
              <input
                type="email"
                placeholder="correo de un usuario registrado"
                value={inviteEmail}
                required
                onChange={(e) => setInviteEmail(e.target.value)}
              />
              <button className="ghost" disabled={busy}>
                Invitar
              </button>
            </form>
          )}
        </div>
      )}

      <div className="row">
        <button className="primary" type="button" onClick={onClose}>
          Cerrar
        </button>
      </div>
    </main>
  );
}

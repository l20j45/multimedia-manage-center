import { useCallback, useEffect, useState } from "react";
import {
  adminOverview,
  adminPatchUser,
  adminSetRegistration,
  type AdminUser,
  type User,
} from "../lib/api";

/** Panel de administración (solo super admin): usuarios + toggle de registro. */
export default function AdminPanel({ me, onClose }: { me: User; onClose: () => void }) {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [activeCount, setActiveCount] = useState(0);
  const [regOpen, setRegOpen] = useState(true);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const overview = await adminOverview();
      setUsers(overview.users);
      setTotal(overview.total);
      setActiveCount(overview.active_count);
      setRegOpen(overview.registration_open);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar la administración");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function toggleRegistration() {
    setMsg("");
    try {
      const res = await adminSetRegistration(!regOpen);
      setRegOpen(res.open);
      setMsg(res.open ? "Registro abierto" : "Registro cerrado");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar el registro");
    }
  }

  async function patch(user: AdminUser, data: { is_active?: boolean; is_admin?: boolean }) {
    setMsg("");
    try {
      const updated = await adminPatchUser(user.id, data);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setActiveCount((n) => n + (data.is_active === false ? -1 : data.is_active === true ? 1 : 0));
      setMsg(`Cuenta actualizada: ${updated.email}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo actualizar la cuenta");
    }
  }

  return (
    <main className="card admin-card" onClick={(e) => e.stopPropagation()}>
      <h2>🛡 Administración</h2>
      <p className="sub">Gestión de la instalación para {me.email}</p>

      <div className="admin-stat-row">
        <div className="admin-stat">
          <span className="admin-stat-num">{total}</span>
          <span className="admin-stat-label">usuarios</span>
        </div>
        <div className="admin-stat">
          <span className="admin-stat-num">{activeCount}</span>
          <span className="admin-stat-label">activos</span>
        </div>
        <button
          className={`ghost ${regOpen ? "" : "danger"}`}
          onClick={toggleRegistration}
          title="Permite o bloquea crear cuentas nuevas desde la pantalla de login"
        >
          {regOpen ? "🔓 Registro: abierto" : "🔒 Registro: cerrado"} — cambiar
        </button>
      </div>
      {msg && <p className="ok">{msg}</p>}
      {error && <p className="error">{error}</p>}

      <div className="admin-user-list">
        {loading && <p className="loading">Cargando usuarios…</p>}
        {users.map((u) => (
          <div className="admin-user" key={u.id}>
            <div className="admin-user-info">
              <span className="admin-user-email">
                {u.email}
                {u.is_admin && <span className="chip chip-admin">admin</span>}
                {!u.is_active && <span className="chip chip-off">inactivo</span>}
              </span>
              <span className="admin-user-sub">
                {u.name ?? "sin nombre"} · {createdOn(u.created_at)}
              </span>
            </div>
            <div className="admin-user-actions">
              {u.id !== me.id && (
                <button
                  className="link tiny"
                  type="button"
                  onClick={() => patch(u, { is_active: !u.is_active })}
                >
                  {u.is_active ? "Desactivar" : "Activar"}
                </button>
              )}
              <button
                className="link tiny"
                type="button"
                disabled={u.is_admin && totalAdmins(users) === 1}
                title={
                  u.is_admin && totalAdmins(users) === 1
                    ? "Debe quedar al menos un admin"
                    : u.is_admin
                      ? "Retira el rol de super admin"
                      : "Convierte en super admin"
                }
                onClick={() => patch(u, { is_admin: !u.is_admin })}
              >
                {u.is_admin ? "Quitar admin" : "Hacer admin"}
              </button>
            </div>
          </div>
        ))}
      </div>

      <div className="row">
        <button className="primary" type="button" onClick={onClose}>
          Cerrar
        </button>
      </div>
    </main>
  );
}

function totalAdmins(users: AdminUser[]): number {
  return users.filter((u) => u.is_admin).length;
}

function createdOn(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

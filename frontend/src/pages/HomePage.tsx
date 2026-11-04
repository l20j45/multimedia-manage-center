import { useState } from "react";
import { updateMe, type User } from "../lib/api";

export default function HomePage({
  user,
  onChange,
  onLogout,
}: {
  user: User;
  onChange: (user: User) => void;
  onLogout: () => void;
}) {
  const [name, setName] = useState(user.name ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setBusy(true);
    try {
      onChange(await updateMe(name));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="home">
      <header className="topbar">
        <h1>Biblioteca de Recursos Multimedia</h1>
        <button className="ghost" onClick={onLogout}>
          Cerrar sesión
        </button>
      </header>

      <main className="content">
        <div className="card">
          <h2>¡Hola{name ? `, ${name}` : ""}!</h2>
          <p className="sub">Sesión iniciada como {user.email}</p>

          <form onSubmit={handleSave}>
            <p className="label">Nombre</p>
            <input
              placeholder="Tu nombre"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            {error && <p className="error">{error}</p>}
            <button className="primary" disabled={busy}>
              {busy ? "Guardando..." : "Guardar"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}

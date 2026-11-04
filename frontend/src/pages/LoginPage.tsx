import { useState } from "react";
import { forgotPassword, login, register, resetPassword, type User } from "../lib/api";

type Mode = "login" | "register" | "forgot";

export default function LoginPage({ onLoggedIn }: { onLoggedIn: (user: User) => void }) {
  const [mode, setMode] = useState<Mode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [info, setInfo] = useState("");
  const [remember, setRemember] = useState(true);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInfo("");
    setBusy(true);
    try {
      if (mode === "forgot") {
        if (!code) {
          // Paso 1: pedir el código (válido 30 min, un solo uso)
          await forgotPassword(email);
          setInfo(`Si ${email} está registrado, te enviamos un código de 6 dígitos.`);
        } else {
          // Paso 2: código + nueva contraseña
          await resetPassword(email, code, password);
          setMode("login");
          setCode("");
          setEmail("");
          setPassword("");
          setInfo("Contraseña actualizada. Inicia sesión con la nueva.");
        }
      } else if (mode === "register") {
        const created = await register(email, name, password);
        setInfo(`¡Cuenta creada para ${created.email}! Ya puedes iniciar sesión.`);
        setMode("login");
      } else {
        await onLoggedIn(
          await login(
            email,
            password,
            remember,
          ),
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setBusy(false);
    }
  }

  function switchMode(next: Mode) {
    setMode(next);
    setCode("");
    setError("");
    setInfo("");
  }

  return (
    <div className="card auth-card">
      <h1>Biblioteca de Recursos Multimedia</h1>
      <p className="sub">Inicia sesión o crea tu cuenta</p>

      <div className="tabs">
        <button className={mode === "login" ? "active" : ""} onClick={() => switchMode("login")}>
          Iniciar sesión
        </button>
        <button className={mode === "register" ? "active" : ""} onClick={() => switchMode("register")}>
          Crear cuenta
        </button>
      </div>

      <form onSubmit={handleSubmit}>
        {mode === "register" && (
          <input
            placeholder="Nombre (opcional)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        )}
        <input
          type="email"
          required
          placeholder="Correo electrónico"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        {mode === "forgot" ? (
          <input
            inputMode="numeric"
            pattern="\d{6}"
            maxLength={6}
            placeholder="Código de 6 dígitos (opcional)"
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          />
        ) : (
          <input
            type="password"
            required
            placeholder={mode === "register" ? "Contraseña (mín. 8)" : "Contraseña"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        )}
        {error && <p className="error">{error}</p>}
        {info && <p className="ok">{info}</p>}
        {mode === "login" && (
          <label className="remember-row">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
            />
            Recordarme 30 días
          </label>
        )}
        <button className="primary" disabled={busy}>
          {busy
            ? "Enviando..."
            : mode === "login"
              ? "Entrar"
              : mode === "register"
                ? "Crear cuenta"
                : code
                  ? "Guardar nueva contraseña"
                  : "Enviar código"}
        </button>
      </form>

      {mode === "login" && (
        <button className="link" type="button" onClick={() => switchMode("forgot")}>
          ¿Olvidaste tu contraseña?
        </button>
      )}
      {mode === "forgot" && (
        <button className="link" type="button" onClick={() => switchMode("login")}>
          Volver a iniciar sesión
        </button>
      )}
    </div>
  );
}

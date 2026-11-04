import { useEffect, useState } from "react";
import { clearToken, getMe, getToken, type User } from "./lib/api";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/HomePage";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(getToken() !== null);

  // Al abrir la app: si hay token guardado, valida la sesión contra el backend
  useEffect(() => {
    if (!getToken()) return;
    getMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setChecking(false));
  }, []);

  if (checking) {
    return <p className="loading">Cargando…</p>;
  }

  return user ? (
    <HomePage
      user={user}
      onChange={setUser}
      onLogout={() => {
        clearToken();
        setUser(null);
      }}
    />
  ) : (
    <LoginPage onLoggedIn={setUser} />
  );
}

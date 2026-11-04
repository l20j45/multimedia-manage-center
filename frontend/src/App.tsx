import { useEffect, useState } from "react";
import { clearToken, getMe, getToken, type User } from "./lib/api";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/HomePage";
import PublicCollectionPage from "./pages/PublicCollection";

// Ruta pública /share/<token>: NO exige sesión (colección compartida).
const shareMatch = window.location.pathname.match(/^\/share\/([A-Za-z0-9_-]+)/);

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(getToken() !== null);

  useEffect(() => {
    if (shareMatch) return; // la vista pública no valida login
    if (!getToken()) return;
    getMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setChecking(false));
  }, []);

  if (shareMatch) {
    return <PublicCollectionPage token={shareMatch[1]} />;
  }

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

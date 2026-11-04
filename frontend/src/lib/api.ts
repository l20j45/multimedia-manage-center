// Cliente HTTP hacia el backend FastAPI.
// URL externa (http://localhost) en dev; dentro de Tauri la ventana sirve la UI.

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export interface User {
  id: number;
  email: string;
  name: string | null;
  is_active: boolean;
}

const TOKEN_KEY = "token";

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.body) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error((data as { detail?: string }).detail ?? `Error ${res.status}`);
  }
  return data as T;
}

export function register(email: string, name: string, password: string): Promise<User> {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, name: name || null, password }),
  });
}

export async function login(email: string, password: string): Promise<User> {
  const form = new URLSearchParams({ username: email, password });
  const data = await request<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: form.toString(),
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
  });
  saveToken(data.access_token);
  return getMe();
}

export function getMe(): Promise<User> {
  return request("/auth/me");
}

export function updateMe(name: string): Promise<User> {
  return request("/users/me", {
    method: "PATCH",
    body: JSON.stringify({ name }),
  });
}

export function forgotPassword(email: string): Promise<void> {
  return request("/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(email: string, code: string, newPassword: string): Promise<void> {
  return request("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ email, code, new_password: newPassword }),
  });
}

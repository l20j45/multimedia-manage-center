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

// ---------------------------------------------------------------- media
export type MediaKind = "audio" | "image" | "video";

export interface MediaItem {
  id: number;
  kind: MediaKind;
  title: string;
  tags: string[];
  filename: string;
  path: string;
  mime: string;
  size: number;
  duration_s: number | null;
  has_thumb: boolean;
  created_at: string;
}

export interface MediaList {
  items: MediaItem[];
  total: number;
}

export function listMedia(
  params: { q?: string; kind?: MediaKind; tag?: string; limit?: number; offset?: number } = {},
): Promise<MediaList> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.kind) search.set("kind", params.kind);
  if (params.tag) search.set("tag", params.tag);
  if (params.limit) search.set("limit", String(params.limit));
  if (params.offset) search.set("offset", String(params.offset));
  const qs = search.toString();
  return request(`/media${qs ? `?${qs}` : ""}`);
}

/** Sube con FormData (el fetch no debe poner Content-Type: lo fija el navegador). */
export function uploadMedia(
  file: File,
  title: string,
  tagsCsv: string,
): Promise<MediaItem> {
  const form = new FormData();
  form.append("file", file);
  form.append("title", title);
  form.append("tags", tagsCsv);
  const token = getToken();
  return fetch(`${API_BASE}/media`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  }).then(async (res) => {
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error((data as { detail?: string }).detail ?? `Error ${res.status}`);
    return data as MediaItem;
  });
}

export function updateMedia(
  id: number,
  data: { title?: string; tags?: string[] },
): Promise<MediaItem> {
  return request(`/media/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

export function deleteMedia(id: number): Promise<void> {
  return request(`/media/${id}`, { method: "DELETE" });
}

export function listTags(): Promise<{ tag: string; count: number }[]> {
  return request("/media/tags");
}

/** URL del fichero/thumbnail con el token en query (los <img>/<video> no mandan header). */
export function mediaUrl(id: number, what: "file" | "thumb" = "file"): string {
  const token = getToken() ?? "";
  return `${API_BASE}/media/${id}/${what}?access_token=${encodeURIComponent(token)}`;
}

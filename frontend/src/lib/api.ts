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
  params: {
    q?: string;
    kind?: MediaKind;
    tag?: string;
    collection?: number;
    limit?: number;
    offset?: number;
  } = {},
): Promise<MediaList> {
  const search = new URLSearchParams();
  if (params.q) search.set("q", params.q);
  if (params.kind) search.set("kind", params.kind);
  if (params.tag) search.set("tag", params.tag);
  if (params.collection) search.set("collection", String(params.collection));
  if (params.limit) search.set("limit", String(params.limit));
  if (params.offset) search.set("offset", String(params.offset));
  const qs = search.toString();
  return request(`/media${qs ? `?${qs}` : ""}`);
}

/** Sube con FormData + XHR (para reportar progreso; el navegador fija Content-Type). */
export function uploadMedia(
  file: File,
  title: string,
  tagsCsv: string,
  onProgress?: (pct: number) => void,
): Promise<MediaItem> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("tags", tagsCsv);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE}/media`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    };
    xhr.onload = () => {
      const data = JSON.parse(xhr.responseText || "{}") as MediaItem & { detail?: string };
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new Error(data.detail ?? `Error ${xhr.status}`));
    };
    xhr.onerror = () => reject(new Error("Error de red al subir"));
    xhr.send(form);
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

// ---------------------------------------------------------------- colecciones
export interface Collection {
  id: number;
  name: string;
  item_count: number;
}

export function listCollections(): Promise<Collection[]> {
  return request("/collections");
}

export function createCollection(name: string): Promise<Collection> {
  return request("/collections", { method: "POST", body: JSON.stringify({ name }) });
}

export function deleteCollection(id: number): Promise<void> {
  return request(`/collections/${id}`, { method: "DELETE" });
}

export function collectionItems(id: number): Promise<MediaItem[]> {
  return request(`/collections/${id}/items`);
}

export function addCollectionItem(id: number, mediaId: number): Promise<Collection> {
  return request(`/collections/${id}/items`, {
    method: "POST",
    body: JSON.stringify({ media_id: mediaId }),
  });
}

export function removeCollectionItem(id: number, mediaId: number): Promise<void> {
  return request(`/collections/${id}/items/${mediaId}`, { method: "DELETE" });
}

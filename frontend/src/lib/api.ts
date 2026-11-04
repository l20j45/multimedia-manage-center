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
  // Headers del caller primero; request() solo AÑADE (no pisa) Content-Type
  // ni Authorization: el login necesita application/x-www-form-urlencoded y
  // el resto JSON (#bug 422 en /auth/login cuando el caller sobreescribía).
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (options.body && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401 && !path.startsWith("/auth") && !path.startsWith("/media/public")) {
    // sesión expirada: fuera tokens y de vuelta al login
    clearToken();
    window.location.assign("/");
    return new Promise<T>(() => {}); // no resolvemos durante el redirect
  }
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
  description: string;
  meta: Record<string, string> | null;
  filename: string;
  path: string;
  mime: string;
  size: number;
  duration_s: number | null;
  has_thumb: boolean;
  visibility: "private" | "team";
  rating: number;
  deleted: boolean;
  created_at: string;
}

export interface MediaList {
  items: MediaItem[];
  total: number;
}

export interface MediaQuery {
  q?: string;
  kind?: MediaKind;
  tag?: string | null;
  tag_no?: string | null;
  collection?: number | null;
  scope?: "mine" | "team";
  order?: "created" | "title" | "size" | "duration" | "rating";
  direction?: "asc" | "desc";
  since?: string | null;
  until?: string | null;
  min_rating?: number | null;
  trash?: boolean;
  limit?: number;
  offset?: number;
}

export function listMedia(params: MediaQuery = {}): Promise<MediaList> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === false) continue;
    search.set(k, String(v));
  }
  const qs = search.toString();
  return request(`/media${qs ? `?${qs}` : ""}`);
}

/** Sube con FormData + XHR (para reportar progreso; el navegador fija Content-Type). */
export function uploadMedia(
  file: File,
  title: string,
  tagsCsv: string,
  onProgress?: (pct: number) => void,
  extra: { description?: string; visibility?: "private" | "team" } = {},
): Promise<MediaItem> {
  return new Promise((resolve, reject) => {
    const form = new FormData();
    form.append("file", file);
    form.append("title", title);
    form.append("tags", tagsCsv);
    if (extra.description) form.append("description", extra.description);
    if (extra.visibility) form.append("visibility", extra.visibility);

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
  data: {
    title?: string;
    tags?: string[];
    description?: string;
    meta?: Record<string, string>;
    visibility?: "private" | "team";
    rating?: number;
  },
): Promise<MediaItem> {
  return request(`/media/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

/** Corta [start→end] de un clip (sin re-subir) y devuelve el recurso nuevo. */
export function trimMedia(
  id: number,
  start: number,
  end: number | null,
  title?: string,
  tags?: string[],
): Promise<MediaItem> {
  return request(`/media/${id}/trim`, {
    method: "POST",
    body: JSON.stringify({ start, end, title: title || undefined, tags: tags || undefined }),
  });
}

export function deleteMedia(id: number): Promise<void> {
  return request(`/media/${id}`, { method: "DELETE" });
}

/** Extrae la pista de audio de un VIDEO → mp3 nuevo. Para el flujo SFX. */
export function extractAudio(id: number): Promise<MediaItem> {
  return request(`/media/${id}/extract-audio`, { method: "POST" });
}

/** Pide sugerencias de tags (IA/heurística). NO aplica nada por sí sola. */
export function getAutotagSuggestions(id: number): Promise<{ suggestions: string[]; source: string }> {
  return request(`/media/${id}/autotag`, { method: "POST" });
}

export function bulkMedia(
  ids: number[],
  action:
    | "add_tag"
    | "remove_tag"
    | "set_visibility"
    | "delete"
    | "restore"
    | "purge"
    | "add_to_collection"
    | "rename",
  extra: { tags?: string[]; visibility?: "private" | "team"; collection_id?: number; pattern?: string } = {},
): Promise<{ done: number; requested: number }> {
  return request("/media/bulk", {
    method: "POST",
    body: JSON.stringify({ ids, action, ...extra }),
  });
}

export function restoreMedia(id: number): Promise<MediaItem> {
  return request(`/media/${id}/restore`, { method: "POST" });
}

export function purgeMedia(id: number): Promise<void> {
  return request(`/media/${id}/purge`, { method: "DELETE" });
}

export function listDuplicates(): Promise<{ groups: MediaItem[][] }> {
  return request("/media/duplicates");
}

export function rethumbMedia(id: number, atSeconds: number): Promise<MediaItem> {
  return request(`/media/${id}/rethumb`, { method: "POST", body: JSON.stringify({ at: atSeconds }) });
}

export function exportUrl(id: number, format: "txt" | "csv" = "txt"): string {
  const token = getToken() ?? "";
  return `${API_BASE}/collections/${id}/export?format=${format}&access_token=${encodeURIComponent(token)}`;
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
  is_project: boolean;
}

export function listCollections(): Promise<Collection[]> {
  return request("/collections");
}

export function createCollection(name: string, isProject = false): Promise<Collection> {
  return request("/collections", { method: "POST", body: JSON.stringify({ name, is_project: isProject }) });
}

export function updateCollection(id: number, data: { name?: string; is_project?: boolean }): Promise<Collection> {
  return request(`/collections/${id}`, { method: "PATCH", body: JSON.stringify(data) });
}

// ---------------------------------------------------------------- compartir
export interface ShareResult {
  token: string;
  url: string;
}

export function createShare(id: number): Promise<ShareResult> {
  return request(`/collections/${id}/share`, { method: "POST" });
}

export function revokeShare(id: number): Promise<void> {
  return request(`/collections/${id}/share`, { method: "DELETE" });
}

export interface PublicCollection {
  name: string;
  is_project: boolean;
  items: MediaItem[];
}

export function fetchPublicCollection(token: string): Promise<PublicCollection> {
  return request(`/media/public/${encodeURIComponent(token)}`);
}

/** URL de fichero/thumbnail accesible para VISITANTES del enlace compartido. */
export function publicMediaUrl(id: number, shareToken: string, what: "file" | "thumb" = "file"): string {
  return `${API_BASE}/media/${id}/${what}?share=${encodeURIComponent(shareToken)}`;
}

/** Enlace compartible completo para el visitante (la app sirve /share/...). */
export function shareLink(url: string): string {
  return `${window.location.origin}${url}`;
}

export function deleteCollection(id: number): Promise<void> {
  return request(`/collections/${id}`, { method: "DELETE" });
}

export function collectionItems(id: number): Promise<MediaItem[]> {
  return request(`/collections/${id}/items`);
}

/** URL para descargar la colección completa como .zip (ficheros reales). */
export function exportZipUrl(id: number): string {
  const token = getToken() ?? "";
  return `${API_BASE}/collections/${id}/export-zip?access_token=${encodeURIComponent(token)}`;
}

export interface StatOut {
  by_kind: Record<string, { count: number; size: number }>;
  top_tags: { tag: string; count: number }[];
  months: { month: string; count: number }[];
  total_size: number;
  trash_count: number;
}

export function fetchStats(): Promise<StatOut> {
  return request("/media/stats/overview");
}

// ---------------------------------------------------------------- llave IA
export function getGeminiKeyStatus(): Promise<{ set: boolean; tail: string; source: string }> {
  return request("/settings/gemini-key");
}

export function setGeminiKey(value: string): Promise<{ set: boolean; tail: string; source: string }> {
  return request("/settings/gemini-key", { method: "PUT", body: JSON.stringify({ value }) });
}

/** Busca un recurso propio por sha256 del contenido (anti-dup al pegar). */
export async function findByHash(sha256: string): Promise<MediaItem | null> {
  try {
    return await request(`/media/by-hash/${sha256}`);
  } catch {
    return null;
  }
}

export async function sha256OfFile(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
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

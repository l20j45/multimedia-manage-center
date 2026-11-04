import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addCollectionItem,
  bulkMedia,
  createCollection,
  deleteMedia,
  exportUrl,
  listCollections,
  listDuplicates,
  listMedia,
  listTags,
  mediaUrl,
  purgeMedia,
  removeCollectionItem,
  restoreMedia,
  rethumbMedia,
  updateMe,
  updateMedia,
  uploadMedia,
  type Collection,
  type MediaItem,
  type MediaKind,
  type MediaQuery,
  type User,
} from "../lib/api";

type TabKey = "all" | MediaKind | "trash";

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: "all", label: "Todos", icon: "🗂" },
  { key: "audio", label: "Audio", icon: "🎵" },
  { key: "image", label: "Imágenes", icon: "🖼" },
  { key: "video", label: "Vídeos", icon: "🎬" },
  { key: "trash", label: "Papelera", icon: "🗑" },
];

const KIND_ICON: Record<MediaKind, string> = { audio: "🎵", image: "🖼", video: "🎬" };
const PAGE_SIZE = 30;

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const units = ["KB", "MB", "GB"];
  let v = bytes / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v < 10 ? 1 : 0)} ${units[i]}`;
}

function fmtDuration(seconds: number | null): string {
  if (seconds === null) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function HomePage({
  user,
  onChange,
  onLogout,
}: {
  user: User;
  onChange: (user: User) => void;
  onLogout: () => void;
}) {
  const [tab, setTab] = useState<TabKey>("all");
  const [query, setQuery] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [tagChips, setTagChips] = useState<{ tag: string; count: number }[]>([]);
  const [items, setItems] = useState<MediaItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");

  // Filtros avanzados / vistas
  const [scope, setScope] = useState<"mine" | "team">("mine");
  const [order, setOrder] = useState<NonNullable<MediaQuery["order"]>>("created");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const [view, setView] = useState<"grid" | "list">("grid");

  // Subida
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"private" | "team">("private");
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [uploadMsg, setUploadMsg] = useState("");

  // Drag & drop de varios archivos
  const [dragging, setDragging] = useState(false);
  const [bulkMsg, setBulkMsg] = useState("");

  // Colecciones
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCol, setSelectedCol] = useState<Collection | null>(null);
  const [colError, setColError] = useState("");
  const [addItemFor, setAddItemFor] = useState<MediaItem | null>(null);

  // Selección múltiple
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [bulkTagsText, setBulkTagsText] = useState("");
  const [bulkColId, setBulkColId] = useState<number | "">("");
  const [bulkBusy, setBulkBusy] = useState(false);

  // Edición / reproductor / duplicados
  const [editing, setEditing] = useState<MediaItem | null>(null);
  const [editDraft, setEditDraft] = useState({
    title: "",
    tags: "",
    description: "",
    camera: "",
    proyecto: "",
    visibility: "private" as "private" | "team",
  });
  const [playing, setPlaying] = useState<MediaItem | null>(null);
  const [dupesOpen, setDupesOpen] = useState(false);
  const [dupes, setDupes] = useState<MediaItem[][]>([]);

  // Perfil
  const [profileOpen, setProfileOpen] = useState(false);
  const [name, setName] = useState(user.name ?? "");
  const [busy, setBusy] = useState(false);
  const [profileError, setProfileError] = useState("");

  const fileInput = useRef<HTMLInputElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);

  /* ------------------------------------------------------ carga de datos */
  const queryBase = useMemo(
    () => ({
      q: debouncedQ || undefined,
      tag: activeTag ?? undefined,
      scope,
      order,
      direction,
      kind: (tab === "all" || tab === "trash" ? undefined : tab) as
        | MediaKind
        | undefined,
    }),
    [debouncedQ, activeTag, scope, order, direction, tab],
  );

  const loadItems = useCallback(
    async (offset = 0, replace = true) => {
      const isTrash = tab === "trash";
      if (selectedCol) {
        // la vista de colección usa el filtro collection (papelera no aplica)
        const res = await listMedia({
          ...queryBase,
          collection: selectedCol.id,
          limit: PAGE_SIZE,
          offset,
        });
        setItems((prev) => (replace ? res.items : [...prev, ...res.items]));
        setTotal(res.total);
        return;
      }
      const res = await listMedia({
        ...queryBase,
        trash: isTrash,
        limit: PAGE_SIZE,
        offset,
      });
      setItems((prev) => (replace ? res.items : [...prev, ...res.items]));
      setTotal(res.total);
    },
    [queryBase, tab, selectedCol],
  );

  const loadTags = useCallback(async () => {
    try {
      setTagChips(await listTags());
    } catch {
      setTagChips([]);
    }
  }, []);

  const loadCollections = useCallback(async () => {
    try {
      setCollections(await listCollections());
    } catch {
      setCollections([]);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    loadItems(0, true)
      .catch((err: unknown) =>
        setListError(err instanceof Error ? err.message : "Error al cargar"),
      )
      .finally(() => setLoading(false));
    setSelectedIds(new Set());
  }, [loadItems]);

  useEffect(() => {
    loadTags();
    loadCollections();
  }, [loadTags, loadCollections]);

  // Debounce de búsqueda
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  const hasMore = items.length < total && !loading;

  const loadMore = useCallback(async () => {
    setLoading(true);
    try {
      await loadItems(items.length, false);
    } finally {
      setLoading(false);
    }
  }, [loadItems, items.length]);

  // Scroll infinito
  const sentinel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!sentinel.current || !hasMore) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) loadMore();
      },
      { rootMargin: "300px" },
    );
    io.observe(sentinel.current);
    return () => io.disconnect();
  }, [hasMore, loadMore]);

  /* ------------------------------------------------------------- helpers */
  const inTrash = tab === "trash";

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function openEdit(item: MediaItem) {
    setEditing(item);
    setEditDraft({
      title: item.title,
      tags: item.tags.join(", "),
      description: item.description ?? "",
      camera: item.meta?.camera ?? "",
      proyecto: item.meta?.proyecto ?? "",
      visibility: item.visibility ?? "private",
    });
  }

  async function handleSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    try {
      const tags = editDraft.tags.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
      const meta: Record<string, string> = {};
      if (editDraft.camera.trim()) meta.camera = editDraft.camera.trim();
      if (editDraft.proyecto.trim()) meta.proyecto = editDraft.proyecto.trim();
      await updateMedia(editing.id, {
        title: editDraft.title.trim() || editing.title,
        tags,
        description: editDraft.description,
        meta,
        visibility: editDraft.visibility,
      });
      setEditing(null);
      await Promise.all([loadItems(0, true), loadTags()]);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al editar");
    }
  }

  async function handleDelete(item: MediaItem) {
    if (!window.confirm(`¿Enviar "${item.title}" a la papelera?`)) return;
    try {
      await deleteMedia(item.id);
      await Promise.all([loadItems(0, true), loadTags()]);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al eliminar");
    }
  }

  async function handlePurge(item: MediaItem) {
    if (!window.confirm(`¿Borrar DEFINITIVAMENTE "${item.title}"? No se puede deshacer.`)) return;
    try {
      await purgeMedia(item.id);
      await loadItems(0, true);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al purgar");
    }
  }

  async function handleRestore(item: MediaItem) {
    try {
      await restoreMedia(item.id);
      await Promise.all([loadItems(0, true), loadTags()]);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al restaurar");
    }
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploadMsg("");
    setUploading(true);
    setUploadPct(0);
    try {
      await uploadMedia(file, title, tagsText, setUploadPct, { description, visibility });
      setFile(null);
      setTitle("");
      setTagsText("");
      setDescription("");
      if (fileInput.current) fileInput.current.value = "";
      setUploadOpen(false);
      await Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
    } catch (err) {
      setUploadMsg(err instanceof Error ? err.message : "Error al subir");
    } finally {
      setUploading(false);
    }
  }

  async function handleDropped(e: React.DragEvent) {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer?.files ?? []);
    if (files.length === 0) return;
    if (files.length === 1) {
      setFile(files[0]);
      setTitle(files[0].name.replace(/\.[^.]+$/, ""));
      setUploadOpen(true);
      return;
    }
    setBulkMsg("");
    let done = 0;
    let failed = 0;
    for (const f of files) {
      try {
        await uploadMedia(f, f.name.replace(/\.[^.]+$/, ""), "", undefined, { visibility });
        done += 1;
      } catch {
        failed += 1;
      }
    }
    setBulkMsg(failed === 0 ? `${done} archivo(s) subidos.` : `${done} subidos · ${failed} fallidos.`);
    await Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
  }

  /* ------------------------------------------------------------ bulk bar */
  async function runBulk(
    action: "add_tag" | "remove_tag" | "set_visibility" | "add_to_collection" | "delete" | "restore" | "purge",
  ) {
    setBulkBusy(true);
    setBulkMsg("");
    try {
      const extra: Record<string, unknown> = {};
      if (action === "add_tag" || action === "remove_tag") {
        extra.tags = bulkTagsText.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
      }
      if (action === "add_to_collection") {
        if (!bulkColId) return;
        extra.collection_id = bulkColId;
      }
      const res = await bulkMedia([...selectedIds], action, extra);
      setBulkMsg(`${res.done} procesado(s).`);
      setSelectedIds(new Set());
      setBulkTagsText("");
      await Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
    } catch (err) {
      setBulkMsg(err instanceof Error ? err.message : "Error en la operación en lote");
    } finally {
      setBulkBusy(false);
    }
  }

  /* --------------------------------------------------------- colecciones */
  async function handleCreateCollection() {
    const name = window.prompt("Nombre de la nueva colección/edición:");
    if (!name || !name.trim()) return;
    const isProj = window.confirm("¿Es una EDICIÓN/proyecto (poder exportar lista)? Aceptar = Sí, Cancelar = Solo colección.");
    setColError("");
    try {
      const col = await createCollection(name.trim(), isProj);
      setCollections((prev) => [...prev, col].sort((a, b) => a.name.localeCompare(b.name)));
      if (selectedCol) setBulkColId(col.id);
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al crear la colección");
    }
  }

  async function handleRemoveFromCollection(item: MediaItem) {
    if (!selectedCol) return;
    setColError("");
    try {
      await removeCollectionItem(selectedCol.id, item.id);
      const updated = { ...selectedCol, item_count: Math.max(0, selectedCol.item_count - 1) };
      setSelectedCol(updated);
      setCollections((prev) =>
        prev.map((c) => (c.id === updated.id ? { ...c, item_count: updated.item_count } : c)),
      );
      await loadItems(0, true);
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al quitar de la colección");
    }
  }

  async function handleAddToCollection(item: MediaItem, col: Collection) {
    setColError("");
    try {
      const updated = await addCollectionItem(col.id, item.id);
      setCollections((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      setAddItemFor(null);
      await Promise.all([loadTags(), loadCollections()]);
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al agregar a la colección");
    }
  }

  /* ------------------------------------------------------------ duplicados */
  async function openDuplicates() {
    try {
      const res = await listDuplicates();
      setDupes(res.groups);
      setDupesOpen(true);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al buscar duplicados");
    }
  }

  async function purgeAllButFirst(group: MediaItem[]) {
    const ids = group.slice(1).map((g) => g.id);
    if (!window.confirm(`¿Purgar ${ids.length} copia(s) y conservar solo "${group[0].title}"?`)) return;
    try {
      await bulkMedia(ids, "purge");
      const res = await listDuplicates();
      setDupes(res.groups);
      await Promise.all([loadItems(0, true), loadCollections()]);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al purgar duplicados");
    }
  }

  /* ------------------------------------------------------------- player */
  async function useThisFrame() {
    const v = videoRef.current;
    if (!v || !playing || playing.kind !== "video") return;
    try {
      const updated = await rethumbMedia(playing.id, v.currentTime);
      const merged = { ...playing, ...updated };
      setPlaying(merged);
      await loadItems(0, true);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al re-generar el poster");
    }
  }

  function playFrom(idx: number) {
    if (idx >= 0 && idx < items.length) setPlaying(items[idx]);
  }

  /* ----------------------------------------------------------- shortcuts */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT") {
        if (e.key === "Escape") (target as HTMLInputElement).blur();
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        searchInput.current?.focus();
        return;
      }
      if (e.key === "Escape") {
        if (addItemFor) setAddItemFor(null);
        else if (editing) setEditing(null);
        else if (profileOpen) setProfileOpen(false);
        else if (uploadOpen) setUploadOpen(false);
        else if (dupesOpen) setDupesOpen(false);
        else if (playing) setPlaying(null);
        else if (selectedIds.size) setSelectedIds(new Set());
        return;
      }
      if (playing && items.length > 1) {
        const idx = items.findIndex((i) => i.id === playing.id);
        if (e.key === "ArrowRight") playFrom(idx + 1);
        if (e.key === "ArrowLeft") playFrom(idx - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing, items, addItemFor, editing, profileOpen, uploadOpen, dupesOpen, selectedIds]);

  /* ------------------------------------------------------------ profile */
  async function handleSaveProfile(e: React.FormEvent) {
    e.preventDefault();
    setProfileError("");
    setBusy(true);
    try {
      onChange(await updateMe(name));
      setProfileOpen(false);
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "Error inesperado");
    } finally {
      setBusy(false);
    }
  }

  /* --------------------------------------------------------------- render */
  return (
    <div
      className="home"
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={handleDropped}
    >
      {dragging && (
        <div className="dropzone" aria-label="Zona de suelta de archivos">
          <p>Suelta tus archivos aquí</p>
          <p className="sub">1 archivo → revisa antes · varios → subida directa</p>
        </div>
      )}

      <header className="topbar">
        <h1>Biblioteca de Recursos Multimedia</h1>
        <div className="topbar-actions">
          <button className="ghost" onClick={openDuplicates} title="Buscar duplicados por contenido">
            👯 Duplicados
          </button>
          <button
            className="ghost"
            onClick={() => setView((v) => (v === "grid" ? "list" : "grid"))}
            title="Cambiar vista (grid/lista)"
          >
            {view === "grid" ? "≡ Lista" : "▦ Grid"}
          </button>
          <button
            className="ghost"
            aria-label="Mi perfil"
            onClick={() => setProfileOpen(true)}
          >
            {user.name || "Perfil"}
          </button>
        </div>
      </header>

      {/* -------- overlays -------- */}
      {profileOpen && (
        <div className="overlay" onClick={() => setProfileOpen(false)}>
          <main className="card profile-card" onClick={(e) => e.stopPropagation()}>
            <h2>Perfil</h2>
            <p className="sub">Sesión iniciada como {user.email}</p>
            <form onSubmit={handleSaveProfile}>
              <p className="label">Nombre</p>
              <input placeholder="Tu nombre" value={name} onChange={(e) => setName(e.target.value)} />
              {profileError && <p className="error">{profileError}</p>}
              <div className="row">
                <button
                  type="button"
                  className="ghost"
                  onClick={() => {
                    setProfileOpen(false);
                    onLogout();
                  }}
                >
                  Cerrar sesión
                </button>
                <button className="primary" disabled={busy}>
                  {busy ? "Guardando..." : "Guardar"}
                </button>
              </div>
            </form>
          </main>
        </div>
      )}

      {uploadOpen && (
        <div className="overlay" onClick={() => setUploadOpen(false)}>
          <form className="card upload-card" onClick={(e) => e.stopPropagation()} onSubmit={handleUpload}>
            <h2>Subir recurso</h2>
            <p className="sub">Audio, imagen o clip de vídeo</p>
            <input
              type="file"
              ref={fileInput}
              accept="image/*,audio/*,video/*"
              onChange={(e) => {
                const f = e.target.files?.[0] ?? null;
                setFile(f);
                if (f && !title.trim()) setTitle(f.name.replace(/\.[^.]+$/, ""));
              }}
            />
            <p className="label">Título</p>
            <input placeholder="Título del recurso" value={title} onChange={(e) => setTitle(e.target.value)} />
            <p className="label">Tags (separados por coma)</p>
            <input placeholder="intro, logo, b-roll..." value={tagsText} onChange={(e) => setTagsText(e.target.value)} />
            <p className="label">Descripción / notas</p>
            <textarea
              className="grow"
              placeholder="Qué contiene, cámara usada, ideas de uso..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <p className="label">Visibilidad</p>
            <select
              value={visibility}
              onChange={(e) => setVisibility(e.target.value as "private" | "team")}
              aria-label="Visibilidad"
            >
              <option value="private">Privada (solo yo)</option>
              <option value="team">Del equipo</option>
            </select>
            {uploading && <progress value={uploadPct} max={100} aria-label="Progreso de subida" />}
            {uploadMsg && <p className="error">{uploadMsg}</p>}
            <div className="row">
              <button type="button" className="ghost" onClick={() => setUploadOpen(false)}>
                Cancelar
              </button>
              <button className="primary" disabled={!file || uploading}>
                {uploading ? "Subiendo..." : "Subir"}
              </button>
            </div>
          </form>
        </div>
      )}

      {editing && (
        <div className="overlay" onClick={() => setEditing(null)}>
          <form className="card upload-card" onClick={(e) => e.stopPropagation()} onSubmit={handleSaveEdit}>
            <h2>Editar recurso</h2>
            <p className="label">Título</p>
            <input value={editDraft.title} onChange={(e) => setEditDraft({ ...editDraft, title: e.target.value })} />
            <p className="label">Tags (separados por coma)</p>
            <input value={editDraft.tags} onChange={(e) => setEditDraft({ ...editDraft, tags: e.target.value })} />
            <p className="label">Descripción / notas</p>
            <textarea
              className="grow"
              value={editDraft.description}
              onChange={(e) => setEditDraft({ ...editDraft, description: e.target.value })}
            />
            <div className="two-col">
              <div>
                <p className="label">Cámara</p>
                <input
                  placeholder="Sony a7, A6000..."
                  value={editDraft.camera}
                  onChange={(e) => setEditDraft({ ...editDraft, camera: e.target.value })}
                />
              </div>
              <div>
                <p className="label">Proyecto</p>
                <input
                  placeholder="Intro, Podcast 12..."
                  value={editDraft.proyecto}
                  onChange={(e) => setEditDraft({ ...editDraft, proyecto: e.target.value })}
                />
              </div>
            </div>
            <p className="label">Visibilidad</p>
            <select
              value={editDraft.visibility}
              onChange={(e) => setEditDraft({ ...editDraft, visibility: e.target.value as "private" | "team" })}
              aria-label="Visibilidad"
            >
              <option value="private">Privada (solo yo)</option>
              <option value="team">Del equipo</option>
            </select>
            <div className="row">
              <button type="button" className="ghost" onClick={() => setEditing(null)}>
                Cancelar
              </button>
              <button className="primary">Guardar</button>
            </div>
          </form>
        </div>
      )}

      {addItemFor && (
        <div className="overlay" onClick={() => setAddItemFor(null)}>
          <div className="card upload-card popover-collections" onClick={(e) => e.stopPropagation()}>
            <h2>Agregar a colección</h2>
            <p className="sub">{addItemFor.title}</p>
            {collections.length === 0 ? (
              <p className="sub">Primero crea una colección con "+ Nueva".</p>
            ) : (
              <div className="col-options">
                {collections.map((c) => (
                  <button
                    key={c.id}
                    className="chip"
                    onClick={() => handleAddToCollection(addItemFor, c)}
                    aria-label={`Agregar a ${c.name}`}
                  >
                    {c.name} <span className="chip-count">{c.item_count}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {playing && (
        <div className="overlay" onClick={() => setPlaying(null)}>
          <div className="modal player" onClick={(e) => e.stopPropagation()}>
            {playing.kind === "video" && (
              <>
                <video controls autoPlay src={mediaUrl(playing.id, "file")} ref={videoRef} />
                <button className="ghost inplayer" onClick={useThisFrame} title="Usar este frame como poster">
                  🖼 Usar este frame
                </button>
              </>
            )}
            {playing.kind === "audio" && <audio controls autoPlay src={mediaUrl(playing.id, "file")} />}
            {playing.kind === "image" && <img src={mediaUrl(playing.id, "file")} alt={playing.title} />}
            <div className="player-caption">
              <p className="sub">{playing.title}</p>
              {playing.description && <p className="sub muted">{playing.description}</p>}
              {playing.meta?.camera && <p className="sub muted">📹 {playing.meta.camera}</p>}
              {(playing.kind === "video" || playing.kind === "audio") && (
                <p className="sub muted">← → para navegar · Esc cierra</p>
              )}
            </div>
          </div>
        </div>
      )}

      {dupesOpen && (
        <div className="overlay" onClick={() => setDupesOpen(false)}>
          <div className="card dupe-card" onClick={(e) => e.stopPropagation()}>
            <h2>Duplicados por contenido</h2>
            {dupes.length === 0 && <p className="sub">No hay duplicados. ¡Limpio!</p>}
            {dupes.map((g, i) => (
              <div className="dupe-group" key={i}>
                <p className="dupe-head">
                  {g.length} copias idénticas ({fmtSize(g[0].size)} cada una)
                </p>
                <ul>
                  {g.map((it) => (
                    <li key={it.id}>
                      {it.title} <span className="muted">· subido {it.created_at.slice(0, 10)}</span>
                    </li>
                  ))}
                </ul>
                <button
                  className="ghost danger"
                  onClick={() => purgeAllButFirst(g)}
                  aria-label="Conservar primero y purgar copias"
                >
                  🗑 Conservar el más viejo y purgar {g.length - 1} copia(s)
                </button>
              </div>
            ))}
            <div className="row">
              <button className="ghost" onClick={() => setDupesOpen(false)}>
                Cerrar
              </button>
            </div>
          </div>
        </div>
      )}

      {/* -------- barra de pestañas + búsqueda -------- */}
      <div className="lib-toolbar">
        <nav className="tabs" aria-label="Tipos de recurso">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`tab${tab === t.key ? " active" : ""}`}
              onClick={() => {
                if (t.key !== "trash") setSelectedCol(null); // papelera NO respeta colección
                setTab(t.key);
              }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </nav>
        <input
          className="search"
          ref={searchInput}
          placeholder="Buscar por nombre, tag o descripción...  ( / para enfocar )"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Buscar"
        />
        <select
          aria-label="Alcance"
          value={scope}
          onChange={(e) => setScope(e.target.value as "mine" | "team")}
          title="Qué libros ver: solo tuyas (+ equipo público)"
        >
          <option value="mine">Mías</option>
          <option value="team">+ Equipo</option>
        </select>
        <select
          aria-label="Orden"
          value={`${order}:${direction}`}
          onChange={(e) => {
            const [o, d] = e.target.value.split(":");
            setOrder(o as typeof order);
            setDirection(d as "asc" | "desc");
          }}
        >
          <option value="created:desc">＋ Nuevos primero</option>
          <option value="created:asc">－ Viejos primero</option>
          <option value="title:asc">A → Z</option>
          <option value="title:desc">Z → A</option>
          <option value="size:desc">Pesados primero</option>
          <option value="size:asc">Ligeros primero</option>
          <option value="duration:desc">Más largos</option>
          <option value="duration:asc">Más cortos</option>
        </select>
        <button className="primary" onClick={() => setUploadOpen(true)}>
          + Subir
        </button>
      </div>

      {/* -------- barra de colecciones + export -------- */}
      {!inTrash && (
        <div className="collections-bar">
          <span className="label">Colecciones</span>
          <select
            aria-label="Seleccionar colección"
            value={selectedCol?.id ?? ""}
            onChange={(e) => {
              const id = Number(e.target.value);
              setSelectedCol(collections.find((c) => c.id === id) ?? null);
            }}
          >
            <option value="">— ver todo —</option>
            {collections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.is_project ? "🎬 " : ""}
                {c.name} ({c.item_count})
              </option>
            ))}
          </select>
          <button className="ghost" onClick={handleCreateCollection} aria-label="Nueva colección">
            + Nueva / editar
          </button>
          {selectedCol && (
            <>
              <a
                className="chip"
                href={exportUrl(selectedCol.id, "txt")}
                download
                title="Descargar lista .txt"
                aria-label="Exportar lista txt"
              >
                ⬇ .txt
              </a>
              <a
                className="chip"
                href={exportUrl(selectedCol.id, "csv")}
                download
                title="Descargar lista .csv"
                aria-label="Exportar lista csv"
              >
                ⬇ .csv
              </a>
            </>
          )}
          {bulkMsg && <span className="ok">{bulkMsg}</span>}
          {colError && <span className="error">{colError}</span>}
        </div>
      )}

      {/* -------- barra de acciones en lote -------- */}
      {selectedIds.size > 0 && (
        <div className="bulk-bar">
          <strong>{selectedIds.size} seleccionado(s)</strong>
          {!inTrash && (
            <>
              <input
                placeholder="tags a añadir/como quitar (coma)"
                value={bulkTagsText}
                onChange={(e) => setBulkTagsText(e.target.value)}
                aria-label="Tags para el lote"
              />
              <button className="chip" disabled={bulkBusy} onClick={() => runBulk("add_tag")}>
                ＋ tags
              </button>
              <button className="chip" disabled={bulkBusy} onClick={() => runBulk("remove_tag")}>
                － tags
              </button>
              <select
                aria-label="Colección destino del lote"
                value={bulkColId}
                onChange={(e) => setBulkColId(Number(e.target.value))}
              >
                <option value="">— añadir a colección…</option>
                {collections.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <button
                className="chip"
                disabled={bulkBusy || !bulkColId}
                onClick={() => runBulk("add_to_collection")}
              >
                → añadir
              </button>
              <button className="chip" disabled={bulkBusy} onClick={() => runBulk("set_visibility")}>
                👥 team
              </button>
              <button className="chip danger" disabled={bulkBusy} onClick={() => runBulk("delete")}>
                🗑 papelera
              </button>
            </>
          )}
          {inTrash && (
            <>
              <button className="chip" disabled={bulkBusy} onClick={() => runBulk("restore")}>
                ↺ restaurar
              </button>
              <button className="chip danger" disabled={bulkBusy} onClick={() => runBulk("purge")}>
                🗑 purgar
              </button>
            </>
          )}
          <button className="ghost" onClick={() => setSelectedIds(new Set())}>
            cancelar
          </button>
        </div>
      )}

      {/* -------- chips de tags -------- */}
      {tagChips.length > 0 && !inTrash && (
        <div className="tag-chips">
          {activeTag && (
            <button
              className="chip active"
              onClick={() => setActiveTag(null)}
              aria-label="Quitar filtro de tag"
            >
              ✕ {activeTag}
            </button>
          )}
          {tagChips
            .filter((c) => c.tag !== activeTag)
            .map((c) => (
              <button key={c.tag} className="chip" onClick={() => setActiveTag(c.tag)}>
                {c.tag} <span className="chip-count">{c.count}</span>
              </button>
            ))}
        </div>
      )}

      {/* -------- listado -------- */}
      <main className="lib">
        {loading && <p className="loading">Cargando…</p>}
        {listError && <p className="error">{listError}</p>}
        {!loading && !listError && items.length === 0 && (
          <div className="empty">
            <p>
              {inTrash
                ? "La papelera está vacía."
                : debouncedQ || activeTag || selectedCol
                  ? "Sin resultados. Prueba otra búsqueda o quita el filtro."
                  : "Nada por aquí todavía. Sube o arrastra tus primeros recursos."}
            </p>
          </div>
        )}
        {!loading && items.length > 0 && (
          <>
            <p className="sub count">
              {selectedCol ? `Colección "${selectedCol.name}" · ` : ""}
              {inTrash ? "Papelera · " : ""}
              {items.length}/{total} recursos
            </p>
            {view === "grid" && !inTrash && (
              <div className="media-grid">
                {items.map((item) => (
                  <GridCard
                    key={item.id}
                    item={item}
                    selected={selectedIds.has(item.id)}
                    onToggleSelect={() => toggleSelect(item.id)}
                    onPlay={() => setPlaying(item)}
                    onEdit={() => openEdit(item)}
                    onDelete={() => handleDelete(item)}
                    onAddToCollection={() => setAddItemFor(item)}
                    hasCollections={collections.length > 0}
                    activeColId={selectedCol?.id}
                    onRemoveFromCol={() => handleRemoveFromCollection(item)}
                    onTagClick={setActiveTag}
                  />
                ))}
              </div>
            )}
            {view === "grid" && inTrash && (
              <div className="media-grid">
                {items.map((item) => (
                  <GridCard
                    key={item.id}
                    item={item}
                    trash
                    selected={selectedIds.has(item.id)}
                    onToggleSelect={() => toggleSelect(item.id)}
                    onRestore={() => handleRestore(item)}
                    onPurge={() => handlePurge(item)}
                  />
                ))}
              </div>
            )}
            {view === "list" && (
              <table className="list-table">
                <thead>
                  <tr>
                    <th />
                    <th>Título</th>
                    <th>Tipo</th>
                    <th>Tags</th>
                    <th>Tamaño</th>
                    <th>Duración</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <ListRow
                      key={item.id}
                      item={item}
                      selected={selectedIds.has(item.id)}
                      onToggleSelect={() => toggleSelect(item.id)}
                      onPlay={() => setPlaying(item)}
                      inTrash={inTrash}
                      onRestore={() => handleRestore(item)}
                      onPurge={() => handlePurge(item)}
                      onDelete={() => handleDelete(item)}
                      onEdit={() => openEdit(item)}
                      onAddToCollection={() => setAddItemFor(item)}
                    />
                  ))}
                </tbody>
              </table>
            )}
            <div ref={sentinel} />
            {hasMore && (
              <div className="row center">
                <button className="ghost" onClick={loadMore}>
                  Cargar más ({total - items.length} restantes)
                </button>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

/* ======================================================== subcomponentes */

function Thumb({ item, className }: { item: MediaItem; className?: string }) {
  return item.has_thumb ? (
    <img src={mediaUrl(item.id, "thumb")} alt={item.title} className={className} />
  ) : (
    <span className="media-icon" role="img">
      {KIND_ICON[item.kind]}
    </span>
  );
}

function GridCard({
  item,
  trash,
  selected,
  onToggleSelect,
  onPlay,
  onEdit,
  onDelete,
  onRestore,
  onPurge,
  onAddToCollection,
  onRemoveFromCol,
  hasCollections,
  activeColId,
  onTagClick,
}: {
  item: MediaItem;
  trash?: boolean;
  selected: boolean;
  onToggleSelect?: () => void;
  onPlay?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onRestore?: () => void;
  onPurge?: () => void;
  onAddToCollection?: () => void;
  onRemoveFromCol?: () => void;
  hasCollections?: boolean;
  activeColId?: number;
  onTagClick?: (t: string) => void;
}) {
  return (
    <article className={`media-card${selected ? " selected" : ""}`}>
      <button className="media-visual" onClick={onPlay} aria-label={`Ver ${item.title}`}>
        <Thumb item={item} />
      </button>
      <label className="pick-row">
        <input type="checkbox" checked={selected} onChange={onToggleSelect} aria-label={`Seleccionar ${item.title}`} />
        <strong className="media-title">{item.title}</strong>
        {item.visibility === "team" && <span className="mini-chip">👥</span>}
      </label>
      <div className="media-info">
        {!trash && onTagClick && (
          <div className="media-tags">
            {item.tags.map((t) => (
              <button
                key={t}
                className="mini-chip"
                onClick={() => onTagClick?.(t)}
                aria-label={`Filtrar por tag ${t}`}
              >
                {t}
              </button>
            ))}
          </div>
        )}
        <span className="media-meta">
          {fmtSize(item.size)}
          {item.duration_s !== null && item.duration_s !== undefined ? ` · ${fmtDuration(item.duration_s)}` : ""}
          {trash ? ` · borrado ${item.created_at.slice(0, 10)} (subida)` : ""}
        </span>
        {item.description && <span className="media-meta desc">{item.description}</span>}
      </div>
      <div className="media-actions">
        {trash && onRestore && (
          <button className="ghost" onClick={onRestore} aria-label={`Restaurar ${item.title}`} title="Restaurar">
            ↺
          </button>
        )}
        {onRemoveFromCol && activeColId && (
          <button
            className="ghost"
            onClick={onRemoveFromCol}
            aria-label={`Quitar ${item.title} de la colección`}
            title="Quitar de la colección"
          >
            －
          </button>
        )}
        {!trash && hasCollections && onAddToCollection && (
          <button
            className="ghost"
            onClick={onAddToCollection}
            aria-label={`Agregar ${item.title} a una colección`}
            title="Agregar a una colección"
          >
            ＋
          </button>
        )}
        <a
          className="ghost action-link"
          href={mediaUrl(item.id, "file")}
          download={item.filename}
          aria-label={`Descargar ${item.title}`}
          title={`Descargar (${item.filename})`}
        >
          ⬇
        </a>
        {!trash && onPlay && (
          <button className="ghost" onClick={onPlay} aria-label={`Reproducir ${item.title}`}>
            {item.kind === "image" ? "👁" : "▶"}
          </button>
        )}
        {!trash && onEdit && (
          <button className="ghost" onClick={onEdit} aria-label={`Editar ${item.title}`}>
            ✏️
          </button>
        )}
        {!trash && onDelete && (
          <button className="ghost danger" onClick={onDelete} aria-label={`Eliminar ${item.title}`} title="A la papelera">
            🗑
          </button>
        )}
        {trash && onPurge && (
          <button className="ghost danger" onClick={onPurge} aria-label={`Purgar ${item.title}`} title="Borrar definitivo">
            🔥
          </button>
        )}
      </div>
    </article>
  );
}

function ListRow({
  item,
  inTrash,
  selected,
  onToggleSelect,
  onPlay,
  onDelete,
  onEdit,
  onRestore,
  onPurge,
  onAddToCollection,
}: {
  item: MediaItem;
  inTrash: boolean;
  selected: boolean;
  onToggleSelect: () => void;
  onPlay: () => void;
  onDelete?: () => void;
  onEdit?: () => void;
  onRestore?: () => void;
  onPurge?: () => void;
  onAddToCollection?: () => void;
}) {
  return (
    <tr className={selected ? "selected" : ""}>
      <td>
        <input type="checkbox" checked={selected} onChange={onToggleSelect} aria-label={`Seleccionar ${item.title}`} />
      </td>
      <td>
        <button className="ghost inline" onClick={onPlay} aria-label={`Ver ${item.title}`}>
          <span className="list-thumb">
            <Thumb item={item} className="mini" />
          </span>
          {item.title}
        </button>
      </td>
      <td>{KIND_ICON[item.kind]}</td>
      <td className="muted">{item.tags.join(", ")}</td>
      <td>{fmtSize(item.size)}</td>
      <td>{fmtDuration(item.duration_s)}</td>
      <td className="row-actions">
        {inTrash && onRestore && (
          <button className="ghost" onClick={onRestore} title="Restaurar">
            ↺
          </button>
        )}
        {inTrash && onPurge && (
          <button className="ghost danger" onClick={onPurge} title="Purgar">
            🔥
          </button>
        )}
        {!inTrash && (
          <>
            {onAddToCollection && (
              <button className="ghost" onClick={onAddToCollection} title="Agregar a colección">
                ＋
              </button>
            )}
            <a
              className="ghost action-link"
              href={mediaUrl(item.id, "file")}
              download={item.filename}
              title="Descargar"
              aria-label={`Descargar ${item.title}`}
            >
              ⬇
            </a>
            {onEdit && (
              <button className="ghost" onClick={onEdit} title="Editar">
                ✏️
              </button>
            )}
            {onDelete && (
              <button className="ghost danger" onClick={onDelete} title="A la papelera">
                🗑
              </button>
            )}
          </>
        )}
      </td>
    </tr>
  );
}

export { };

import { useCallback, useEffect, useRef, useState } from "react";
import {
  addCollectionItem,
  createCollection,
  deleteMedia,
  listCollections,
  listMedia,
  listTags,
  mediaUrl,
  removeCollectionItem,
  updateMedia,
  updateMe,
  uploadMedia,
  type Collection,
  type MediaItem,
  type MediaKind,
  type User,
} from "../lib/api";

type TabKey = "all" | MediaKind;

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: "all", label: "Todos", icon: "🗂" },
  { key: "audio", label: "Audio", icon: "🎵" },
  { key: "image", label: "Imágenes", icon: "🖼" },
  { key: "video", label: "Vídeos", icon: "🎬" },
];

const KIND_ICON: Record<MediaKind, string> = { audio: "🎵", image: "🖼", video: "🎬" };

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

  // Subida
  const [uploadOpen, setUploadOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [tagsText, setTagsText] = useState("");
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

  // Edición y reproductor
  const [editing, setEditing] = useState<MediaItem | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [editTags, setEditTags] = useState("");
  const [playing, setPlaying] = useState<MediaItem | null>(null);

  // Perfil (edición de nombre, como antes)
  const [profileOpen, setProfileOpen] = useState(false);
  const [name, setName] = useState(user.name ?? "");
  const [busy, setBusy] = useState(false);
  const [profileError, setProfileError] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

  // Debounce de la búsqueda por nombre/tags
  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

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

  const loadItems = useCallback(async () => {
    setLoading(true);
    setListError("");
    try {
      const res = await listMedia({
        q: debouncedQ || undefined,
        kind: tab === "all" ? undefined : tab,
        tag: activeTag ?? undefined,
        collection: selectedCol?.id,
      });
      setItems(res.items);
      setTotal(res.total);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al cargar la biblioteca");
    } finally {
      setLoading(false);
    }
  }, [debouncedQ, tab, activeTag, selectedCol]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    loadTags();
    loadCollections();
  }, [loadTags, loadCollections]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    setUploadMsg("");
    setUploading(true);
    setUploadPct(0);
    try {
      await uploadMedia(file, title, tagsText, setUploadPct);
      setUploadMsg("");
      setFile(null);
      setTitle("");
      setTagsText("");
      if (fileInput.current) fileInput.current.value = "";
      setUploadOpen(false);
      await Promise.all([loadItems(), loadTags(), loadCollections()]);
    } catch (err) {
      setUploadMsg(err instanceof Error ? err.message : "Error al subir");
    } finally {
      setUploading(false);
    }
  }

  // ---- drag & drop: 1 archivo → dialogo pre-llenado; varios → subida · en lote
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
        await uploadMedia(f, f.name.replace(/\.[^.]+$/, ""), "");
        done += 1;
      } catch {
        failed += 1;
      }
    }
    setBulkMsg(
      failed === 0
        ? `${done} archivo(s) subidos.`
        : `${done} subidos · ${failed} fallidos (revisa formato/tamaño).`,
    );
    await Promise.all([loadItems(), loadTags(), loadCollections()]);
  }

  // ---- colecciones
  async function handleCreateCollection() {
    const name = window.prompt("Nombre de la nueva colección (álbum/playlist):");
    if (!name || !name.trim()) return;
    setColError("");
    try {
      const col = await createCollection(name.trim());
      setCollections((prev) => [...prev, col].sort((a, b) => a.name.localeCompare(b.name)));
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al crear la colección");
    }
  }

  async function handleAddToCollection(item: MediaItem, col: Collection) {
    setColError("");
    try {
      const updated = await addCollectionItem(col.id, item.id);
      setCollections((prev) =>
        prev.map((c) => (c.id === updated.id ? updated : c)),
      );
      setAddItemFor(null);
      await Promise.all([loadTags(), loadCollections()]);
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al agregar a la colección");
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
      await loadItems();
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al quitar de la colección");
    }
  }

  async function handleDelete(item: MediaItem) {
    if (!window.confirm(`¿Eliminar "${item.title}" de la biblioteca?`)) return;
    try {
      await deleteMedia(item.id);
      await Promise.all([loadItems(), loadTags()]);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al eliminar");
    }
  }

  function openEdit(item: MediaItem) {
    setEditing(item);
    setEditTitle(item.title);
    setEditTags(item.tags.join(", "));
  }

  async function handleSaveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    try {
      const tags = editTags
        .split(",")
        .map((t) => t.trim().toLowerCase())
        .filter(Boolean);
      await updateMedia(editing.id, {
        title: editTitle.trim() || editing.title,
        tags,
      });
      setEditing(null);
      await Promise.all([loadItems(), loadTags()]);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al editar");
    }
  }

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
          <p className="sub">1 archivo → revision antes de subir · varios → subida directa</p>
        </div>
      )}
      <header className="topbar">
        <h1>Biblioteca de Recursos Multimedia</h1>
        <div>
          <button
            className="ghost"
            aria-label="Mi perfil"
            onClick={() => setProfileOpen((v) => !v)}
          >
            Perfil
          </button>
          <button className="ghost" onClick={onLogout}>
            Cerrar sesión
          </button>
        </div>
      </header>

      {profileOpen && (
        <main className="content">
          <div className="card">
            <h2>Perfil</h2>
            <p className="sub">Sesión iniciada como {user.email}</p>
            <form onSubmit={handleSaveProfile}>
              <p className="label">Nombre</p>
              <input
                placeholder="Tu nombre"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
              {profileError && <p className="error">{profileError}</p>}
              <button className="primary" disabled={busy}>
                {busy ? "Guardando..." : "Guardar"}
              </button>
            </form>
          </div>
        </main>
      )}

      {uploadOpen && (
        <div className="overlay" onClick={() => setUploadOpen(false)}>
          <form
            className="card upload-card"
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleUpload}
          >
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
            <input
              placeholder="Título del recurso"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
            <p className="label">Tags (separados por coma)</p>
            <input
              placeholder="intro, logo, b-roll..."
              value={tagsText}
              onChange={(e) => setTagsText(e.target.value)}
            />
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
          <form
            className="card upload-card"
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSaveEdit}
          >
            <h2>Editar recurso</h2>
            <p className="label">Título</p>
            <input value={editTitle} onChange={(e) => setEditTitle(e.target.value)} />
            <p className="label">Tags (separados por coma)</p>
            <input value={editTags} onChange={(e) => setEditTags(e.target.value)} />
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
          <div
            className="card upload-card popover-collections"
            onClick={(e) => e.stopPropagation()}
          >
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
              <video controls autoPlay src={mediaUrl(playing.id, "file")} />
            )}
            {playing.kind === "audio" && (
              <audio controls autoPlay src={mediaUrl(playing.id, "file")} />
            )}
            {playing.kind === "image" && (
              <img src={mediaUrl(playing.id, "file")} alt={playing.title} />
            )}
            <p className="sub">{playing.title}</p>
          </div>
        </div>
      )}

      <div className="lib-toolbar">
        <nav className="tabs" aria-label="Tipos de recurso">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`tab${tab === t.key ? " active" : ""}`}
              onClick={() => setTab(t.key)}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </nav>
        <input
          className="search"
          placeholder="Buscar por nombre o tag..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Buscar"
        />
        <button className="primary" onClick={() => setUploadOpen(true)}>
          + Subir
        </button>
      </div>

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
              {c.name} ({c.item_count})
            </option>
          ))}
        </select>
        <button className="ghost" onClick={handleCreateCollection} aria-label="Nueva colección">
          + Nueva
        </button>
        {bulkMsg && <span className="ok">{bulkMsg}</span>}
        {colError && <span className="error">{colError}</span>}
      </div>

      {tagChips.length > 0 && (
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

      <main className="lib">
        {loading && <p className="loading">Cargando…</p>}
        {listError && <p className="error">{listError}</p>}
        {!loading && !listError && items.length === 0 && (
          <div className="empty">
            <p>
              {debouncedQ || activeTag
                ? "Sin resultados. Prueba otra búsqueda o quita el filtro."
                : "Nada por aquí todavía. Sube o arrastra tus primeros recursos."}
            </p>
          </div>
        )}
        {!loading && items.length > 0 && (
          <>
            <p className="sub count">
              {selectedCol ? `Colección "${selectedCol.name}" · ` : ""}
              {total} recurso(s)
            </p>
            <div className="media-grid">
              {items.map((item) => (
                <article className="media-card" key={item.id}>
                  <button
                    className="media-visual"
                    onClick={() => setPlaying(item)}
                    aria-label={`Ver ${item.title}`}
                  >
                    {item.kind !== "audio" && item.has_thumb ? (
                      <img src={mediaUrl(item.id, "thumb")} alt={item.title} />
                    ) : (
                      <span className="media-icon" role="img" aria-label="">
                        {KIND_ICON[item.kind]}
                      </span>
                    )}
                  </button>
                  <div className="media-info">
                    <strong className="media-title">{item.title}</strong>
                    <div className="media-tags">
                      {item.tags.map((t) => (
                        <button
                          key={t}
                          className="mini-chip"
                          onClick={() => setActiveTag(t)}
                          aria-label={`Filtrar por tag ${t}`}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                    <span className="media-meta">
                      {fmtSize(item.size)}
                      {item.duration_s !== null ? ` · ${fmtDuration(item.duration_s)}` : ""}
                    </span>
                  </div>
                  <div className="media-actions">
                    {collections.length > 0 && (
                      selectedCol ? (
                        <button
                          className="ghost"
                          onClick={() => handleRemoveFromCollection(item)}
                          aria-label={`Quitar ${item.title} de la colección ${selectedCol.name}`}
                          title={`Quitar de "${selectedCol.name}"`}
                        >
                          －
                        </button>
                      ) : (
                        <button
                          className="ghost"
                          onClick={() => setAddItemFor(item)}
                          aria-label={`Agregar ${item.title} a una colección`}
                          title="Agregar a una colección"
                        >
                          ＋
                        </button>
                      )
                    )}
                    <button
                      className="ghost"
                      onClick={() => setPlaying(item)}
                      aria-label={`Reproducir ${item.title}`}
                    >
                      {KIND_ICON[item.kind] === "🖼" ? "Ver" : "▶"}
                    </button>
                    <button
                      className="ghost"
                      onClick={() => openEdit(item)}
                      aria-label={`Editar ${item.title}`}
                    >
                      ✏️
                    </button>
                    <button
                      className="ghost danger"
                      onClick={() => handleDelete(item)}
                      aria-label={`Eliminar ${item.title}`}
                    >
                      🗑
                    </button>
                  </div>
                </article>
              ))}
            </div>
          </>
        )}
      </main>
    </div>
  );
}

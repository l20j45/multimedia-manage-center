import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  addCollectionItem,
  bulkMedia,
  createCollection,
  deleteCollection,
  createShare,
  revokeShare,
  deleteMedia,
  exportUrl,
  exportZipUrl,
  fetchStats,
  findByHash,
  getApiBase,
  getAutotagSuggestions,
  getGeminiKeyStatus,
  listCollections,
  listDuplicates,
  listMedia,
  listTags,
  mediaUrl,
  purgeMedia,
  removeCollectionItem,
  restoreMedia,
  jobStatus,
  setApiBase,
  setGeminiKey,
  sha256OfFile,
  shareLink,
  updateMe,
  updateMedia,
  uploadMedia,
  type Collection,
  type MediaItem,
  type MediaKind,
  type MediaQuery,
  type StatOut,
  type User,
} from "../lib/api";
import DetailPanel from "./DetailPanel";

type NavKey = "all" | MediaKind | "trash" | "collections" | "stats";

const NAV_MAIN: { key: NavKey; label: string; icon: string }[] = [
  { key: "all", label: "Todos", icon: "🗂" },
  { key: "audio", label: "Audio", icon: "🎵" },
  { key: "image", label: "Imágenes", icon: "🖼" },
  { key: "video", label: "Vídeos", icon: "🎬" },
  { key: "collections", label: "Colecciones", icon: "📚" },
  { key: "stats", label: "Stats", icon: "📊" },
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
  const [nav, setNav] = useState<NavKey>("all");
  const [query, setQuery] = useState("");
  const [debouncedQ, setDebouncedQ] = useState("");
  const [activeTag, setActiveTag] = useState<string | null>(null);
  const [tagChips, setTagChips] = useState<{ tag: string; count: number }[]>([]);
  const [items, setItems] = useState<MediaItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState("");

  // Filtros / vistas
  const [scope, setScope] = useState<"mine" | "team">("mine");
  const [order, setOrder] = useState<NonNullable<MediaQuery["order"]>>("created");
  const [direction, setDirection] = useState<"asc" | "desc">("desc");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [minRating, setMinRating] = useState(false);

  // Subida
  const [uploadOpen, setUploadOpen] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [title, setTitle] = useState("");
  const [tagsText, setTagsText] = useState("");
  const [description, setDescription] = useState("");
  const [visibility, setVisibility] = useState<"private" | "team">("private");
  const [uploading, setUploading] = useState(false);
  const [uploadPct, setUploadPct] = useState(0);
  const [uploadMsg, setUploadMsg] = useState("");

  // Compresión en background: items con job activo (poll cada 3s → notificación)
  const [compressJobs, setCompressJobs] = useState<number[]>([]);

  // Drag & drop
  const [dragging, setDragging] = useState(false);
  const [toasts, setToasts] = useState<{ id: number; msg: string }[]>([]);

  function toast(msg: string): void {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, msg }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4500);
  }

  function trackJob(itemId: number): void {
    setCompressJobs((prev) => (prev.includes(itemId) ? prev : [...prev, itemId]));
  }

  // Poll para los jobs de compresión en background: al terminar (o fallar)
  // suelta el item y lanza la notificación tipo toast.
  useEffect(() => {
    if (compressJobs.length === 0) return;
    const timer = setInterval(async () => {
      for (const itemId of compressJobs) {
        try {
          const st = await jobStatus(itemId);
          if (st.status === "done") {
            setCompressJobs((prev) => prev.filter((id) => id !== itemId));
            toast(
              st.new_size !== null && st.old_size !== null && st.new_size < st.old_size
                ? `🗜 compresión lista: ${fmtSize(st.old_size)} → ${fmtSize(st.new_size)}`
                : "🗜 compresión lista (el original ya era compacto — sin cambios)",
            );
            await loadItems(0, true);
          } else if (st.status === "failed" || st.status === "lost") {
            setCompressJobs((prev) => prev.filter((id) => id !== itemId));
            toast(
              st.status === "lost"
                ? "⚠ compresión interrumpida por un reinicio — re-inténtala con 🗜 Comprimir"
                : `⚠ compresión falló: ${st.error ?? "error desconocido"}`,
            );
          }
        } catch {
          setCompressJobs((prev) => prev.filter((id) => id !== itemId));
        }
      }
    }, 3000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [compressJobs]);

  // Auto-tag sugerencias (nunca se aplican solas)
  const [suggestions, setSuggestions] = useState<{
    id: number;
    title: string;
    baseTags: string[];
    suggestions: string[];
    source: string;
  } | null>(null);

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

  // Detalle / duplicados / edición
  const [detail, setDetail] = useState<MediaItem | null>(null);
  const [editing, setEditing] = useState<MediaItem | null>(null);
  const [editDraft, setEditDraft] = useState({
    title: "",
    tags: "",
    description: "",
    camera: "",
    proyecto: "",
    visibility: "private" as "private" | "team",
  });
  const [dupesOpen, setDupesOpen] = useState(false);
  const [dupes, setDupes] = useState<MediaItem[][]>([]);
  const [similar, setSimilar] = useState<MediaItem[][]>([]);
  const [shareLinkFor, setShareLinkFor] = useState<{ name: string; link: string } | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  // Perfil
  const [profileOpen, setProfileOpen] = useState(false);
  const [name, setName] = useState(user.name ?? "");
  const [busy, setBusy] = useState(false);
  const [profileError, setProfileError] = useState("");

  // Servidor (dirección del backend): clave para APK / oficina
  const [apiBase, setApiBaseState] = useState(getApiBase());
  const [apiSaved, setApiSaved] = useState(false);

  function saveApiBase() {
    setApiSaved(false);
    try {
      const stored = setApiBase(apiBase);
      setApiBaseState(stored);
      setApiSaved(true);
      toast(`🌐 servidor: ${stored}`);
      window.setTimeout(() => window.location.reload(), 900); // reconectar
    } catch (err) {
      setProfileError(err instanceof Error ? err.message : "URL inválida");
    }
  }

  // Llave IA (configuración desde la app)
  const [geminiKey, setGeminiKeyValue] = useState("");
  const [geminiStatus, setGeminiStatus] = useState<{ set: boolean; tail: string; source: string } | null>(null);
  const [geminiBusy, setGeminiBusy] = useState(false);

  // Stats
  const [stats, setStats] = useState<StatOut | null>(null);

  const fileInput = useRef<HTMLInputElement>(null);
  const searchInput = useRef<HTMLInputElement>(null);

  /* ------------------------------------------------------ carga de datos */
  const inTrash = nav === "trash";
  const queryBase = useMemo(
    () => ({
      q: debouncedQ || undefined,
      tag: activeTag ?? undefined,
      scope,
      order,
      direction,
      min_rating: minRating ? 3 : null,
      kind: (nav === "all" || nav === "trash" || nav === "collections" ? undefined : nav) as
        | MediaKind
        | undefined,
    }),
    [debouncedQ, activeTag, scope, order, direction, nav, minRating],
  );

  const loadItems = useCallback(
    async (offset = 0, replace = true) => {
      let res;
      if (selectedCol && !inTrash && nav !== "collections") {
        res = await listMedia({ ...queryBase, collection: selectedCol.id, limit: PAGE_SIZE, offset });
      } else if (nav === "collections") {
        setItems([]);
        setTotal(0);
        return;
      } else {
        res = await listMedia({ ...queryBase, trash: inTrash, limit: PAGE_SIZE, offset });
      }
      setItems((prev) => (replace ? res.items : [...prev, ...res.items]));
      setTotal(res.total);
    },
    [queryBase, nav, selectedCol, inTrash],
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
      .catch((err: unknown) => setListError(err instanceof Error ? err.message : "Error al cargar"))
      .finally(() => setLoading(false));
    setSelectedIds(new Set());
  }, [loadItems]);

  useEffect(() => {
    loadTags();
    loadCollections();
  }, [loadTags, loadCollections]);

  // stats y estado de llave: al abrir Perfil o la vista Stats
  useEffect(() => {
    if (nav === "stats" && !stats) {
      fetchStats().then(setStats).catch(() => setStats(null));
    }
  }, [nav, stats]);

  useEffect(() => {
    if (profileOpen && !geminiStatus) {
      getGeminiKeyStatus().then(setGeminiStatus).catch(() => setGeminiStatus(null));
    }
    if (!profileOpen) setGeminiKeyValue("");
  }, [profileOpen, geminiStatus]);

  async function saveGeminiKey() {
    setGeminiBusy(true);
    try {
      setGeminiStatus(await setGeminiKey(geminiKey));
      setGeminiKeyValue("");
    } catch {
      /* la UI muestra el error dentro del estado si falla: aquí silencio */
    } finally {
      setGeminiBusy(false);
    }
  }

  useEffect(() => {
    const t = setTimeout(() => setDebouncedQ(query.trim()), 300);
    return () => clearTimeout(t);
  }, [query]);

  const hasMore = items.length < total && !loading && nav !== "collections";
  const loadMore = useCallback(async () => {
    setLoading(true);
    try {
      await loadItems(items.length, false);
    } finally {
      setLoading(false);
    }
  }, [loadItems, items.length]);

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
      if (detail?.id === item.id) setDetail(null);
      await Promise.all([loadItems(0, true), loadTags()]);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al eliminar");
    }
  }

  async function handlePurge(item: MediaItem) {
    if (!window.confirm(`¿Borrar DEFINITIVAMENTE "${item.title}"? No se puede deshacer.`)) return;
    try {
      await purgeMedia(item.id);
      if (detail?.id === item.id) setDetail(null);
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

  async function rateItem(id: number, stars: number) {
    const target = items.find((i) => i.id === id)?.rating === stars ? 0 : stars;
    try {
      const updated = await updateMedia(id, { rating: target });
      setItems((prev) => prev.map((i) => (i.id === updated.id ? { ...i, rating: updated.rating } : i)));
      await loadTags();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al valorar");
    }
  }

  async function postUploadRefresh(): Promise<void> {
    await Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
  }

  /** Sube varios archivos en fila aplicando tags/desc/visibilidad compartidos.
   *  Título siempre = nombre del fichero. Registra jobs de compresión. */
  async function uploadMany(
    files: File[],
    onTick: (doneIndex: number, pctFile: number) => void,
    shared?: { tags: string; description: string },
  ): Promise<{ done: number; failed: number; dups: number; sims: number }> {
    let done = 0;
    let failed = 0;
    let dups = 0;
    let sims = 0;
    for (const [i, f] of files.entries()) {
      try {
        const up = await uploadMedia(
          f,
          f.name.replace(/\.[^.]+$/, ""),
          shared?.tags ?? "",
          (pct) => onTick(i, pct),
          { description: shared?.description ?? "", visibility },
        );
        if (up.compress_job_id) trackJob(up.id);
        if (up.duplicate_of) dups += 1;
        if (up.similar_of) sims += 1;
        done += 1;
      } catch {
        failed += 1;
      }
    }
    return { done, failed, dups, sims };
  }

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (selectedFiles.length === 0) return;
    setUploadMsg("");
    setUploading(true);
    setUploadPct(0);
    try {
      if (selectedFiles.length === 1) {
        const up = await uploadMedia(selectedFiles[0], title, tagsText, setUploadPct, {
          description,
          visibility,
        });
        if (up.compress_job_id) trackJob(up.id);
        if (up.duplicate_of) {
          toast(`⚠ mismo contenido que «${up.duplicate_of.title}» — mira la sección de duplicados`);
        } else if (up.similar_of) {
          toast(`👁 muy parecido a «${up.similar_of.title}» — revisa la sección de duplicados`);
        }
        await postUploadRefresh();
        getAutotagSuggestions(up.id)
          .then((r) => {
            if (r.suggestions.length > 0) {
              setSuggestions({
                id: up.id,
                title: up.title,
                baseTags: (up.tags ?? []).slice(),
                suggestions: r.suggestions,
                source: r.source,
              });
            }
          })
          .catch(() => {});
      } else {
        const { done, failed, dups, sims } = await uploadMany(
          selectedFiles,
          (doneIdx, pctFile) =>
            setUploadPct(((doneIdx + pctFile / 100) / selectedFiles.length) * 100),
          { tags: tagsText, description },
        );
        toast(
          (failed === 0
            ? `${done} archivo(s) subidos`
            : `${done} subidos · ${failed} fallidos`)
            + (dups > 0 ? ` · ⚠ ${dups} duplicado(s)` : "")
            + (sims > 0 ? ` · 👁 ${sims} muy parecido(s)` : ""),
        );
        await postUploadRefresh();
      }
      setSelectedFiles([]);
      setTitle("");
      setTagsText("");
      setDescription("");
      if (fileInput.current) fileInput.current.value = "";
      setUploadOpen(false);
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
      setSelectedFiles(files);
      setTitle(files[0].name.replace(/\.[^.]+$/, ""));
      setUploadOpen(true);
      return;
    }
    const { done, failed, dups, sims } = await uploadMany(files, () => {});
    toast(
      (failed === 0
        ? `${done} archivo(s) subidos`
        : `${done} subidos · ${failed} fallidos`)
        + (dups > 0 ? ` · ⚠ ${dups} duplicado(s)` : "")
        + (sims > 0 ? ` · 👁 ${sims} muy parecido(s)` : ""),
    );
    await postUploadRefresh();
  }

  async function doQuickUpload(f: File) {
    
    try {
      // anti-dup: si el contenido ya existe lo abrimos en vez de duplicar
      const sha = await sha256OfFile(f);
      if (sha) {
        const dup = await findByHash(sha);
        if (dup) {
          toast(`📋 ya lo tenías: «${dup.title}» — abre el detalle (no duplicado)`);
          setDetail(dup);
          return;
        }
      }
      const up = await uploadMedia(f, f.name.replace(/\.[^.]+$/, ""), "", undefined, { visibility });
      if (up.compress_job_id) trackJob(up.id);
      toast(`📋 pegado y subido: ${f.name}`);
      await Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
      getAutotagSuggestions(up.id)
        .then((r) => {
          if (r.suggestions.length > 0) {
            setSuggestions({
              id: up.id,
              title: up.title,
              baseTags: (up.tags ?? []).slice(),
              suggestions: r.suggestions,
              source: r.source,
            });
          }
        })
        .catch(() => {});
    } catch (err) {
      toast(err instanceof Error ? `⚠ ${err.message}` : "⚠ Error al pegar");
    }
  }

  /* -------------------------------------------------- sugerencias auto-tag */
  async function applySuggestion(tag: string) {
    if (!suggestions) return;
    try {
      await updateMedia(suggestions.id, { tags: [...suggestions.baseTags, tag] });
      setSuggestions((prev) =>
        prev
          ? {
              ...prev,
              baseTags: [...prev.baseTags, tag],
              suggestions: prev.suggestions.filter((t) => t !== tag),
            }
          : null,
      );
      await loadTags();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "No se pudo aplicar el tag");
    }
  }

  async function applyAllSuggestions() {
    if (!suggestions) return;
    try {
      await updateMedia(suggestions.id, { tags: [...suggestions.baseTags, ...suggestions.suggestions] });
      setSuggestions(null);
      await loadTags();
    } catch (err) {
      setListError(err instanceof Error ? err.message : "No se pudieron aplicar los tags");
    }
  }

  /* ------------------------------------------------------------ bulk bar */
  async function runBulk(
    action:
      | "add_tag"
      | "remove_tag"
      | "set_visibility"
      | "add_to_collection"
      | "delete"
      | "restore"
      | "purge"
      | "rename",
  ) {
    setBulkBusy(true);
    
    try {
      const extra: Record<string, unknown> = {};
      if (action === "add_tag" || action === "remove_tag") {
        extra.tags = bulkTagsText.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
      }
      if (action === "add_to_collection") {
        if (!bulkColId) return;
        extra.collection_id = bulkColId;
      }
      if (action === "rename") {
        extra.pattern = renamePattern.trim();
      }
      const res = await bulkMedia([...selectedIds], action, extra);
      toast(`✔ ${res.done} procesado(s).`);
      setSelectedIds(new Set());
      setBulkTagsText("");
      await Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
    } catch (err) {
      toast(err instanceof Error ? `⚠ ${err.message}` : "⚠ Error en la operación en lote");
    } finally {
      setBulkBusy(false);
    }
  }

  /* ------------------------------------------------------------ colecciones */
  async function handleCreateCollection() {
    const name = window.prompt("Nombre de la nueva colección/edición:");
    if (!name || !name.trim()) return;
    const isProj = window.confirm("¿Es una EDICIÓN/proyecto? Aceptar = Sí · Cancelar = Colección normal");
    setColError("");
    try {
      const col = await createCollection(name.trim(), isProj);
      setCollections((prev) => [...prev, col].sort((a, b) => a.name.localeCompare(b.name)));
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al crear la colección");
    }
  }

  /* ---------------------------------------------------- compartir / rename */
  async function createShareLink(col: Collection) {
    setColError("");
    try {
      const r = await createShare(col.id);
      setShareLinkFor({ name: col.name, link: shareLink(r.url) });
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al crear el enlace");
    }
  }

  async function revokeCollectionShare(col: Collection) {
    setColError("");
    try {
      await revokeShare(col.id);
      toast(`🚫 enlace de "${col.name}" revocado`);
    } catch (err) {
      setColError(err instanceof Error ? err.message : "Error al revocar el enlace");
    }
  }

  const [renamePattern, setRenamePattern] = useState("");

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

  async function openDuplicates() {
    try {
      const res = await listDuplicates();
      setDupes(res.groups ?? []);
      setSimilar(res.similar ?? []);
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
      setDupes(res.groups ?? []);
      setSimilar(res.similar ?? []);
      await Promise.all([loadItems(0, true), loadCollections()]);
    } catch (err) {
      setListError(err instanceof Error ? err.message : "Error al purgar duplicados");
    }
  }

  /* ------------------------------------------------------------ shortcuts */
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) {
        if (e.key === "Escape") target.blur();
        return;
      }
      if (e.key === "?") {
        setHelpOpen(true);
        return;
      }
      if (e.key === "/") {
        e.preventDefault();
        searchInput.current?.focus();
        return;
      }
      if (e.key === "Escape") {
        if (helpOpen) setHelpOpen(false);
        else if (addItemFor) setAddItemFor(null);
        else if (editing) setEditing(null);
        else if (profileOpen) setProfileOpen(false);
        else if (uploadOpen) setUploadOpen(false);
        else if (dupesOpen) setDupesOpen(false);
        else if (detail) setDetail(null);
        else if (selectedIds.size) setSelectedIds(new Set());
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [detail, addItemFor, editing, profileOpen, uploadOpen, dupesOpen, selectedIds, helpOpen]);

  /* puntapapel: Ctrl+V pegar directamente */
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      if (uploadOpen || editing || addItemFor || profileOpen || dupesOpen || detail) return;
      const dt = e.clipboardData;
      if (!dt) return;
      const files: File[] = [];
      if (dt.files && dt.files.length > 0) {
        Array.from(dt.files).forEach((f) => files.push(f));
      } else {
        Array.from(dt.items ?? []).forEach((it) => {
          if (it.kind === "file") {
            const f = it.getAsFile();
            if (f) {
              const ext = f.type.includes("png") ? "png" : f.type.split("/")[1] || "bin";
              files.push(new File([f], `pegado-${Date.now()}.${ext}`, { type: f.type }));
            }
          }
        });
      }
      const media_files = files.filter((f) =>
        /\.(png|jpe?g|gif|webp|avif|bmp|mp3|wav|ogg|oga|m4a|flac|aac|opus|weba|mp4|mov|webm|mkv|avi|m4v)$/i.test(f.name),
      );
      if (media_files.length === 0) return;
      e.preventDefault();
      for (const f of media_files) void doQuickUpload(f);
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploadOpen, editing, addItemFor, profileOpen, dupesOpen, detail, visibility]);

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
      className="shell"
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

      {/* ==================== SIDEBAR ==================== */}
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-stripes" aria-hidden>
            ▮▮▮
          </span>
          <span>Biblioteca <b>MM</b></span>
        </div>

        <nav className="snav">
          {NAV_MAIN.map((t) => (
            <button
              key={t.key}
              className={`snav-item${nav === t.key ? " active" : ""}`}
              onClick={() => {
                setNav(t.key);
                if (t.key !== "trash" && t.key !== "collections") setActiveTag(null);
              }}
            >
              {t.icon} {t.label}
            </button>
          ))}
        </nav>

        <div className="snav-section">
          <p className="snav-label">Vistas</p>
          <button
            className={`snav-item${minRating ? " active" : ""}`}
            onClick={() => {
              setMinRating((v) => !v);
              setNav("all");
            }}
          >
            ★ Favoritos
          </button>
          <button
            className={`snav-item${scope === "team" ? " active" : ""}`}
            onClick={() => setScope((s) => (s === "team" ? "mine" : "team"))}
            title="Biblioteca propia + recursos del equipo"
          >
            👥 Del equipo
          </button>
        </div>

        <div className="snav-section grow">
          <p className="snav-label">Mis colecciones</p>
          {collections.length === 0 && <p className="snav-empty">Crea la primera →</p>}
          {collections.map((c) => (
            <button
              key={c.id}
              className={`snav-item${selectedCol?.id === c.id && nav !== "collections" ? " active" : ""}`}
              onClick={() => {
                setSelectedCol(c);
                setNav("all");
              }}
            >
              {c.is_project ? "🎬" : "📚"} {c.name}
              <span className="chip-count">{c.item_count}</span>
            </button>
          ))}
        </div>

        <div className="snav-bottom">
          <button className="snav-item" onClick={() => setHelpOpen(true)}>
            ⌨️ Atajos
          </button>
          <button className="snav-item" onClick={openDuplicates}>
            👯 Duplicados
          </button>
          <button className="snav-item" onClick={() => setProfileOpen(true)}>
            👤 {user.name || "Perfil"}
          </button>
        </div>
      </aside>

      {/* ==================== MAIN ==================== */}
      <main className="main">
        <div className="topbar-main">
          <input
            className="search"
            ref={searchInput}
            placeholder="Búsqueda rápida...   ( / )"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="Buscar"
          />
          <button className="primary" onClick={() => setUploadOpen(true)}>
            ⇪ Importar recurso
          </button>
        </div>

        {/* ---- toolbars (solo en vistas de biblioteca) ---- */}
        {nav !== "collections" && (
          <>
            <div className="lib-toolbar">
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
                <option value="rating:desc">★ Mejor valorados</option>
              </select>
              <select
                aria-label="Alcance"
                value={scope}
                onChange={(e) => setScope(e.target.value as "mine" | "team")}
                title="Mías (+ equipo público)"
              >
                <option value="mine">Mías</option>
                <option value="team">+ Equipo</option>
              </select>
              {!inTrash && (
                <select
                  aria-label="Seleccionar colección"
                  value={selectedCol?.id ?? ""}
                  onChange={(e) => {
                    const id = Number(e.target.value);
                    setSelectedCol(collections.find((c) => c.id === id) ?? null);
                  }}
                >
                  <option value="">— filtro colección —</option>
                  {collections.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.is_project ? "🎬 " : ""}
                      {c.name} ({c.item_count})
                    </option>
                  ))}
                </select>
              )}
              {selectedCol && !inTrash && (
                <>
                  <a className="chip" href={exportUrl(selectedCol.id, "txt")} download aria-label="Exportar lista txt">
                    ⬇ .txt
                  </a>
                  <a className="chip" href={exportUrl(selectedCol.id, "csv")} download aria-label="Exportar lista csv">
                    ⬇ .csv
                  </a>
                </>
              )}
              <span className="spacer" />
              <button
                className="ghost"
                onClick={() => setView((v) => (v === "grid" ? "list" : "grid"))}
                title="Cambiar vista"
              >
                {view === "grid" ? "≡ Lista" : "▦ Grid"}
              </button>
            </div>

            {!inTrash && (
              <div className="collections-bar">
                <span className="snav-label inline">Tags</span>
                {activeTag && (
                  <button className="chip active" onClick={() => setActiveTag(null)} aria-label="Quitar filtro">
                    ✕ {activeTag}
                  </button>
                )}
                {tagChips
                  .filter((c) => c.tag !== activeTag)
                  .slice(0, 14)
                  .map((c) => (
                    <button key={c.tag} className="chip" onClick={() => setActiveTag(c.tag)}>
                      {c.tag} <span className="chip-count">{c.count}</span>
                    </button>
                  ))}
                {colError && <span className="error">{colError}</span>}
              </div>
            )}

            {suggestions && (
              <div className="sugg-bar">
                <span className="snav-label inline">🤖 Sugerencias para «{suggestions.title}»</span>
                {suggestions.suggestions.map((t) => (
                  <button key={t} className="chip" onClick={() => applySuggestion(t)} title="Aplicar este tag">
                    + {t}
                  </button>
                ))}
                <button className="chip active" onClick={applyAllSuggestions}>
                  ✓ aplicar todas
                </button>
                <button className="ghost" onClick={() => setSuggestions(null)}>
                  ✕
                </button>
              </div>
            )}

            {selectedIds.size > 0 && (
              <div className="bulk-bar">
                <strong>{selectedIds.size} seleccionado(s)</strong>
                {!inTrash && (
                  <>
                    <input
                      placeholder="tags del lote (coma)"
                      value={bulkTagsText}
                      onChange={(e) => setBulkTagsText(e.target.value)}
                      aria-label="Tags para el lote"
                    />
                    <button className="chip" disabled={bulkBusy} onClick={() => runBulk("add_tag")}>＋ tags</button>
                    <button className="chip" disabled={bulkBusy} onClick={() => runBulk("remove_tag")}>－ tags</button>
                    <select
                      aria-label="Colección destino del lote"
                      value={bulkColId}
                      onChange={(e) => setBulkColId(Number(e.target.value))}
                    >
                      <option value="">— añadir a colección…</option>
                      {collections.map((c) => (
                        <option key={c.id} value={c.id}>{c.name}</option>
                      ))}
                    </select>
                    <button className="chip" disabled={bulkBusy || !bulkColId} onClick={() => runBulk("add_to_collection")}>
                      → añadir
                    </button>
                    <button className="chip" disabled={bulkBusy} onClick={() => runBulk("set_visibility")}>👥 team</button>
                    <input
                      className="rename-input"
                      placeholder="renombrar: meme-{date}-{n}"
                      value={renamePattern}
                      onChange={(e) => setRenamePattern(e.target.value)}
                      aria-label="Patrón de renombrado"
                    />
                    <button
                      className="chip"
                      disabled={bulkBusy || !renamePattern.trim()}
                      onClick={() => runBulk("rename")}
                      title="Renombra con el patrón ({n}=orden, {date}=hoy, {title}=nombre actual)"
                    >
                      ✏️ renombrar
                    </button>
                    <button className="chip danger" disabled={bulkBusy} onClick={() => runBulk("delete")}>🗑 papelera</button>
                  </>
                )}
                {inTrash && (
                  <>
                    <button className="chip" disabled={bulkBusy} onClick={() => runBulk("restore")}>↺ restaurar</button>
                    <button className="chip danger" disabled={bulkBusy} onClick={() => runBulk("purge")}>🔥 purgar</button>
                  </>
                )}
                <button className="ghost" onClick={() => setSelectedIds(new Set())}>cancelar</button>
              </div>
            )}
          </>
        )}

        {/* ---- contenido principal ---- */}
        {nav === "stats" ? (
          <div className="stats-page">
            <h2>📊 Estadísticas de tu biblioteca</h2>
            {!stats && <p className="loading">Cargando…</p>}
            {stats && (
              <>
                <div className="stats-cards">
                  {(["image", "video", "audio"] as MediaKind[]).map((k) => (
                    <div className="stat-card" key={k}>
                      <p className="stat-icon">{KIND_ICON[k]}</p>
                      <strong>{stats.by_kind[k]?.count ?? 0}</strong>
                      <span className="media-meta">
                        {fmtSize(stats.by_kind[k]?.size ?? 0)}
                      </span>
                    </div>
                  ))}
                  <div className="stat-card">
                    <p className="stat-icon">🗑</p>
                    <strong>{stats.trash_count}</strong>
                    <span className="media-meta">papelera</span>
                  </div>
                </div>
                <p className="sub total-line">Peso total: {fmtSize(stats.total_size)}</p>
                <p className="snav-label">Tags más usados</p>
                <div className="tag-chips">
                  {stats.top_tags.map((t) => (
                    <span key={t.tag} className="chip static">{t.tag} <b>{t.count}</b></span>
                  ))}
                  {stats.top_tags.length === 0 && <span className="muted">sin tags todavía</span>}
                </div>
                <p className="snav-label">Subidas por mes</p>
                <div className="months-bars">
                  {stats.months.map((m) => {
                    const max = Math.max(...stats.months.map((x) => x.count), 1);
                    return (
                      <div className="month-col" key={m.month}>
                        <div className="bar" style={{ height: `${(m.count / max) * 100}%` }} title={`${m.count} subida(s)`}>
                          <span>{m.count}</span>
                        </div>
                        <p className="media-meta">{m.month.slice(5)}</p>
                      </div>
                    );
                  })}
                  {stats.months.length === 0 && <span className="muted">sin actividad</span>}
                </div>
              </>
            )}
          </div>
        ) : nav === "collections" ? (
          <div className="collections-page">
            <h2>Colecciones y ediciones</h2>
            <p className="sub">📚 colección = agrupación · 🎬 proyecto de edición (exportable a .txt/.csv)</p>
            <button className="primary" onClick={handleCreateCollection}>＋ Nueva colección</button>
            <div className="collections-list">
              {collections.map((c) => (
                <div className="col-row" key={c.id}>
                  <span className="col-name">
                    {c.is_project ? "🎬" : "📚"} {c.name}
                  </span>
                  <span className="muted">{c.item_count} recurso(s)</span>
                  <span className="spacer" />
                  <a className="chip" href={exportUrl(c.id, "txt")} download title="Exportar .txt">⬇ txt</a>
                  <a className="chip" href={exportUrl(c.id, "csv")} download title="Exportar .csv">⬇ csv</a>
                  <a className="chip" href={exportZipUrl(c.id)} download title="Descargar ZIP con los ficheros">📦 zip</a>
                  <button
                    className="chip"
                    onClick={() => createShareLink(c)}
                    title="Crear/rota el enlace público (sin login, revocable)"
                  >
                    🔗 compartir
                  </button>
                  <button
                    className="chip"
                    onClick={async () => {
                      if (!window.confirm(`¿Revocar el enlace público de "${c.name}"?`)) return;
                      await revokeCollectionShare(c);
                    }}
                    title="Revocar el enlace compartido"
                  >
                    🚫 revocar
                  </button>
                  <button
                    className="chip"
                    onClick={() => {
                      setSelectedCol(c);
                      setNav("all");
                    }}
                  >
                    abrir
                  </button>
                  <button
                    className="chip danger"
                    onClick={async () => {
                      if (!window.confirm(`¿Borrar la colección "${c.name}"? (los recursos no se borran)`)) return;
                      await deleteCollection(c.id);
                      if (selectedCol?.id === c.id) setSelectedCol(null);
                      await loadCollections();
                    }}
                  >
                    🗑
                  </button>
                </div>
              ))}
            </div>
            {shareLinkFor && (
              <div className="share-result">
                <p className="dupe-head">
                  🔗 Enlace de «{shareLinkFor.name}» copiable (visitable sin login):
                </p>
                <div className="row">
                  <input readOnly value={shareLinkFor.link} aria-label="Enlace compartido" onClick={(e) => (e.target as HTMLInputElement).select()} />
                  <button
                    className="primary"
                    onClick={() => void navigator.clipboard?.writeText(shareLinkFor.link).then(() => toast("🔗 enlace copiado"))}
                  >
                    Copiar
                  </button>
                  <button className="ghost" onClick={() => setShareLinkFor(null)}>cerrar</button>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="lib">
            {loading && <p className="loading">Cargando…</p>}
            {listError && <p className="error">{listError}</p>}
            {!loading && !listError && items.length === 0 && (
              <div className="empty">
                <p>
                  {inTrash
                    ? "La papelera está vacía."
                    : debouncedQ || activeTag || selectedCol || minRating
                      ? "Sin resultados. Prueba otra búsqueda o quita el filtro."
                      : "Nada por aquí todavía. Sube, pega (Ctrl+V) o arrastra tus recursos."}
                </p>
              </div>
            )}
            {!loading && items.length > 0 && (
              <>
                <p className="sub count">
                  {selectedCol && !inTrash ? `Colección "${selectedCol.name}" · ` : ""}
                  {inTrash ? "Papelera · " : ""}
                  {items.length}/{total} recursos
                </p>
                {view === "grid" ? (
                  <div className="media-grid">
                    {items.map((item) => (
                      <GridCard
                        key={item.id}
                        item={item}
                        trash={inTrash}
                        selected={selectedIds.has(item.id)}
                        onToggleSelect={() => toggleSelect(item.id)}
                        onOpen={() => setDetail(item)}
                        onEdit={() => openEdit(item)}
                        onDelete={() => handleDelete(item)}
                        onRestore={() => handleRestore(item)}
                        onPurge={() => handlePurge(item)}
                        onAddToCollection={() => setAddItemFor(item)}
                        hasCollections={collections.length > 0}
                        activeColId={selectedCol?.id}
                        onRemoveFromCol={() => handleRemoveFromCollection(item)}
                        onTagClick={setActiveTag}
                        onRate={(s) => rateItem(item.id, s)}
                      />
                    ))}
                  </div>
                ) : (
                  <table className="list-table">
                    <thead>
                      <tr>
                        <th />
                        <th>Título</th>
                        <th>Tipo</th>
                        <th>Tags</th>
                        <th>★</th>
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
                          inTrash={inTrash}
                          selected={selectedIds.has(item.id)}
                          onToggleSelect={() => toggleSelect(item.id)}
                          onOpen={() => setDetail(item)}
                          onRestore={() => handleRestore(item)}
                          onPurge={() => handlePurge(item)}
                          onDelete={() => handleDelete(item)}
                          onEdit={() => openEdit(item)}
                          onAddToCollection={() => setAddItemFor(item)}
                          onRate={(s) => rateItem(item.id, s)}
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
          </div>
        )}
      </main>

      {/* ==================== OVERLAYS ==================== */}
      <div className="toast-stack" aria-live="polite">
        {toasts.map((t) => (
          <div className="toast" key={t.id}>
            {t.msg}
          </div>
        ))}
      </div>

      {helpOpen && (
        <div className="overlay" onClick={() => setHelpOpen(false)}>
          <div className="card help-card" onClick={(e) => e.stopPropagation()}>
            <h2>⌨️ Atajos</h2>
            <dl className="help-list">
              <div><dt>/</dt><dd>Buscar</dd></div>
              <div><dt>Ctrl+V</dt><dd>Subir lo que tengas copiado (sin duplicar)</dd></div>
              <div><dt>I / O</dt><dd>Marcar In / Out del clip (en el detalle)</dd></div>
              <div><dt>← →</dt><dd>Recurso anterior / siguiente</dd></div>
              <div><dt>Esc</dt><dd>Cerrar lo que esté abierto</dd></div>
            </dl>
            <div className="row">
              <button className="ghost" onClick={() => setHelpOpen(false)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}
      {detail && (
        <DetailPanel
          item={items.find((i) => i.id === detail.id) ?? detail}
          onClose={() => setDetail(null)}
          onChanged={(upd) => setItems((prev) => prev.map((i) => (i.id === upd.id ? upd : i)))}
          onAddToCollectionPicker={(it) => setAddItemFor(it)}
          onNavigate={(dir: 1 | -1) => {
            if (!detail) return;
            const idx = items.findIndex((i) => i.id === detail.id);
            const next = items[idx + dir];
            if (next) setDetail(next);
          }}
          onTrimCreated={(frag: MediaItem) => {
            toast(`✂ fragmento creado: ${frag.title}`);
            Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
          }}
          onCreated={(frag: MediaItem) => {
            toast(`🎧 audio extraído: ${frag.title} — ábrelo y recorta tu SFX con I/O`);
            Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
          }}
          onCompressQueued={(itemId: number) => trackJob(itemId)}
          onSplitCreated={(frags: MediaItem[]) => {
            if (frags.length > 0) {
              toast(`✂ separado por silencios: ${frags.length} parte(s) nueva(s)`);
              Promise.all([loadItems(0, true), loadTags(), loadCollections()]);
            }
          }}
        />
      )}

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

            <div className="detail-section gemini-section">
              <p className="snav-label">🌐 Servidor (backend)</p>
              <p className="sub">
                Dirección del backend en uso: <code>{apiBase}</code>. Cámbiala
                para apuntar a otra máquina (ej. <code>http://192.168.1.10:8000</code>).
              </p>
              <input
                placeholder="http://192.168.1.10:8000"
                value={apiBase}
                onChange={(e) => {
                  setApiBaseState(e.target.value);
                  setApiSaved(false);
                }}
                aria-label="Dirección del servidor"
              />
              <div className="row">
                <button className="primary" onClick={saveApiBase} title="Guarda y reconecta al momento">
                  {apiSaved ? "Guardado ✓" : "Guardar y reconectar"}
                </button>
                {getApiBase() !== apiBase && (
                  <button
                    className="ghost"
                    onClick={() => {
                      setApiBaseState(getApiBase());
                      setApiSaved(true);
                    }}
                  >
                    Revertir
                  </button>
                )}
              </div>
              <p className="sub tiny-note">
                Se guarda en este dispositivo (localStorage): cada teléfono/oficina apunta a donde le toca.
              </p>
            </div>

            <div className="detail-section gemini-section">
              <p className="snav-label">🤖 Auto-tag con IA — llave de Gemini</p>
              {geminiStatus?.set ? (
                <p className="sub">
                  Configurada {geminiStatus.source === "app" ? "desde la app" : "en .env"} ({geminiStatus.tail})
                </p>
              ) : (
                <p className="sub">Sin llave: se usa la heurística local (tags por tamaño/orientación/nombre).</p>
              )}
              <input
                type="password"
                placeholder="Pega tu GEMINI_API_KEY (AIza...)"
                value={geminiKey}
                onChange={(e) => setGeminiKeyValue(e.target.value)}
                aria-label="Llave de Gemini"
              />
              <div className="row">
                <button
                  type="button"
                  className="ghost"
                  disabled={geminiBusy}
                  onClick={() => saveGeminiKey()}
                  title="Vacío = borra la llave"
                >
                  {geminiBusy ? "Guardando…" : "Guardar llave"}
                </button>
                {geminiStatus?.set && geminiStatus.source === "app" && (
                  <button
                    type="button"
                    className="ghost danger"
                    onClick={() => setGeminiKey("").then(setGeminiStatus).catch(() => {})}
                  >
                    Quitar
                  </button>
                )}
              </div>
              <p className="sub tiny-note">
                Se guarda en la BD del proyecto (viaja con tu backup), nunca en .env ni en el repo.
              </p>
            </div>
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
              multiple
              accept="image/*,audio/*,video/*"
              onChange={(e) => {
                const fs = Array.from(e.target.files ?? []);
                setSelectedFiles(fs);
                if (fs.length === 1 && !title.trim()) {
                  setTitle(fs[0].name.replace(/\.[^.]+$/, ""));
                }
              }}
            />
            {selectedFiles.length > 1 && (
              <p className="sub">
                {selectedFiles.length} archivos: se suben con su nombre como título y comparten
                tags/descripción/visibilidad. Los videos se comprimen en background.
              </p>
            )}
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
              <button className="primary" disabled={selectedFiles.length === 0 || uploading}>
                {uploading
                  ? "Subiendo..."
                  : selectedFiles.length > 1
                    ? `Subir ${selectedFiles.length} archivos`
                    : "Subir"}
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
                <input placeholder="Sony a7, A6000..." value={editDraft.camera} onChange={(e) => setEditDraft({ ...editDraft, camera: e.target.value })} />
              </div>
              <div>
                <p className="label">Proyecto</p>
                <input placeholder="Intro, Podcast 12..." value={editDraft.proyecto} onChange={(e) => setEditDraft({ ...editDraft, proyecto: e.target.value })} />
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
              <button type="button" className="ghost" onClick={() => setEditing(null)}>Cancelar</button>
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
              <p className="sub">Primero crea una colección.</p>
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

      {dupesOpen && (
        <div className="overlay" onClick={() => setDupesOpen(false)}>
          <div className="card dupe-card" onClick={(e) => e.stopPropagation()}>
            <h2>Duplicados por contenido</h2>
            {dupes.length === 0 && similar.length === 0 && (
              <p className="sub">No hay duplicados. ¡Limpio!</p>
            )}
            {dupes.map((g, i) => (
              <div className="dupe-group" key={`exact-${i}`}>
                <p className="dupe-head">
                  {g.length} copias idénticas ({fmtSize(g[0].size)} cada una)
                </p>
                <ul>
                  {g.map((it) => (
                    <li key={it.id}>
                      {it.title} <span className="muted">· {it.created_at.slice(0, 10)}</span>
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
            {similar.length > 0 && (
              <>
                <h2>👁 Muy parecidas (visual)</h2>
                <p className="sub">
                  Mismo look con bytes distintos (re-descargas, re-saves, compresiones).
                  Revísalas antes de borrar: el parecido no garantiza que sobren.
                </p>
                {similar.map((g, i) => (
                  <div className="dupe-group" key={`similar-${i}`}>
                    <p className="dupe-head">{g.length} imágenes muy similares</p>
                    <ul>
                      {g.map((it) => (
                        <li key={it.id}>
                          {it.title} <span className="muted">· {fmtSize(it.size)}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </>
            )}
            <div className="row">
              <button className="ghost" onClick={() => setDupesOpen(false)}>Cerrar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ======================================================== subcomponentes */

function Thumb({ item, className }: { item: MediaItem; className?: string }) {
  return item.has_thumb ? (
    <img src={mediaUrl(item.id, "thumb")} alt={item.title} className={className} loading="lazy" decoding="async" />
  ) : (
    <span className="media-icon" role="img">
      {KIND_ICON[item.kind]}
    </span>
  );
}

function Stars({
  rating,
  onRate,
  big,
}: {
  rating: number;
  onRate?: (stars: number) => void;
  big?: boolean;
}) {
  return (
    <span className={`stars${big ? " big" : ""}`}>
      {[1, 2, 3, 4, 5].map((s) => (
        <button
          key={s}
          className={`star${s <= rating ? " on" : ""}`}
          onClick={(e) => {
            e.stopPropagation();
            onRate?.(s);
          }}
          aria-label={`Valorar ${s} estrella${s > 1 ? "s" : ""}`}
          title={onRate ? `Valorar ${s}` : `${rating} estrellas`}
        >
          ★
        </button>
      ))}
    </span>
  );
}

function GridCard({
  item,
  trash,
  selected,
  onToggleSelect,
  onOpen,
  onEdit,
  onDelete,
  onRestore,
  onPurge,
  onAddToCollection,
  onRemoveFromCol,
  hasCollections,
  activeColId,
  onTagClick,
  onRate,
}: {
  item: MediaItem;
  trash?: boolean;
  selected: boolean;
  onToggleSelect?: () => void;
  onOpen?: () => void;
  onEdit?: () => void;
  onDelete?: () => void;
  onRestore?: () => void;
  onPurge?: () => void;
  onAddToCollection?: () => void;
  onRemoveFromCol?: () => void;
  hasCollections?: boolean;
  activeColId?: number;
  onTagClick?: (t: string) => void;
  onRate?: (stars: number) => void;
}) {
  return (
    <article className={`media-card${selected ? " selected" : ""}`}>
      <button className="media-visual" onClick={onOpen} aria-label={`Abrir ${item.title}`}>
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
            {item.tags.slice(0, 6).map((t) => (
              <button
                key={t}
                className="mini-chip"
                onClick={() => onTagClick?.(t)}
                aria-label={`Filtrar por tag ${t}`}
              >
                {t}
              </button>
            ))}
            {onRate && <Stars rating={item.rating} onRate={(s) => onRate(s)} />}
          </div>
        )}
        <span className="media-meta">
          {fmtSize(item.size)}
          {item.duration_s !== null && item.duration_s !== undefined ? ` · ${fmtDuration(item.duration_s)}` : ""}
        </span>
        {item.description && <span className="media-meta desc">{item.description}</span>}
      </div>
      <div className="media-actions">
        {trash && onRestore && (
          <button className="ghost" onClick={onRestore} aria-label={`Restaurar ${item.title}`} title="Restaurar">↺</button>
        )}
        {onRemoveFromCol && activeColId && (
          <button className="ghost" onClick={onRemoveFromCol} aria-label={`Quitar ${item.title} de la colección`} title="Quitar de la colección">－</button>
        )}
        {!trash && hasCollections && onAddToCollection && (
          <button className="ghost" onClick={onAddToCollection} aria-label={`Agregar ${item.title} a una colección`} title="Agregar a una colección">＋</button>
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
        {!trash && onEdit && (
          <button className="ghost" onClick={onEdit} aria-label={`Editar ${item.title}`} title="Editar">✏️</button>
        )}
        {!trash && onDelete && (
          <button className="ghost danger" onClick={onDelete} aria-label={`Eliminar ${item.title}`} title="A la papelera">🗑</button>
        )}
        {trash && onPurge && (
          <button className="ghost danger" onClick={onPurge} aria-label={`Purgar ${item.title}`} title="Borrar definitivo">🔥</button>
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
  onOpen,
  onDelete,
  onEdit,
  onRestore,
  onPurge,
  onAddToCollection,
  onRate,
}: {
  item: MediaItem;
  inTrash: boolean;
  selected: boolean;
  onToggleSelect: () => void;
  onOpen: () => void;
  onDelete?: () => void;
  onEdit?: () => void;
  onRestore?: () => void;
  onPurge?: () => void;
  onAddToCollection?: () => void;
  onRate?: (stars: number) => void;
}) {
  return (
    <tr className={selected ? "selected" : ""}>
      <td>
        <input type="checkbox" checked={selected} onChange={onToggleSelect} aria-label={`Seleccionar ${item.title}`} />
      </td>
      <td>
        <button className="ghost inline" onClick={onOpen} aria-label={`Abrir ${item.title}`}>
          <span className="list-thumb">
            <Thumb item={item} className="mini" />
          </span>
          {item.title}
        </button>
      </td>
      <td>{KIND_ICON[item.kind]}</td>
      <td className="muted">{item.tags.join(", ")}</td>
      <td>{onRate ? <Stars rating={item.rating} onRate={(s) => onRate(s)} /> : "★".repeat(item.rating)}</td>
      <td>{fmtSize(item.size)}</td>
      <td>{fmtDuration(item.duration_s)}</td>
      <td className="row-actions">
        {inTrash && onRestore && (
          <button className="ghost" onClick={onRestore} title="Restaurar">↺</button>
        )}
        {inTrash && onPurge && (
          <button className="ghost danger" onClick={onPurge} title="Purgar">🔥</button>
        )}
        {!inTrash && (
          <>
            {onAddToCollection && (
              <button className="ghost" onClick={onAddToCollection} title="Agregar a colección">＋</button>
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
              <button className="ghost" onClick={onEdit} title="Editar">✏️</button>
            )}
            {onDelete && (
              <button className="ghost danger" onClick={onDelete} title="A la papelera">🗑</button>
            )}
          </>
        )}
      </td>
    </tr>
  );
}

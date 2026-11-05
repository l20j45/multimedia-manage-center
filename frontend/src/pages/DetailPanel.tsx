import { useEffect, useRef, useState } from "react";
import {
  compressMedia,
  extractAudio,
  mediaUrl,
  rethumbMedia,
  splitMedia,
  trimMedia,
  updateMedia,
  type MediaItem,
  type MediaKind,
} from "../lib/api";

const KIND_LABEL: Record<MediaKind, string> = { audio: "Audio", image: "Imagen", video: "Video" };

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

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString("es", { day: "2-digit", month: "short", year: "numeric" }) +
    " · " + d.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" });
}

/**
 * Vista de detalle individual (estilo papra): panel izquierdo con INFORMACIÓN
 * + ACTIONS, panel derecho con el CONTENIDO (player/preview) y NOTAS debajo.
 * Todo editable en línea: título, rating, tags, meta, visibilidad, descripción.
 */
export default function DetailPanel({
  item,
  onClose,
  onChanged,
  onAddToCollectionPicker,
  onTrimCreated,
  onCreated,
  onNavigate,
  onCompressQueued,
  onSplitCreated,
}: {
  item: MediaItem;
  onClose: () => void;
  onChanged: (updated: MediaItem) => void;
  onAddToCollectionPicker: (item: MediaItem) => void;
  onTrimCreated: (frag: MediaItem) => void;
  onCreated?: (item: MediaItem) => void;
  onNavigate?: (dir: 1 | -1) => void;
  onCompressQueued?: (itemId: number) => void;
  onSplitCreated?: (frags: MediaItem[]) => void;
}) {
  const [extracting, setExtracting] = useState(false);
  const [compressing, setCompressing] = useState(false);
  const [splitting, setSplitting] = useState(false);
  const [notice, setNotice] = useState("");
  const [cur, setCur] = useState(item);
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState(item.title);
  const [tagDraft, setTagDraft] = useState("");
  const [notes, setNotes] = useState(item.description ?? "");
  const [notesBusy, setNotesBusy] = useState(false);
  const [error, setError] = useState("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  // el reproductor presente según el tipo (para las teclas I/O)
  function timeOf(): number {
    return videoRef.current?.currentTime ?? audioRef.current?.currentTime ?? 0;
  }
  const [trimIn, setTrimIn] = useState<number | null>(null);
  const [trimOut, setTrimOut] = useState<number | null>(null);
  const [trimBusy, setTrimBusy] = useState(false);

  useEffect(() => {
    setCur(item);
    setTitleDraft(item.title);
    setNotes(item.description ?? "");
  }, [item]);

  // teclas I/O para marcar In/Out y ←/→ para navegar mientras esté abierto
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const t = e.target as HTMLElement;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName)) return;
      if (e.key === "I") setTrimIn(timeOf());
      if (e.key === "O") setTrimOut(timeOf());
      if (e.key === "ArrowRight") onNavigate?.(1);
      if (e.key === "ArrowLeft") onNavigate?.(-1);
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onNavigate]);

  async function cutSegment() {
    if (trimIn === null || trimOut === null) {
      setError("Marca In (I) y Out (O) primero.");
      return;
    }
    if (trimOut <= trimIn) {
      setError("Out debe ir después de In.");
      return;
    }
    setTrimBusy(true);
    try {
      const frag = await trimMedia(cur.id, trimIn, trimOut);
      setTrimIn(null);
      setTrimOut(null);
      onTrimCreated(frag);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cortar");
    } finally {
      setTrimBusy(false);
    }
  }

  async function useThisFrame() {
    const v = videoRef.current;
    if (!v) return;
    try {
      const updated = await rethumbMedia(cur.id, v.currentTime);
      setCur(updated);
      onChanged(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al re-generar el poster");
    }
  }

  async function patch(data: Parameters<typeof updateMedia>[1]) {
    setError("");
    try {
      const updated = await updateMedia(cur.id, data);
      setCur(updated);
      onChanged(updated);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al guardar");
    }
  }

  async function doExtractAudio() {
    setExtracting(true);
    setError("");
    try {
      const frag = await extractAudio(cur.id);
      onCreated?.(frag);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al extraer audio");
    } finally {
      setExtracting(false);
    }
  }

  async function doCompress() {
    setCompressing(true);
    setError("");
    setNotice("");
    try {
      await compressMedia(cur.id); // 202: encola y responde, no espera ffmpeg
      setNotice("🗜 Compresión en background… te avisamos cuando termine.");
      onCompressQueued?.(cur.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al comprimir");
    } finally {
      setCompressing(false);
    }
  }

  async function doSplit() {
    setSplitting(true);
    setError("");
    setNotice("");
    try {
      const frags = await splitMedia(cur.id);
      setNotice(
        frags.length === 0
          ? "Solo se detectó sonido continuo: nada que separar."
          : `✂ ${frags.length} parte(s) creadas por silencios.`,
      );
      onSplitCreated?.(frags);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al separar el audio");
    } finally {
      setSplitting(false);
    }
  }

  function addTags(raw: string): string[] {
    const clean = raw.split(",").map((t) => t.trim().toLowerCase()).filter(Boolean);
    const next = [...new Set([...cur.tags, ...clean])];
    void patch({ tags: next });
    return next;
  }

  function removeTag(tag: string) {
    void patch({ tags: cur.tags.filter((t) => t !== tag) });
  }

  async function saveNotes() {
    setNotesBusy(true);
    await patch({ description: notes });
    setNotesBusy(false);
  }

  function askCamara() {
    const v = window.prompt("Cámara / dispositivo:", cur.meta?.camera ?? "");
    if (v === null) return;
    void patch({ meta: { ...(cur.meta ?? {}), camera: v.trim() } });
  }
  function askProyecto() {
    const v = window.prompt("Proyecto / edición:", cur.meta?.proyecto ?? "");
    if (v === null) return;
    void patch({ meta: { ...(cur.meta ?? {}), proyecto: v.trim() } });
  }

  return (
    <div className="overlay" onClick={onClose}>
      <div className="detail two-panel" onClick={(e) => e.stopPropagation()}>
        {/* ---------- panel izquierdo: INFORMACIÓN ---------- */}
        <div className="detail-info">
          <div className="detail-head">
            {renaming ? (
              <input
                autoFocus
                value={titleDraft}
                onChange={(e) => setTitleDraft(e.target.value)}
                onBlur={() => {
                  setRenaming(false);
                  if (titleDraft.trim() && titleDraft !== cur.title) void patch({ title: titleDraft.trim() });
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") e.currentTarget.blur();
                }}
              />
            ) : (
              <h2 onClick={() => setRenaming(true)} title="Clic para renombrar">
                {cur.title} <span className="edit-ico">✏️</span>
              </h2>
            )}
            <button className="ghost x" onClick={onClose} aria-label="Cerrar detalle">✕</button>
          </div>
          <p className="detail-id">{cur.mime} · {cur.kind}</p>

          <div className="detail-actions">
            <a className="ghost" href={mediaUrl(cur.id, "file")} download={cur.filename} aria-label="Descargar">
              ⬇ Descargar
            </a>
            {cur.kind === "video" && (
              <button className="ghost" onClick={doExtractAudio} disabled={extracting} title="Extrae la pista de audio como mp3 nuevo (para tu flujo SFX)">
                {extracting ? "Extrayendo…" : "🎧 Extraer audio"}
              </button>
            )}
            {(cur.kind === "video" || cur.kind === "image") && (
              <button
                className="ghost"
                onClick={doCompress}
                disabled={compressing}
                title="Optimiza el original en background (video: H.264+a escala máx; imagen: JPEG/WebP). Se reemplaza solo si pesa menos."
              >
                {compressing ? "En cola…" : "🗜 Comprimir"}
              </button>
            )}
            <button
              className="ghost"
              onClick={async () => {
                setError("");
                try {
                  const upd = await rethumbMedia(cur.id, null);
                  setCur(upd);
                  onChanged(upd);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Error al regenerar miniatura");
                }
              }}
              title="Regenera miniatura/frame/waveform según el tipo (para recursos que quedaron sin thumb)"
            >
              ♻ Miniatura
            </button>
            <button className="ghost" onClick={() => onAddToCollectionPicker(cur)}>＋ Colección</button>
            {cur.deleted ? (
              <span className="chip danger-static">En papelera</span>
            ) : null}
          </div>

          <div className="detail-tags">
            {cur.tags.map((t) => (
              <button
                key={t}
                className="chip"
                title="Quitar tag"
                onClick={() => removeTag(t)}
                aria-label={`Quitar tag ${t}`}
              >
                {t} ✕
              </button>
            ))}
            <input
              className="tag-add"
              placeholder="+ tag y Enter"
              value={tagDraft}
              onChange={(e) => setTagDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && tagDraft.trim()) {
                  addTags(tagDraft);
                  setTagDraft("");
                }
              }}
              aria-label="Añadir tag"
            />
          </div>

          <div className="detail-section">
            <p className="snav-label">INFORMACIÓN</p>
            <dl className="info-rows">
              <div><dt>Tipo</dt><dd>{KIND_LABEL[cur.kind]}</dd></div>
              <div><dt>Formato</dt><dd className="mono">{cur.mime}</dd></div>
              <div><dt>Tamaño</dt><dd>{fmtSize(cur.size)}</dd></div>
              <div><dt>Duración</dt><dd>{cur.duration_s !== null ? `${cur.duration_s}s` : "—"}</dd></div>
              <div><dt>Creado</dt><dd>{fmtDate(cur.created_at)}</dd></div>
              <div>
                <dt>Visibilidad</dt>
                <dd>
                  <button
                    className="chip"
                    onClick={() => void patch({ visibility: cur.visibility === "team" ? "private" : "team" })}
                    title="Clic para alternar privado/equipo"
                  >
                    {cur.visibility === "team" ? "👥 Del equipo" : "🔒 Privada"}
                  </button>
                </dd>
              </div>
            </dl>
          </div>

          <div className="detail-section">
            <p className="snav-label">PROPIEDADES</p>
            <dl className="info-rows">
              <div>
                <dt>📹 Cámara</dt>
                <dd>
                  {cur.meta?.camera ? cur.meta.camera : <span className="muted">No definido</span>}
                  <button className="link tiny" onClick={askCamara}>edit</button>
                </dd>
              </div>
              <div>
                <dt>🎬 Proyecto</dt>
                <dd>
                  {cur.meta?.proyecto ? cur.meta.proyecto : <span className="muted">No definido</span>}
                  <button className="link tiny" onClick={askProyecto}>edit</button>
                </dd>
              </div>
            </dl>
          </div>

          {error && <p className="error">{error}</p>}
          {notice && <p className="sub">{notice}</p>}
        </div>

        {/* ---------- panel derecho: CONTENIDO + NOTAS ---------- */}
        <div className="detail-content">
          <div className="detail-preview">
            {cur.kind === "video" && (
              <video key={cur.path} controls src={mediaUrl(cur.id, "file")} ref={videoRef} />
            )}
            {cur.kind === "audio" && (
              <audio key={cur.path} controls src={mediaUrl(cur.id, "file")} ref={audioRef} />
            )}
            {cur.kind === "image" && <img src={mediaUrl(cur.id, "file")} alt={cur.title} />}
          </div>
          <p className="detail-hint">
            ← → navega · I marca In · O marca Out · Esc cierra
          </p>

          {(cur.kind === "video" || cur.kind === "audio") && (
            <div className="trim-bar detail-trim">
              <button
                className="chip"
                onClick={() => setTrimIn(timeOf())}
                title="Marcar In (tecla I)"
              >
                [In{trimIn === null ? "" : ` ${trimIn.toFixed(1)}s`}]
              </button>
              <button
                className="chip"
                onClick={() => setTrimOut(timeOf())}
                title="Marcar Out (tecla O)"
              >
                [Out{trimOut === null ? "" : ` ${trimOut.toFixed(1)}s`}]
              </button>
              <button
                className="chip active"
                disabled={trimBusy || trimIn === null || trimOut === null}
                onClick={cutSegment}
                title="Crea un recurso nuevo con ese fragmento"
              >
                {trimBusy ? "Cortando…" : "✂ Cortar In→Out"}
              </button>
              {cur.kind === "video" && (
                <button className="chip" onClick={useThisFrame} title="Usar este frame como poster">
                  🖼 Este frame
                </button>
              )}
              {cur.kind === "audio" && (
                <button
                  className="chip"
                  disabled={splitting}
                  onClick={doSplit}
                  title="Detecta los silencios y crea un recurso por cada trozo de sonido"
                >
                  {splitting ? "Separando…" : "✂ Separar por silencios"}
                </button>
              )}
            </div>
          )}

          <div className="detail-notes">
            <p className="snav-label">NOTAS</p>
            <textarea
              className="grow"
              placeholder="Notas sobre este recurso (qué contiene, cómo usarlo, ideas...)"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
            />
            <div className="row">
              <button className="primary" disabled={notesBusy || notes === (cur.description ?? "")} onClick={saveNotes}>
                {notesBusy ? "Guardando…" : "Guardar notas"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

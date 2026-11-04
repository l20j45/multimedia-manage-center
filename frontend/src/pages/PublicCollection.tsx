import { useEffect, useState } from "react";
import { fetchPublicCollection, publicMediaUrl, type MediaItem, type PublicCollection } from "../lib/api";

/** Vista PÚBLICA de una colección compartida (sin login): /share/<token> */
export default function PublicCollectionPage({ token }: { token: string }) {
  const [data, setData] = useState<PublicCollection | null>(null);
  const [error, setError] = useState("");
  const [preview, setPreview] = useState<MediaItem | null>(null);

  useEffect(() => {
    fetchPublicCollection(token)
      .then(setData)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : "Enlace no válido"));
  }, [token]);

  return (
    <div className="public-page">
      <header className="topbar">
        <h1>{data ? data.name : "Cargando…"}</h1>
      </header>
      {error && <p className="error">{error}</p>}
      {data && (
        <>
          {data.is_project && <p className="sub">🎬 Proyecto de edición · lista de material</p>}
          <p className="sub">
            {data.items.length} recurso(s) compartidos · solo lectura · enlace del propietario
          </p>
          <div className="media-grid">
            {data.items.map((item) => (
              <article className="media-card" key={item.id}>
                <button className="media-visual" onClick={() => setPreview(item)} aria-label={`Ver ${item.title}`}>
                  {item.has_thumb ? (
                    <img src={publicMediaUrl(item.id, token, "thumb")} alt={item.title} />
                  ) : (
                    <span className="media-icon" role="img">
                      {item.kind === "audio" ? "🎵" : item.kind === "video" ? "🎬" : "🖼"}
                    </span>
                  )}
                </button>
                <div className="media-info">
                  <strong className="media-title">{item.title}</strong>
                  <div className="media-tags">
                    {item.tags.map((t) => (
                      <span key={t} className="mini-chip">{t}</span>
                    ))}
                  </div>
                  <span className="media-meta">{(item.size / (1024 * 1024)).toFixed(1)} MB</span>
                </div>
                <div className="media-actions">
                  <a
                    className="ghost action-link"
                    href={publicMediaUrl(item.id, token, "file")}
                    download={item.filename}
                    aria-label={`Descargar ${item.title}`}
                    title="Descargar"
                  >
                    ⬇
                  </a>
                </div>
              </article>
            ))}
          </div>
          {data.items.length === 0 && <div className="empty"><p>La colección compartida está vacía.</p></div>}
        </>
      )}

      {preview && (
        <div className="overlay" onClick={() => setPreview(null)}>
          <div className="modal player" onClick={(e) => e.stopPropagation()}>
            {preview.kind === "video" && <video controls autoPlay src={publicMediaUrl(preview.id, token, "file")} />}
            {preview.kind === "audio" && <audio controls autoPlay src={publicMediaUrl(preview.id, token, "file")} />}
            {preview.kind === "image" && <img src={publicMediaUrl(preview.id, token, "file")} alt={preview.title} />}
            <div className="player-caption">
              <p className="sub">{preview.title}</p>
              {preview.description && <p className="sub muted">{preview.description}</p>}
            </div>
          </div>
        </div>
      )}

      <footer className="sub center-foot">Compartido con la Biblioteca de Recursos Multimedia</footer>
    </div>
  );
}

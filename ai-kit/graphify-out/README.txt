Paquete pre-extraido por ai-bootstrap. Que hace cada cosa:
- graph.json/GRAPH_REPORT.md: grafo + reporte (se regeneran con rebuild)
- cache/: caché AST + semántica (evita re-extraer con LLM los archivos sin cambios)
- manifest.json: stamps por archivo (base del update incremental)
NO commitear .graphify_python ni _pipeline (dependen de la maquina).
Regenera este kit SOLO tras un rebuild completo del grafo (ai-bootstrap paso "rebuild").

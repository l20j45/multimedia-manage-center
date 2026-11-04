# Graph Report - templatesIA  (2026-11-04)

## Corpus Check
- Corpus is ~20,417 words - fits in a single context window. You may not need a graph.

## Summary
- 655 nodes · 1167 edges · 70 communities (40 shown, 30 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 74 edges (avg confidence: 0.95)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Community 0
- Base de datos y sesión
- Dependencias frontend
- Auth: login y recuperación
- API client React
- Dependencias Python
- Config Tauri
- Íconos de escritorio
- Community 8
- Entry Vite y docs
- Community 10
- Alembic entorno
- Servicio de email
- Docker compose
- Tests de humo
- Tests de rate limit
- Arranque de FastAPI
- Rate limit y stdlib
- Config Settings
- Middleware HTTP
- Capabilities Tauri
- Triggers de CI
- Health check
- Workspace pnpm
- Íconos iOS pequeños
- Render del template
- Build Docker script
- Build Rust Tauri
- Íconos iOS 20pt
- Íconos iOS 29pt
- Íconos iOS 40pt
- Íconos iOS grandes
- Íconos iOS iPad
- Lib Rust Tauri
- Main Rust Tauri
- Run para Unix
- Firma Android
- Íconos iOS
- Íconos iOS
- Íconos iOS
- Íconos iOS
- Íconos iOS
- Íconos iOS
- Tipos Vite
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68

## God Nodes (most connected - your core abstractions)
1. `HomePage()` - 42 edges
2. `User` - 40 edges
3. `request()` - 23 edges
4. `MediaItem` - 18 edges
5. `CollectionItem` - 15 edges
6. `upload()` - 15 edges
7. `App icon asset (1024px purple-gradient T logo PNG)` - 15 edges
8. `compilerOptions` - 14 edges
9. `with` - 12 edges
10. `_owned_item()` - 12 edges

## Surprising Connections (you probably didn't know these)
- `get_current_user()` --uses--> `User`  [INFERRED]
  backend/app/deps.py → backend/app/models.py
- `get_current_user_flexible()` --uses--> `User`  [INFERRED]
  backend/app/deps.py → backend/app/models.py
- `forgot_password()` --uses--> `User`  [INFERRED]
  backend/app/routers/auth.py → backend/app/models.py
- `login()` --uses--> `User`  [INFERRED]
  backend/app/routers/auth.py → backend/app/models.py
- `me()` --uses--> `User`  [INFERRED]
  backend/app/routers/auth.py → backend/app/models.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Tauri App Icon Family (all size renditions of purple-gradient T logo)** — frontend_src_tauri_app_icon, frontend_src_tauri_icons_icon, frontend_src_tauri_icons_128x128, frontend_src_tauri_icons_128x128_2x, frontend_src_tauri_icons_32x32, frontend_src_tauri_icons_64x64, frontend_src_tauri_icons_square30x30logo, frontend_src_tauri_icons_square44x44logo, frontend_src_tauri_icons_square71x71logo, frontend_src_tauri_icons_square89x89logo, frontend_src_tauri_icons_square107x107logo, frontend_src_tauri_icons_square142x142logo, frontend_src_tauri_icons_square150x150logo, frontend_src_tauri_icons_square284x284logo, frontend_src_tauri_icons_square310x310logo, frontend_src_tauri_icons_storelogo [INFERRED 0.75]
- **Android launcher icon density family** — frontend_src_tauri_icons_android_mipmap_hdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_hdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_hdpi_ic_launcher_round, frontend_src_tauri_icons_android_mipmap_mdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_mdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_mdpi_ic_launcher_round, frontend_src_tauri_icons_android_mipmap_xhdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_xhdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_xhdpi_ic_launcher_round, frontend_src_tauri_icons_android_mipmap_xxhdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_xxhdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_xxhdpi_ic_launcher_round, frontend_src_tauri_icons_android_mipmap_xxxhdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_xxxhdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_xxxhdpi_ic_launcher_round [EXTRACTED 0.75]
- **iOS small AppIcon family** — frontend_src_tauri_icons_ios_appicon_20x20_1x, frontend_src_tauri_icons_ios_appicon_20x20_2x_1, frontend_src_tauri_icons_ios_appicon_20x20_2x, frontend_src_tauri_icons_ios_appicon_20x20_3x, frontend_src_tauri_icons_ios_appicon_29x29_1x, frontend_src_tauri_icons_ios_appicon_29x29_2x_1, frontend_src_tauri_icons_ios_appicon_29x29_2x, frontend_src_tauri_icons_ios_appicon_29x29_3x, frontend_src_tauri_icons_ios_appicon_40x40_1x, frontend_src_tauri_icons_ios_appicon_40x40_2x_1, frontend_src_tauri_icons_ios_appicon_40x40_2x, frontend_src_tauri_icons_ios_appicon_40x40_3x [EXTRACTED 0.75]
- **iOS large AppIcon family** — frontend_src_tauri_icons_ios_appicon_512_2x, frontend_src_tauri_icons_ios_appicon_60x60_2x, frontend_src_tauri_icons_ios_appicon_60x60_3x, frontend_src_tauri_icons_ios_appicon_76x76_1x, frontend_src_tauri_icons_ios_appicon_76x76_2x, frontend_src_tauri_icons_ios_appicon_83_5x83_5_2x [EXTRACTED 0.75]

## Communities (70 total, 30 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (65): App(), addCollectionItem(), bulkMedia(), clearToken(), Collection, collectionItems(), createCollection(), deleteCollection() (+57 more)

### Community 1 - "Base de datos y sesión"
Cohesion: 0.05
Nodes (26): Settings, run_migrations(), health(), auth(), make_png(), register_and_login(), test_ciclo_completo_de_coleccion(), test_privacidad_de_colecciones() (+18 more)

### Community 2 - "Dependencias frontend"
Cohesion: 0.06
Nodes (45): dependencies, react@^18.3.1, react-dom@^18.3.1, @tauri-apps/api@^2.0.0, devDependencies, jsdom@^25.0.1, @tauri-apps/cli@^2.0.0, @testing-library/react@^16.1.0 (+37 more)

### Community 3 - "Auth: login y recuperación"
Cohesion: 0.11
Nodes (17): MediaItem, bulk(), duplicates(), list_tags(), update_item(), BulkRequest, BulkResult, CollectionAddItem (+9 more)

### Community 4 - "API client React"
Cohesion: 0.08
Nodes (5): RateLimitMiddleware, reset_rate_limits(), _fresh_rate_limit_buckets(), test_endpoint_libre_sin_limite(), test_login_rate_limit()

### Community 5 - "Dependencias Python"
Cohesion: 0.15
Nodes (9): upload(), delete_files(), detect_kind(), ffmpeg_bin(), make_thumbnail(), media_root(), probe_duration(), rethumbnail_at() (+1 more)

### Community 6 - "Config Tauri"
Cohesion: 0.22
Nodes (9): CollectionItem, User, add_item(), collection_items(), delete_collection(), export_collection(), list_collections(), _owned_collection() (+1 more)

### Community 7 - "Íconos de escritorio"
Cohesion: 0.15
Nodes (5): get_db(), get_current_user(), get_current_user_flexible(), get_me(), decode_access_token()

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (18): app, security, windows, build, beforeBuildCommand, beforeDevCommand, devUrl, frontendDist (+10 more)

### Community 9 - "Entry Vite y docs"
Cohesion: 0.17
Nodes (5): upgrade(), upgrade(), upgrade(), upgrade(), upgrade()

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (16): App icon asset (1024px purple-gradient T logo PNG), Tauri 128x128 icon (purple-gradient T logo), Tauri 256px icon (128x128@2x purple-gradient T logo), Tauri 32x32 icon (purple-gradient T logo), Tauri 64x64 icon (purple-gradient T logo), App icon 512px (icons/icon.png), Windows Square107x107Logo (107px purple-gradient T), Windows Square142x142Logo (142px purple-gradient T) (+8 more)

### Community 11 - "Alembic entorno"
Cohesion: 0.12
Nodes (15): compilerOptions, esModuleInterop, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+7 more)

### Community 12 - "Servicio de email"
Cohesion: 0.16
Nodes (7): Base, Collection, create_collection(), update_collection(), CollectionCreate, CollectionOut, CollectionUpdate

### Community 13 - "Docker compose"
Cohesion: 0.15
Nodes (6): count_all(), get_file(), get_thumb(), _item_for_read(), list_media(), MediaList

### Community 14 - "Tests de humo"
Cohesion: 0.22
Nodes (6): delete_item(), _owned_item(), purge_item(), restore_item(), rethumb(), RethumbIn

### Community 15 - "Tests de rate limit"
Cohesion: 0.14
Nodes (13): build, env_file, environment, image, ports, restart, volumes, DATABASE_URL (+5 more)

### Community 16 - "Arranque de FastAPI"
Cohesion: 0.21
Nodes (7): forgot_password(), register(), reset_password(), ForgotPasswordIn, Message, ResetPasswordIn, hash_password()

### Community 17 - "Rate limit y stdlib"
Cohesion: 0.23
Nodes (4): send_email(), send_password_reset_email(), send_welcome_email(), smtp_configured()

### Community 18 - "Config Settings"
Cohesion: 0.23
Nodes (3): create_access_token(), create_reset_code(), hash_code()

### Community 20 - "Capabilities Tauri"
Cohesion: 0.20
Nodes (5): login(), update_me(), Token, UserUpdate, verify_password()

### Community 21 - "Triggers de CI"
Cohesion: 0.20
Nodes (10): with, cache, cache-dependency-path, name, node-version, path, python-version, retention-days (+2 more)

### Community 22 - "Health check"
Cohesion: 0.22
Nodes (8): name, runs-on, concurrency, cancel-in-progress, group, jobs, backend, name

### Community 23 - "Workspace pnpm"
Cohesion: 0.39
Nodes (9): steps, steps, steps, continue-on-error, if, name, run, uses (+1 more)

### Community 24 - "Íconos iOS pequeños"
Cohesion: 0.22
Nodes (9): tauri, os, fail-fast, matrix, if, name, needs, runs-on (+1 more)

### Community 25 - "Render del template"
Cohesion: 0.25
Nodes (8): defaults, run, defaults, name, runs-on, frontend, working-directory, defaults

### Community 26 - "Build Docker script"
Cohesion: 0.25
Nodes (7): command, cwd, type, mcp, servers, $schema, graphify

### Community 28 - "Íconos iOS 20pt"
Cohesion: 0.33
Nodes (5): description, identifier, permissions, $schema, windows

### Community 29 - "Íconos iOS 29pt"
Cohesion: 0.53
Nodes (6): iOS App Store icon 1024px marketing, iOS home screen icon 120px (iPhone 60pt@2x), iOS home screen icon 180px (iPhone 60pt@3x), iOS home screen icon 76px (iPad 76pt@1x), iOS home screen icon 152px (iPad 76pt@2x), iOS home screen icon 167px (iPad Pro 83.5pt@2x)

### Community 30 - "Íconos iOS 40pt"
Cohesion: 0.33
Nodes (6): on, pull_request, push, workflow_dispatch, branches, tags

### Community 31 - "Íconos iOS grandes"
Cohesion: 0.40
Nodes (5): if, name, needs, runs-on, docker

### Community 32 - "Íconos iOS iPad"
Cohesion: 0.50
Nodes (3): allowBuilds, esbuild, packages

### Community 33 - "Lib Rust Tauri"
Cohesion: 0.50
Nodes (4): iOS AppIcon 20pt @1x, iOS AppIcon 20pt @2x, iOS AppIcon 20pt @2x-1, iOS AppIcon 20pt @3x

### Community 34 - "Main Rust Tauri"
Cohesion: 0.50
Nodes (4): iOS AppIcon 29pt @1x, iOS AppIcon 29pt @2x, iOS AppIcon 29pt @2x-1, iOS AppIcon 29pt @3x

### Community 35 - "Run para Unix"
Cohesion: 0.50
Nodes (4): iOS AppIcon 40pt @1x, iOS AppIcon 40pt @2x, iOS AppIcon 40pt @2x-1, iOS AppIcon 40pt @3x

### Community 36 - "Firma Android"
Cohesion: 0.83
Nodes (3): sedi(), render.sh script, verify_cmd()

### Community 38 - "Íconos iOS"
Cohesion: 0.67
Nodes (3): Android launcher icon hdpi regular, Android launcher icon hdpi foreground, Android launcher icon hdpi round

### Community 39 - "Íconos iOS"
Cohesion: 0.67
Nodes (3): Android launcher icon mdpi regular, Android launcher icon mdpi foreground, Android launcher icon mdpi round

### Community 40 - "Íconos iOS"
Cohesion: 0.67
Nodes (3): Android launcher icon xhdpi regular, Android launcher icon xhdpi foreground, Android launcher icon xhdpi round

### Community 41 - "Íconos iOS"
Cohesion: 0.67
Nodes (3): Android launcher icon xxhdpi regular, Android launcher icon xxhdpi foreground, Android launcher icon xxhdpi round

### Community 42 - "Íconos iOS"
Cohesion: 0.67
Nodes (3): Android launcher icon xxxhdpi regular, Android launcher icon xxxhdpi foreground, Android launcher icon xxxhdpi round

## Knowledge Gaps
- **50 isolated node(s):** `biblioteca-recursos-multimedia-backend`, `biblioteca-recursos-multimedia`, `Graphify knowledge graph + MCP infra (graphify-out, ai-kit)`, `Biblioteca de Recursos Multimedia (AGENTS.md overview)`, `docker-compose API deployment` (+45 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 305 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `User` connect `Config Tauri` to `Auth: login y recuperación`, `Íconos iOS`, `Dependencias Python`, `Íconos de escritorio`, `Servicio de email`, `Docker compose`, `Tests de humo`, `Arranque de FastAPI`, `Middleware HTTP`, `Capabilities Tauri`?**
  _High betweenness centrality (0.037) - this node is a cross-community bridge._
- **Are the 33 inferred relationships involving `User` (e.g. with `get_current_user()` and `get_current_user_flexible()`) actually correct?**
  _`User` has 33 INFERRED edges - model-reasoned connections that need verification._
- **What connects `biblioteca-recursos-multimedia-backend`, `biblioteca-recursos-multimedia`, `Graphify knowledge graph + MCP infra (graphify-out, ai-kit)` to the rest of the system?**
  _50 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.07293594964827842 - nodes in this community are weakly interconnected._
- **Why does `upload()` connect `Dependencias Python` to `Auth: login y recuperación`, `Tests de humo`, `Config Tauri`, `Íconos de escritorio`?**
  _High betweenness centrality (0.012) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `MediaItem` (e.g. with `collection_items()` and `export_collection()`) actually correct?**
  _`MediaItem` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Should `Base de datos y sesión` be split into smaller, more focused modules?**
  _Cohesion score 0.05456095481670929 - nodes in this community are weakly interconnected._
# Graph Report - templatesIA  (2026-11-04)

## Corpus Check
- Corpus is ~9,006 words - fits in a single context window. You may not need a graph.

## Summary
- 461 nodes · 630 edges · 48 communities (31 shown, 17 thin omitted)
- Extraction: 94% EXTRACTED · 6% INFERRED · 0% AMBIGUOUS · INFERRED: 35 edges (avg confidence: 0.93)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- CI GitHub Actions
- Base de datos y sesión
- Dependencias frontend
- Auth: login y recuperación
- API client React
- Dependencias Python
- Config Tauri
- Íconos de escritorio
- Íconos Android
- Entry Vite y docs
- Config TypeScript
- Alembic entorno
- Servicio de email
- Docker compose
- Tests de humo
- Tests de rate limit
- Arranque de FastAPI
- Rate limit y stdlib
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
- Tipos Vite
- Paquete backend
- Run para Windows

## God Nodes (most connected - your core abstractions)
1. `App icon asset (1024px purple-gradient T logo PNG)` - 15 edges
2. `compilerOptions` - 14 edges
3. `User` - 13 edges
4. `FastAPI + SQLite backend (Python 3.14+, uv)` - 13 edges
5. `with` - 12 edges
6. `reset_password()` - 10 edges
7. `LoginPage()` - 10 edges
8. `backend/requirements.txt (pip fallback)` - 10 edges
9. `login()` - 9 edges
10. `forgot_password()` - 9 edges

## Surprising Connections (you probably didn't know these)
- `Rule: uv (pyproject.toml) is dependency source of truth` --rationale_for--> `backend/requirements.txt (pip fallback)`  [EXTRACTED]
  AGENTS.md → backend/requirements.txt
- `fastapi==0.162.0` --conceptually_related_to--> `FastAPI + SQLite backend (Python 3.14+, uv)`  [INFERRED]
  backend/requirements.txt → README.md
- `sqlalchemy==2.1.6` --conceptually_related_to--> `FastAPI + SQLite backend (Python 3.14+, uv)`  [INFERRED]
  backend/requirements.txt → README.md
- `uvicorn[standard]==0.54.0` --conceptually_related_to--> `FastAPI + SQLite backend (Python 3.14+, uv)`  [INFERRED]
  backend/requirements.txt → README.md
- `frontend/index.html (Vite entry document)` --conceptually_related_to--> `Frontend stack (Tauri 2 + React + Vite, desktop + Android APK)`  [INFERRED]
  frontend/index.html → AGENTS.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Configuration coherence: root .env, CORS_ORIGINS, VITE_API_URL, Docker deploy** — readme_root_env, readme_cors_origins, readme_vite_api_url, agents_docker_deploy, agents_cors_rule [INFERRED 0.75]
- **FastAPI backend stack: API server + ASGI + ORM + migrations** — readme_fastapi_sqlite_backend, backend_requirements_fastapi, backend_requirements_uvicorn, backend_requirements_sqlalchemy, backend_requirements_alembic [INFERRED 0.85]
- **Registration/login/recovery flow: JWT+bcrypt auth, 6-digit recovery, SMTP email, rate limiting** — readme_jwt_bcrypt_auth, readme_password_recovery_code, readme_smtp_email_service, readme_rate_limiting, readme_endpoints [EXTRACTED 0.95]
- **Tauri App Icon Family (all size renditions of purple-gradient T logo)** — frontend_src_tauri_app_icon, frontend_src_tauri_icons_icon, frontend_src_tauri_icons_128x128, frontend_src_tauri_icons_128x128_2x, frontend_src_tauri_icons_32x32, frontend_src_tauri_icons_64x64, frontend_src_tauri_icons_square30x30logo, frontend_src_tauri_icons_square44x44logo, frontend_src_tauri_icons_square71x71logo, frontend_src_tauri_icons_square89x89logo, frontend_src_tauri_icons_square107x107logo, frontend_src_tauri_icons_square142x142logo, frontend_src_tauri_icons_square150x150logo, frontend_src_tauri_icons_square284x284logo, frontend_src_tauri_icons_square310x310logo, frontend_src_tauri_icons_storelogo [INFERRED 0.75]
- **Android launcher icon density family** — frontend_src_tauri_icons_android_mipmap_hdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_hdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_hdpi_ic_launcher_round, frontend_src_tauri_icons_android_mipmap_mdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_mdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_mdpi_ic_launcher_round, frontend_src_tauri_icons_android_mipmap_xhdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_xhdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_xhdpi_ic_launcher_round, frontend_src_tauri_icons_android_mipmap_xxhdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_xxhdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_xxhdpi_ic_launcher_round, frontend_src_tauri_icons_android_mipmap_xxxhdpi_ic_launcher, frontend_src_tauri_icons_android_mipmap_xxxhdpi_ic_launcher_foreground, frontend_src_tauri_icons_android_mipmap_xxxhdpi_ic_launcher_round [EXTRACTED 0.75]
- **iOS small AppIcon family** — frontend_src_tauri_icons_ios_appicon_20x20_1x, frontend_src_tauri_icons_ios_appicon_20x20_2x_1, frontend_src_tauri_icons_ios_appicon_20x20_2x, frontend_src_tauri_icons_ios_appicon_20x20_3x, frontend_src_tauri_icons_ios_appicon_29x29_1x, frontend_src_tauri_icons_ios_appicon_29x29_2x_1, frontend_src_tauri_icons_ios_appicon_29x29_2x, frontend_src_tauri_icons_ios_appicon_29x29_3x, frontend_src_tauri_icons_ios_appicon_40x40_1x, frontend_src_tauri_icons_ios_appicon_40x40_2x_1, frontend_src_tauri_icons_ios_appicon_40x40_2x, frontend_src_tauri_icons_ios_appicon_40x40_3x [EXTRACTED 0.75]
- **iOS large AppIcon family** — frontend_src_tauri_icons_ios_appicon_512_2x, frontend_src_tauri_icons_ios_appicon_60x60_2x, frontend_src_tauri_icons_ios_appicon_60x60_3x, frontend_src_tauri_icons_ios_appicon_76x76_1x, frontend_src_tauri_icons_ios_appicon_76x76_2x, frontend_src_tauri_icons_ios_appicon_83_5x83_5_2x [EXTRACTED 0.75]

## Communities (48 total, 17 thin omitted)

### Community 0 - "CI GitHub Actions"
Cohesion: 0.08
Nodes (12): run_migrations_offline(), run_migrations_online(), upgrade(), upgrade(), Base, get_db(), get_current_user(), PasswordResetToken (+4 more)

### Community 1 - "Base de datos y sesión"
Cohesion: 0.08
Nodes (18): forgot_password(), login(), register(), reset_password(), update_me(), ForgotPasswordIn, Message, ResetPasswordIn (+10 more)

### Community 2 - "Dependencias frontend"
Cohesion: 0.07
Nodes (38): dependencies, react@^18.3.1, react-dom@^18.3.1, @tauri-apps/api@^2.0.0, devDependencies, jsdom@^25.0.1, @tauri-apps/cli@^2.0.0, @testing-library/react@^16.1.0 (+30 more)

### Community 3 - "Auth: login y recuperación"
Cohesion: 0.08
Nodes (32): alembic==1.20.1, passlib[ bcrypt]==1.7.4 + bcrypt==4.0.1, email-validator==2.3.0, fastapi==0.162.0, pydantic-settings==2.16.2, PyJWT==2.15.1, python-multipart==0.0.33, sqlalchemy==2.1.6 (+24 more)

### Community 4 - "API client React"
Cohesion: 0.21
Nodes (18): App(), clearToken(), forgotPassword(), getMe(), getToken(), login(), register(), request() (+10 more)

### Community 5 - "Dependencias Python"
Cohesion: 0.13
Nodes (19): Rule: model change → Alembic migration in same commit, Commit convention: imperative, split backend/frontend, Rule: CORS_ORIGINS coherent with VITE_API_URL, Docker deploy (templatesia-api image, ${API_PORT}), Backend stack (FastAPI, SQLite, uv, Alembic, JWT+bcrypt, rate limiting), Graphify knowledge graph + MCP server (graphify-out/), Agent instructions for TemplatesIA repo, Rule: don't change rate-limit thresholds (login 10/min, register/forgot 5/min) (+11 more)

### Community 6 - "Config Tauri"
Cohesion: 0.11
Nodes (18): app, security, windows, build, beforeBuildCommand, beforeDevCommand, devUrl, frontendDist (+10 more)

### Community 7 - "Íconos de escritorio"
Cohesion: 0.12
Nodes (16): App icon asset (1024px purple-gradient T logo PNG), Tauri 128x128 icon (purple-gradient T logo), Tauri 256px icon (128x128@2x purple-gradient T logo), Tauri 32x32 icon (purple-gradient T logo), Tauri 64x64 icon (purple-gradient T logo), App icon 512px (icons/icon.png), Windows Square107x107Logo (107px purple-gradient T), Windows Square142x142Logo (142px purple-gradient T) (+8 more)

### Community 8 - "Íconos Android"
Cohesion: 0.12
Nodes (15): compilerOptions, esModuleInterop, isolatedModules, jsx, lib, module, moduleResolution, noEmit (+7 more)

### Community 9 - "Entry Vite y docs"
Cohesion: 0.23
Nodes (4): send_email(), send_password_reset_email(), send_welcome_email(), smtp_configured()

### Community 10 - "Config TypeScript"
Cohesion: 0.15
Nodes (12): build, env_file, environment, image, ports, restart, volumes, DATABASE_URL (+4 more)

### Community 12 - "Servicio de email"
Cohesion: 0.20
Nodes (10): with, cache, cache-dependency-path, name, node-version, path, python-version, retention-days (+2 more)

### Community 13 - "Docker compose"
Cohesion: 0.25
Nodes (3): reset_rate_limits(), test_endpoint_libre_sin_limite(), test_login_rate_limit()

### Community 14 - "Tests de humo"
Cohesion: 0.22
Nodes (8): name, runs-on, concurrency, cancel-in-progress, group, jobs, backend, name

### Community 15 - "Tests de rate limit"
Cohesion: 0.39
Nodes (9): steps, steps, steps, continue-on-error, if, name, run, uses (+1 more)

### Community 16 - "Arranque de FastAPI"
Cohesion: 0.22
Nodes (9): tauri, os, fail-fast, matrix, if, name, needs, runs-on (+1 more)

### Community 19 - "Middleware HTTP"
Cohesion: 0.25
Nodes (8): defaults, run, defaults, name, runs-on, frontend, working-directory, defaults

### Community 20 - "Capabilities Tauri"
Cohesion: 0.25
Nodes (7): command, cwd, type, mcp, servers, $schema, graphify

### Community 23 - "Workspace pnpm"
Cohesion: 0.33
Nodes (5): description, identifier, permissions, $schema, windows

### Community 24 - "Íconos iOS pequeños"
Cohesion: 0.53
Nodes (6): iOS App Store icon 1024px marketing, iOS home screen icon 120px (iPhone 60pt@2x), iOS home screen icon 180px (iPhone 60pt@3x), iOS home screen icon 76px (iPad 76pt@1x), iOS home screen icon 152px (iPad 76pt@2x), iOS home screen icon 167px (iPad Pro 83.5pt@2x)

### Community 25 - "Render del template"
Cohesion: 0.33
Nodes (6): on, pull_request, push, workflow_dispatch, branches, tags

### Community 26 - "Build Docker script"
Cohesion: 0.40
Nodes (5): if, name, needs, runs-on, docker

### Community 28 - "Íconos iOS 20pt"
Cohesion: 0.50
Nodes (3): allowBuilds, esbuild, packages

### Community 29 - "Íconos iOS 29pt"
Cohesion: 0.50
Nodes (4): iOS AppIcon 20pt @1x, iOS AppIcon 20pt @2x, iOS AppIcon 20pt @2x-1, iOS AppIcon 20pt @3x

### Community 30 - "Íconos iOS 40pt"
Cohesion: 0.50
Nodes (4): iOS AppIcon 29pt @1x, iOS AppIcon 29pt @2x, iOS AppIcon 29pt @2x-1, iOS AppIcon 29pt @3x

### Community 31 - "Íconos iOS grandes"
Cohesion: 0.50
Nodes (4): iOS AppIcon 40pt @1x, iOS AppIcon 40pt @2x, iOS AppIcon 40pt @2x-1, iOS AppIcon 40pt @3x

### Community 32 - "Íconos iOS iPad"
Cohesion: 0.67
Nodes (3): Android launcher icon hdpi regular, Android launcher icon hdpi foreground, Android launcher icon hdpi round

### Community 33 - "Lib Rust Tauri"
Cohesion: 0.67
Nodes (3): Android launcher icon mdpi regular, Android launcher icon mdpi foreground, Android launcher icon mdpi round

### Community 34 - "Main Rust Tauri"
Cohesion: 0.67
Nodes (3): Android launcher icon xhdpi regular, Android launcher icon xhdpi foreground, Android launcher icon xhdpi round

### Community 35 - "Run para Unix"
Cohesion: 0.67
Nodes (3): Android launcher icon xxhdpi regular, Android launcher icon xxhdpi foreground, Android launcher icon xxhdpi round

### Community 36 - "Firma Android"
Cohesion: 0.67
Nodes (3): Android launcher icon xxxhdpi regular, Android launcher icon xxxhdpi foreground, Android launcher icon xxxhdpi round

## Knowledge Gaps
- **53 isolated node(s):** `templatesia-backend`, `templatesia`, `Docker deploy (templatesia-api image, ${API_PORT})`, `Graphify knowledge graph + MCP server (graphify-out/)`, `Rule: model change → Alembic migration in same commit` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 233 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **17 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RateLimitMiddleware` connect `Health check` to `Rate limit y stdlib`, `Config Settings`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `App icon asset (1024px purple-gradient T logo PNG)` (e.g. with `Tauri 128x128 icon (purple-gradient T logo)` and `Tauri 64x64 icon (purple-gradient T logo)`) actually correct?**
  _`App icon asset (1024px purple-gradient T logo PNG)` has 11 INFERRED edges - model-reasoned connections that need verification._
- **What connects `templatesia-backend`, `templatesia`, `Docker deploy (templatesia-api image, ${API_PORT})` to the rest of the system?**
  _53 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `CI GitHub Actions` be split into smaller, more focused modules?**
  _Cohesion score 0.07585568917668825 - nodes in this community are weakly interconnected._
- **Why does `react` connect `API client React` to `Dependencias frontend`?**
  _High betweenness centrality (0.007) - this node is a cross-community bridge._
- **Are the 8 inferred relationships involving `User` (e.g. with `get_current_user()` and `forgot_password()`) actually correct?**
  _`User` has 8 INFERRED edges - model-reasoned connections that need verification._
- **Should `Base de datos y sesión` be split into smaller, more focused modules?**
  _Cohesion score 0.07781649245063879 - nodes in this community are weakly interconnected._
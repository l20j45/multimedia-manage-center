#!/usr/bin/env bash
# setup-android-signing.sh — aplica la configuración de firma de la APK release.
#
# El proyecto Android (`src-tauri/gen/android`) se regenera con
# `pnpm tauri android init` y vive fuera de git; este script (rastreado en git)
# parchear `app/build.gradle.kts` de forma idempotente para que la APK de
# release se firme leyendo las variables del .env raíz:
#   TAURI_ANDROID_KEYSTORE_PATH / _PASSWORD / TAURI_ANDROID_KEY_ALIAS / _KEY_PASSWORD
#
# Flujo recomendado después de `tauri android init`:
#   bash scripts/setup-android-signing.sh
#   pnpm tauri android build --apk
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
gradle_file="$root/frontend/src-tauri/gen/android/app/build.gradle.kts"

if [ ! -f "$gradle_file" ]; then
  echo "No existe $gradle_file."
  echo "Primero corre:  cd frontend && pnpm tauri android init"
  exit 1
fi

python3 - "$gradle_file" <<'PYEOF'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

if "TAURI_ANDROID_KEYSTORE_PATH" in text:
    print("La firma de release ya está configurada. Nada que hacer.")
    sys.exit(0)

# 1) variable al inicio del bloque android
text = text.replace(
    "android {",
    'val keystorePath = System.getenv("TAURI_ANDROID_KEYSTORE_PATH")\n\nandroid {',
    1,
)

# 2) signingConfigs antes de buildTypes
signing = (
    '    // Firma de release leyendo las variables del .env raíz del proyecto\n'
    '    signingConfigs {\n'
    '        if (keystorePath != null) {\n'
    '            create("release") {\n'
    '                storeFile = file(keystorePath)\n'
    '                storePassword = System.getenv("TAURI_ANDROID_KEYSTORE_PASSWORD")\n'
    '                keyAlias = System.getenv("TAURI_ANDROID_KEY_ALIAS")\n'
    '                keyPassword = System.getenv("TAURI_ANDROID_KEY_PASSWORD")\n'
    '            }\n'
    '        }\n'
    '    }\n'
    '    buildTypes {'
)
text = text.replace("    buildTypes {", signing, 1)

# 3) aplicar el signingConfig al build de release
release = (
    '        getByName("release") {\n'
    '            if (keystorePath != null) {\n'
    '                signingConfig = signingConfigs.getByName("release")\n'
    '            }\n'
)
text = text.replace(
    '        getByName("release") {',
    release,
    1,
)

path.write_text(text, encoding="utf-8")
print("Parche de firma aplicado a", path.name)
PYEOF

echo ""
echo "Recuerda: keystore + contraseñas viven en el .env RAÍZ (TAURI_ANDROID_*)."
echo "Compila la APK firmada con:  cd frontend && pnpm tauri android build --apk"

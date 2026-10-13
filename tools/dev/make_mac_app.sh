#!/bin/bash
# Cria ~/Applications/Hesper.app: um atalho de app do macOS que roda o jogo direto do repo (uv run python -m game).
# Não empacota nada: o .app é só um script + ícone, então sempre roda o código atual do repo.
# Uso: bash tools/dev/make_mac_app.sh   (rode de novo se mudar o repo de lugar ou quiser outro ícone)
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../.." && pwd)"
UV="$(command -v uv)"
APP="$HOME/Applications/Hesper.app"
TMP="$(mktemp -d)"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"

cat > "$APP/Contents/MacOS/Hesper" <<EOF
#!/bin/bash
# Atalho do Hesper: roda o jogo do repo (arm64: sem isso o macOS abre script de .app no Rosetta e o numpy do .venv não carrega). Log da última partida em ~/Library/Logs/hesper.log
cd "$REPO"
exec /usr/bin/arch -arm64 "$UV" run python -m game > "\$HOME/Library/Logs/hesper.log" 2>&1
EOF
chmod +x "$APP/Contents/MacOS/Hesper"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Hesper</string>
  <key>CFBundleDisplayName</key><string>Hesper</string>
  <key>CFBundleIdentifier</key><string>dev.gabrieloliveira.hesper</string>
  <key>CFBundleExecutable</key><string>Hesper</string>
  <key>CFBundleIconFile</key><string>Hesper</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleVersion</key><string>1</string>
  <key>LSArchitecturePriority</key><array><string>arm64</string></array>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
EOF

# Ícone: o "H" do logo sobre a nuvem de poeira da tela de título (tools/dev/mac_icon.py, desenhado pelo próprio jogo).
(cd "$REPO" && SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy "$UV" run python tools/dev/mac_icon.py "$TMP/icon_1024.png" >/dev/null)

ICONSET="$TMP/Hesper.iconset"
mkdir -p "$ICONSET"
for size in 16 32 128 256 512; do
  sips -z $size $size "$TMP/icon_1024.png" --out "$ICONSET/icon_${size}x${size}.png" >/dev/null
  sips -z $((size * 2)) $((size * 2)) "$TMP/icon_1024.png" --out "$ICONSET/icon_${size}x${size}@2x.png" >/dev/null
done
iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/Hesper.icns"
rm -rf "$TMP"
touch "$APP"
echo "Pronto: $APP"

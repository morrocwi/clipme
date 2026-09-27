#!/usr/bin/env bash
# clipme bootstrap: create a local venv and make ffmpeg + ffprobe resolvable
# on a no-sudo machine, without touching system PATH or requiring root.
#
# What this does NOT do: modify clipme.py or core/*.py, install a system
# package, or require sudo. It only wires binaries into a repo-local bin/.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

VENV_DIR="$REPO_ROOT/.venv"
BIN_DIR="$REPO_ROOT/bin"
ENV_SCRIPT="$REPO_ROOT/scripts/env.sh"

echo "== clipme bootstrap =="
echo "repo root: $REPO_ROOT"

# 1) venv
if [ ! -d "$VENV_DIR" ]; then
    echo "-- creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
else
    echo "-- venv already exists at $VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# 2) base requirements
echo "-- installing requirements.txt"
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# 3) ffmpeg (imageio-ffmpeg ships a static ffmpeg binary, no ffprobe)
echo "-- installing imageio-ffmpeg (provides ffmpeg only)"
pip install --quiet imageio-ffmpeg

FFMPEG_BIN="$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())' 2>/dev/null || true)"
if [ -n "$FFMPEG_BIN" ] && [ -x "$FFMPEG_BIN" ]; then
    echo "-- ffmpeg resolved via imageio-ffmpeg: $FFMPEG_BIN"
else
    echo "-- imageio-ffmpeg did not yield a usable ffmpeg binary"
    FFMPEG_BIN=""
fi

# ffprobe is NOT bundled by imageio-ffmpeg. Try static-ffmpeg, which bundles
# both ffmpeg and ffprobe static binaries.
echo "-- installing static-ffmpeg (provides ffmpeg + ffprobe)"
pip install --quiet static-ffmpeg

STATIC_DIR="$(python3 - <<'PY'
import time
import static_ffmpeg

ffmpeg_path = ffprobe_path = ""
# The underlying fetch downloads a static binary archive over the network;
# retry once in case of a transient network hiccup before giving up.
for attempt in range(2):
    try:
        ffmpeg_path, ffprobe_path = static_ffmpeg.run.get_or_fetch_platform_executables_else_raise()
        break
    except Exception:  # noqa: BLE001
        if attempt == 0:
            time.sleep(2)
            continue
        ffmpeg_path = ffprobe_path = ""

print(ffmpeg_path)
print(ffprobe_path)
PY
)"
STATIC_FFMPEG="$(echo "$STATIC_DIR" | sed -n '1p')"
STATIC_FFPROBE="$(echo "$STATIC_DIR" | sed -n '2p')"

if [ -n "$STATIC_FFPROBE" ] && [ -x "$STATIC_FFPROBE" ]; then
    echo "-- ffprobe resolved via static-ffmpeg: $STATIC_FFPROBE"
else
    echo "-- static-ffmpeg did not yield a usable ffprobe binary"
    STATIC_FFPROBE=""
fi

# Prefer static-ffmpeg's ffmpeg too if imageio-ffmpeg failed but static did not.
if [ -z "$FFMPEG_BIN" ] && [ -n "$STATIC_FFMPEG" ] && [ -x "$STATIC_FFMPEG" ]; then
    FFMPEG_BIN="$STATIC_FFMPEG"
    echo "-- ffmpeg resolved via static-ffmpeg fallback: $FFMPEG_BIN"
fi

# 4) symlink (or copy) both binaries into repo-local bin/ under fixed names
mkdir -p "$BIN_DIR"

link_or_copy() {
    local src="$1" dest="$2"
    if [ -z "$src" ]; then
        return 1
    fi
    rm -f "$dest"
    if ln -sf "$src" "$dest" 2>/dev/null; then
        return 0
    fi
    cp "$src" "$dest"
    chmod +x "$dest"
}

if link_or_copy "$FFMPEG_BIN" "$BIN_DIR/ffmpeg"; then
    echo "-- wired $BIN_DIR/ffmpeg -> $FFMPEG_BIN"
else
    echo "-- could not wire ffmpeg into $BIN_DIR"
fi

if link_or_copy "$STATIC_FFPROBE" "$BIN_DIR/ffprobe"; then
    echo "-- wired $BIN_DIR/ffprobe -> $STATIC_FFPROBE"
else
    echo "-- could not wire ffprobe into $BIN_DIR"
fi

# 5) PATH export line, printed and written to scripts/env.sh
PATH_LINE="export PATH=\"$BIN_DIR:\$PATH\""
echo ""
echo "== add this to your shell profile (or source scripts/env.sh) =="
echo "$PATH_LINE"

cat > "$ENV_SCRIPT" <<EOF
#!/usr/bin/env bash
# source this file to put clipme's bootstrapped ffmpeg/ffprobe on PATH:
#   source scripts/env.sh
$PATH_LINE
EOF
chmod +x "$ENV_SCRIPT"
echo "-- wrote $ENV_SCRIPT"

if [ ! -f "$REPO_ROOT/.envrc" ]; then
    echo "$PATH_LINE" > "$REPO_ROOT/.envrc"
    echo "-- wrote $REPO_ROOT/.envrc"
else
    echo "-- $REPO_ROOT/.envrc already exists, leaving it as-is"
fi

# 6) sanity check: init a scratch project, then verify both binaries on PATH
echo ""
echo "== sanity check =="
export PATH="$BIN_DIR:$PATH"

SCRATCH_DIR="/tmp/clipme-bootstrap-check"
rm -rf "$SCRATCH_DIR"
python3 "$REPO_ROOT/clipme.py" init "$SCRATCH_DIR" --profile short-90s --title Test --duration 10 >/dev/null
echo "-- clipme.py init OK: $SCRATCH_DIR"

FFMPEG_STATUS="FAIL"
FFPROBE_STATUS="FAIL"

if ffmpeg -version >/dev/null 2>&1; then
    FFMPEG_STATUS="PASS"
fi
if ffprobe -version >/dev/null 2>&1; then
    FFPROBE_STATUS="PASS"
fi

echo ""
echo "== bootstrap summary =="
echo "ffmpeg:  $FFMPEG_STATUS"
echo "ffprobe: $FFPROBE_STATUS"

if [ "$FFMPEG_STATUS" = "PASS" ] && [ "$FFPROBE_STATUS" = "PASS" ]; then
    echo "bootstrap OK: source scripts/env.sh (or add the export line above) then re-run clipme.py probe/assemble."
    exit 0
else
    echo "bootstrap INCOMPLETE: one or both binaries are still unavailable. See messages above."
    exit 1
fi

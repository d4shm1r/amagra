#!/usr/bin/env bash
# Convert every .webm in ./out to an optimized, README-ready .gif.
# Two-pass palette (palettegen/paletteuse) — far smaller and cleaner than a
# naive single-pass GIF. Tuned to land each clip comfortably under ~5 MB.
#
# Usage:   ./to-gif.sh [width] [fps] [trim]
#   width  output width in px    (default 960; use 800 for Reddit/README embeds)
#   fps    frames per second     (default 15; drop to 12 for smaller files)
#   trim   seconds to skip from the START of every clip (default 0) — cuts the
#          launcher/navigation lead-in so the GIF opens on the action.
#
# Per-file trim override (shots have different lead-in lengths). Set an env var
# named TRIM_<basename with dashes as underscores>, e.g.:
#   TRIM_shot1_divergence=2  TRIM_shot2_replay=3  ./to-gif.sh
#
# Requires ffmpeg (already standard). For even smaller/higher-quality output,
# install `gifski` and see the note at the bottom.
set -euo pipefail

WIDTH="${1:-960}"
FPS="${2:-15}"
TRIM_DEFAULT="${3:-0}"
OUT_DIR="${OUT_DIR:-./out}"

shopt -s nullglob
webms=("$OUT_DIR"/*.webm)
if [ ${#webms[@]} -eq 0 ]; then
  echo "No .webm files in $OUT_DIR — run 'npm run record' first." >&2
  exit 1
fi

for src in "${webms[@]}"; do
  base="$(basename "${src%.webm}")"
  palette="$OUT_DIR/${base}.palette.png"
  gif="$OUT_DIR/${base}.gif"
  filters="fps=${FPS},scale=${WIDTH}:-1:flags=lanczos"

  # Per-file trim override (TRIM_shot1_divergence=…) falls back to the default.
  trim_var="TRIM_$(echo "$base" | tr '-' '_')"
  trim="${!trim_var:-$TRIM_DEFAULT}"
  ss=()
  note=""
  [ "$trim" != "0" ] && { ss=(-ss "$trim"); note=", trim ${trim}s"; }

  echo "→ $base.gif  (${WIDTH}px @ ${FPS}fps${note})"
  # -ss before -i seeks the input, so it applies only to the video (not the palette).
  ffmpeg -y -loglevel error "${ss[@]}" -i "$src" \
    -vf "${filters},palettegen=stats_mode=diff" "$palette"
  ffmpeg -y -loglevel error "${ss[@]}" -i "$src" -i "$palette" \
    -lavfi "${filters} [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle" \
    "$gif"
  rm -f "$palette"
  size=$(du -h "$gif" | cut -f1)
  echo "   ✔ $gif  ($size)"
done

echo
echo "Done. If any file is too large, re-run with a smaller width/fps, e.g.:"
echo "   ./to-gif.sh 800 12"
echo
echo "Higher quality + smaller (optional): install gifski, then"
echo "   ffmpeg -i out/shot1-divergence.webm -vf scale=960:-1 -r 15 out/frame_%04d.png"
echo "   gifski -o out/shot1-divergence.gif --fps 15 out/frame_*.png && rm out/frame_*.png"

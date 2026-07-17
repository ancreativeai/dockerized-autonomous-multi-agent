#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Hermes model auto-selection by host RAM.
#
# NOTE: this mapping CORRECTS the original spec, which was inverted and
# physically impossible (Q4_K_M is LARGER than Q3_K_M, and a 70B Q4_K_M model
# needs ~42GB+ RAM — it can never run on a 16GB machine):
#
#   < 5.8 GB RAM   -> 8B  Q3_K_M  (~4.0 GB file)  tight but loads
#   < 20  GB RAM   -> 8B  Q4_K_M  (~4.9 GB file)  <- HP EliteBook 830 G6 (16GB)
#   < 48  GB RAM   -> 8B  Q6_K    (~6.6 GB file)  higher quality
#   >= 48 GB RAM   -> 70B Q4_K_M  (~42  GB file)  workstation-class only
#
# Override with HERMES_FORCE_FILE=<filename.gguf> in .env if desired.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

MODEL_DIR="${MODEL_DIR:-/models}"
REPO_8B="https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-8B-GGUF/resolve/main"
REPO_70B="https://huggingface.co/NousResearch/Hermes-3-Llama-3.1-70B-GGUF/resolve/main"

mem_mb=$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo)
threads=$(nproc)

if   [ "$mem_mb" -lt 5800 ]; then
  FILE="Hermes-3-Llama-3.1-8B.Q3_K_M.gguf";  URL="$REPO_8B/$FILE"
elif [ "$mem_mb" -lt 20000 ]; then
  FILE="Hermes-3-Llama-3.1-8B.Q4_K_M.gguf";  URL="$REPO_8B/$FILE"
elif [ "$mem_mb" -lt 48000 ]; then
  FILE="Hermes-3-Llama-3.1-8B.Q6_K.gguf";    URL="$REPO_8B/$FILE"
else
  FILE="Hermes-3-Llama-3.1-70B.Q4_K_M.gguf"; URL="$REPO_70B/$FILE"
fi

if [ -n "${HERMES_FORCE_FILE:-}" ]; then
  FILE="$HERMES_FORCE_FILE"
  URL="$REPO_8B/$FILE"
fi

echo "[hermes] host RAM: ${mem_mb} MB | threads: ${threads} | selected model: ${FILE}"

mkdir -p "$MODEL_DIR"
if [ ! -s "$MODEL_DIR/$FILE" ]; then
  echo "[hermes] model not cached — downloading (resumable): $URL"
  curl -L --fail --retry 8 --retry-delay 5 -C - -o "$MODEL_DIR/$FILE.part" "$URL"
  mv "$MODEL_DIR/$FILE.part" "$MODEL_DIR/$FILE"
  echo "[hermes] download complete."
else
  echo "[hermes] using cached model at $MODEL_DIR/$FILE"
fi

# Leave one thread free for the OS/other containers
run_threads=$(( threads > 1 ? threads - 1 : 1 ))

exec /app/llama-server \
  --model "$MODEL_DIR/$FILE" \
  --alias hermes \
  --host 0.0.0.0 --port 8080 \
  --ctx-size "${HERMES_CTX:-8192}" \
  --threads "$run_threads" \
  --parallel "${HERMES_PARALLEL:-2}" \
  --metrics \
  --jinja

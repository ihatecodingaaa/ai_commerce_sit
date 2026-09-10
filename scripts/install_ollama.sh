#!/bin/bash
# Installs Ollama and pulls the lab's default small model. Intended for a
# fresh Amazon Linux / Ubuntu EC2 instance. CPU-only is fine (no GPU
# required) -- Ollama automatically falls back to CPU inference.
set -euo pipefail

MODEL="${OLLAMA_MODEL:-qwen2.5:3b}"

echo "== Installing Ollama (CPU-only is fine) =="
if ! command -v ollama >/dev/null 2>&1; then
  curl -fsSL https://ollama.com/install.sh | sh
else
  echo "ollama already installed: $(command -v ollama)"
fi

echo "== Starting Ollama service =="
if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files | grep -q ollama.service; then
  sudo systemctl enable --now ollama
else
  echo "systemd ollama.service not found; starting 'ollama serve' in the background"
  nohup ollama serve > /tmp/ollama-serve.log 2>&1 &
  sleep 2
fi

echo "== Pulling model: $MODEL (this can take a few minutes on CPU) =="
ollama pull "$MODEL"

echo "== Done. Verify with: =="
echo "curl -s http://127.0.0.1:11434/api/tags"

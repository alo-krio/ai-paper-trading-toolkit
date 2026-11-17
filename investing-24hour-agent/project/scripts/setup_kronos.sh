#!/bin/sh
# Sandbox loses pip packages between sessions. CPU-only torch (CUDA build fills the disk). ~1-2 min when missing.
python3 -c "import torch,pandas,einops,huggingface_hub,safetensors" 2>/dev/null || {
  pip install -q --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch &&
  pip install -q --no-cache-dir pandas einops huggingface_hub safetensors; }
python3 -c "import torch,pandas; print('kronos deps ok')"

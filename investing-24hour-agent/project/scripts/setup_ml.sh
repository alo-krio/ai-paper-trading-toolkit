#!/bin/sh
# Sandbox loses pip packages between sessions; run before chatter.py (~1-2 min). CPU-only torch (CUDA build fills the disk).
python3 -c "import transformers,torch" 2>/dev/null || { pip install -q --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch && pip install -q --no-cache-dir transformers peft accelerate; }
python3 -c "import gliner2" 2>/dev/null || pip install -q --no-cache-dir --no-deps gliner2

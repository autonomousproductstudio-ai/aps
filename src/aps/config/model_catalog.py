"""Model catalog — the single source of truth for what the UI model-selector offers.

Data only, no secrets. Lists the providers APS supports today (gemini, nim) and a curated set
of NVIDIA NIM **free-endpoint** models (the OpenAI-compatible path: ChatOpenAI + NIM base_url).
The frontend's per-run model dropdown is built from `GET /models`, so adding/removing a model is
a one-line edit here — no frontend change. Tool-calling is the gate that matters for APS; the
`tools` flag marks models known to support function-calling ("verify" = check with the smoke).
"""
from __future__ import annotations

# (id, label, tools) — id is what gets sent as config.model and to ChatOpenAI(model=...).
NIM_MODELS: list[dict] = [
    {"id": "nvidia/nvidia-nemotron-nano-9b-v2", "label": "Nemotron Nano 9B v2 (default, fast/cheap)", "tools": True},
    {"id": "openai/gpt-oss-120b", "label": "GPT-OSS 120B (MoE reasoning)", "tools": True},
    {"id": "openai/gpt-oss-20b", "label": "GPT-OSS 20B (smaller MoE)", "tools": True},
    {"id": "qwen/qwen3.5-122b-a10b", "label": "Qwen3.5 122B-A10B (agent-ready)", "tools": True},
    {"id": "mistralai/mistral-medium-3.5-128b", "label": "Mistral Medium 3.5 128B", "tools": True},
    {"id": "z-ai/glm-5.1", "label": "GLM-5.1 (agentic / long-horizon)", "tools": True},
    {"id": "nvidia/nemotron-3-nano-30b-a3b", "label": "Nemotron-3 Nano 30B-A3B (1M ctx)", "tools": True},
    {"id": "nvidia/nemotron-3-super-120b-a12b", "label": "Nemotron-3 Super 120B-A12B", "tools": True},
    {"id": "meta/llama-3.3-70b-instruct", "label": "Llama 3.3 70B Instruct", "tools": True},
    {"id": "deepseek-ai/deepseek-v4-pro", "label": "DeepSeek V4 Pro (1M ctx)", "tools": "verify"},
    {"id": "moonshotai/kimi-k2.6", "label": "Kimi K2.6 (multimodal MoE)", "tools": "verify"},
]

# Providers the backend can resolve today. (The multi-provider failover chain in
# multipleAPIplan.md is future work; this catalog reflects what ships now.)
PROVIDERS: list[dict] = [
    {"id": "nim", "label": "NVIDIA NIM", "key_env": "NVIDIA_API_KEY", "models": NIM_MODELS},
    {"id": "gemini", "label": "Google Gemini", "key_env": "GEMINI_API_KEY",
     "models": [{"id": "gemini-2.5-flash", "label": "Gemini 2.5 Flash", "tools": True}]},
]


def catalog() -> dict:
    """The full selector catalog (providers → models)."""
    return {"providers": PROVIDERS}

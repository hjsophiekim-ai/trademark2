from __future__ import annotations

import copy
import json
import os
from pathlib import Path


DEFAULT_PHONETIC_CONFIG: dict = {
    "rule_weights": {
        "sub_same": 0.0,
        "sub_strong": 0.14,
        "sub_medium": 0.22,
        "sub_weak": 0.32,
        "sub_far": 0.58,
        "insdel": 0.45,
        "end_vowel": 0.08,
        "silent_e": 0.10,
        "digraph": 0.10,
        "double_vowel": 0.18,
        "coda_weakening": 0.16,
    },
    "query": {
        "max_terms": 12,
        "min_variant_weight": 0.68,
        "min_class_variant_weight": 0.76,
        "korean_pronunciation_weight": 0.78,
        "min_korean_pronunciation_weight": 0.50,
    },
}

_OVERRIDE: dict | None = None


def _deep_update(dst: dict, src: dict) -> dict:
    for key, value in (src or {}).items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _deep_update(dst[key], value)
        else:
            dst[key] = value
    return dst


def set_phonetic_config_override(override: dict | None) -> None:
    global _OVERRIDE
    _OVERRIDE = override


def load_phonetic_config_file(path: str | os.PathLike | None) -> dict:
    if not path:
        return {}
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def get_phonetic_config() -> dict:
    cfg = copy.deepcopy(DEFAULT_PHONETIC_CONFIG)
    file_cfg = load_phonetic_config_file(os.environ.get("TRADEMARK_PHONETIC_CONFIG", ""))
    _deep_update(cfg, file_cfg)
    if _OVERRIDE:
        _deep_update(cfg, _OVERRIDE)

    weights = cfg.get("rule_weights", {}) or {}
    weights.update(
        {
            "P/B": float(weights.get("sub_weak", 0.32)),
            "K/G": float(weights.get("sub_weak", 0.32)),
            "T/D": float(weights.get("sub_weak", 0.32)),
            "P/F": float(weights.get("sub_medium", 0.22)),
            "R/L": float(weights.get("sub_medium", 0.22)),
        }
    )
    cfg["rule_weights"] = weights
    return cfg


def get_rule_weights() -> dict:
    return get_phonetic_config().get("rule_weights", {}) or {}


def get_query_config() -> dict:
    return get_phonetic_config().get("query", {}) or {}


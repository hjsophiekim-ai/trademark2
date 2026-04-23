from __future__ import annotations

import re
from collections import deque
from difflib import SequenceMatcher

try:
    from phonetic_config import get_rule_weights
except ImportError:
    from .phonetic_config import get_rule_weights

CONSONANT_GROUPS_EN = [
    {"P", "B", "F", "V"},
    {"C", "K", "Q", "G"},
    {"T", "D"},
    {"S", "Z", "X"},
    {"J", "G"},
    {"L", "R"},
    {"M", "N"},
    {"H"},
    {"W", "U"},
    {"Y", "I"},
]

VOWEL_GROUPS_EN = [
    {"OO", "U", "OU"},
    {"EE", "I", "IE", "Y"},
    {"A", "AE", "E"},
    {"O", "AU", "AW"},
    {"EI", "AY", "AI"},
    {"OI", "OY"},
    {"U", "OO", "EW", "UE"},
]

DIGRAPH_RULES: dict[str, list[str]] = {
    "PH": ["F"],
    "CK": ["K"],
    "QU": ["K", "KW"],
    "X": ["KS", "Z"],
    "CH": ["CH", "K", "SH"],
    "SH": ["SH"],
    "TH": ["T", "S"],
    "GH": ["G", ""],
    "ING": ["IN", "NG"],
}

HANGUL_PHONETIC_GROUPS = {
    "onset": [
        {"ㅂ", "ㅍ"},
        {"ㄱ", "ㅋ", "ㄲ"},
        {"ㄷ", "ㅌ", "ㄸ"},
        {"ㅈ", "ㅊ"},
        {"ㅅ", "ㅆ"},
        {"ㄹ", "ㄴ"},
        {"ㅎ"},
    ],
    "vowel": [
        {"ㅜ", "ㅠ"},
        {"ㅣ", "ㅟ", "ㅢ"},
        {"ㅓ", "ㅕ"},
        {"ㅗ", "ㅛ"},
        {"ㅐ", "ㅔ"},
        {"ㅘ", "ㅝ"},
    ],
    "coda": [
        {""},
        {"ㄱ", "ㅋ", "ㄲ"},
        {"ㅂ", "ㅍ"},
        {"ㄷ", "ㅅ", "ㅈ", "ㅊ", "ㅌ"},
        {"ㅇ"},
    ],
}

_EN_VOWEL_CHUNKS = [
    "OO",
    "OU",
    "EE",
    "IE",
    "AI",
    "AY",
    "EI",
    "OI",
    "OY",
    "AU",
    "AW",
    "UE",
    "EW",
]

_ROMAN_ONLY = re.compile(r"[^0-9A-Za-z]+")

_COMMON_SUFFIXES_EN = [
    "TECH",
    "TEK",
    "MART",
    "CARE",
    "LINE",
    "SHOP",
    "STORE",
    "LAB",
    "LABS",
]
_COMMON_SUFFIXES_KO = [
    "테크",
    "텍",
    "마트",
    "케어",
    "라인",
    "샵",
    "스토어",
    "랩",
]

_CHOSUNG = [
    "ㄱ",
    "ㄲ",
    "ㄴ",
    "ㄷ",
    "ㄸ",
    "ㄹ",
    "ㅁ",
    "ㅂ",
    "ㅃ",
    "ㅅ",
    "ㅆ",
    "ㅇ",
    "ㅈ",
    "ㅉ",
    "ㅊ",
    "ㅋ",
    "ㅌ",
    "ㅍ",
    "ㅎ",
]
_JUNGSUNG = [
    "ㅏ",
    "ㅐ",
    "ㅑ",
    "ㅒ",
    "ㅓ",
    "ㅔ",
    "ㅕ",
    "ㅖ",
    "ㅗ",
    "ㅘ",
    "ㅙ",
    "ㅚ",
    "ㅛ",
    "ㅜ",
    "ㅝ",
    "ㅞ",
    "ㅟ",
    "ㅠ",
    "ㅡ",
    "ㅢ",
    "ㅣ",
]
_JONGSUNG = [
    "",
    "ㄱ",
    "ㄲ",
    "ㄳ",
    "ㄴ",
    "ㄵ",
    "ㄶ",
    "ㄷ",
    "ㄹ",
    "ㄺ",
    "ㄻ",
    "ㄼ",
    "ㄽ",
    "ㄾ",
    "ㄿ",
    "ㅀ",
    "ㅁ",
    "ㅂ",
    "ㅄ",
    "ㅅ",
    "ㅆ",
    "ㅇ",
    "ㅈ",
    "ㅊ",
    "ㅋ",
    "ㅌ",
    "ㅍ",
    "ㅎ",
]


def _normalize_roman(mark: str) -> str:
    raw = str(mark or "").strip()
    compact = _ROMAN_ONLY.sub("", raw).upper()
    return compact


def _hangul_only(mark: str) -> str:
    return "".join(ch for ch in str(mark or "").strip() if _is_hangul_syllable(ch))


def _longest_common_suffix_len(a: str, b: str) -> int:
    left = str(a or "")
    right = str(b or "")
    i = 0
    while i < min(len(left), len(right)) and left[-1 - i] == right[-1 - i]:
        i += 1
    return i


def _edit_distance_small(a: str, b: str, limit: int = 2) -> int:
    left = str(a or "")
    right = str(b or "")
    if left == right:
        return 0
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    if max(len(left), len(right)) > 6:
        return limit + 1

    dp = list(range(len(right) + 1))
    for i, ca in enumerate(left, start=1):
        prev = dp[0]
        dp[0] = i
        best_row = dp[0]
        for j, cb in enumerate(right, start=1):
            cur = dp[j]
            if ca == cb:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j - 1], cur)
            prev = cur
            best_row = min(best_row, dp[j])
        if best_row > limit:
            return limit + 1
    return dp[-1]


def _roman_cv_pattern(text: str) -> str:
    t = _normalize_roman(text)
    if not t:
        return ""
    out = []
    last = ""
    for ch in t:
        k = "V" if ch in "AEIOUY" else "C"
        if k == last:
            continue
        out.append(k)
        last = k
    return "".join(out)


def _is_hangul_syllable(ch: str) -> bool:
    code = ord(ch)
    return 0xAC00 <= code <= 0xD7A3


def _decompose_hangul(text: str) -> list[tuple[str, str, str]]:
    parts: list[tuple[str, str, str]] = []
    for ch in str(text or "").strip():
        if not _is_hangul_syllable(ch):
            continue
        code = ord(ch) - 0xAC00
        choseong = code // 588
        jungseong = (code % 588) // 28
        jongseong = code % 28
        parts.append((_CHOSUNG[choseong], _JUNGSUNG[jungseong], _JONGSUNG[jongseong]))
    return parts


def _group_cost(value: str, groups: list[set[str]], base_cost: float) -> float:
    weights = get_rule_weights()
    if not value:
        return 0.0
    for group in groups:
        if value in group:
            return base_cost
    return float(weights.get("sub_far", 0.58))


def _hangul_component_cost(left: str, right: str, groups: list[set[str]]) -> float:
    weights = get_rule_weights()
    if left == right:
        return 0.0
    for group in groups:
        if left in group and right in group:
            if group == {"ㄹ", "ㄴ"}:
                return float(weights.get("sub_weak", 0.32))
            if group == {"ㅎ"}:
                return float(weights.get("sub_weak", 0.32))
            if group == {"ㅘ", "ㅝ"}:
                return float(weights.get("sub_weak", 0.32))
            return float(weights.get("sub_medium", 0.22)) if group != {""} else float(weights.get("sub_same", 0.0))
    if left == "" or right == "":
        return float(weights.get("coda_weakening", 0.16))
    return float(weights.get("sub_far", 0.58))


def hangul_pronunciation_similarity(mark_a: str, mark_b: str) -> dict:
    weights = get_rule_weights()
    left = _decompose_hangul(mark_a)
    right = _decompose_hangul(mark_b)
    if not left or not right:
        return {
            "similarity": 0,
            "onset_similarity": 0,
            "vowel_similarity": 0,
            "coda_similarity": 0,
            "best_path": [],
            "path_breakdown": [],
        }

    left_syllables = [ch for ch in str(mark_a or "").strip() if _is_hangul_syllable(ch)]
    right_syllables = [ch for ch in str(mark_b or "").strip() if _is_hangul_syllable(ch)]

    insdel = float(weights.get("insdel", 0.45))
    onset_groups = HANGUL_PHONETIC_GROUPS["onset"]
    vowel_groups = HANGUL_PHONETIC_GROUPS["vowel"]
    coda_groups = HANGUL_PHONETIC_GROUPS["coda"]

    def component_cost(left_value: str, right_value: str, groups: list[set[str]], kind: str) -> tuple[float, str]:
        if left_value == right_value:
            return 0.0, "same"
        for group in groups:
            if left_value in group and right_value in group:
                if kind == "onset" and group == {"ㄹ", "ㄴ"}:
                    return float(weights.get("sub_weak", 0.32)), "weak_group"
                if kind == "onset" and group == {"ㅎ"}:
                    return float(weights.get("sub_weak", 0.32)), "weak_group"
                if kind == "vowel" and group == {"ㅘ", "ㅝ"}:
                    return float(weights.get("sub_weak", 0.32)), "weak_group"
                return float(weights.get("sub_medium", 0.22)), "group"
        if left_value == "" or right_value == "":
            return float(weights.get("coda_weakening", 0.16)), "weakening"
        return float(weights.get("sub_far", 0.58)), "far"

    n = len(left)
    m = len(right)
    dp_total = [[0.0] * (m + 1) for _ in range(n + 1)]
    dp_o = [[0.0] * (m + 1) for _ in range(n + 1)]
    dp_v = [[0.0] * (m + 1) for _ in range(n + 1)]
    dp_c = [[0.0] * (m + 1) for _ in range(n + 1)]
    prev: list[list[tuple[str, int, int, dict] | None]] = [[None] * (m + 1) for _ in range(n + 1)]

    for i in range(1, n + 1):
        dp_total[i][0] = dp_total[i - 1][0] + insdel
        dp_o[i][0] = dp_o[i - 1][0] + insdel
        dp_v[i][0] = dp_v[i - 1][0] + insdel
        dp_c[i][0] = dp_c[i - 1][0] + insdel
        prev[i][0] = ("del", i - 1, 0, {})
    for j in range(1, m + 1):
        dp_total[0][j] = dp_total[0][j - 1] + insdel
        dp_o[0][j] = dp_o[0][j - 1] + insdel
        dp_v[0][j] = dp_v[0][j - 1] + insdel
        dp_c[0][j] = dp_c[0][j - 1] + insdel
        prev[0][j] = ("ins", 0, j - 1, {})

    def better(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
        if a[0] != b[0]:
            return a[0] < b[0]
        if a[1] != b[1]:
            return a[1] < b[1]
        if a[2] != b[2]:
            return a[2] < b[2]
        return a[3] < b[3]

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            lo, lv, lc = left[i - 1]
            ro, rv, rc = right[j - 1]

            oc, ot = component_cost(lo, ro, onset_groups, "onset")
            vc, vt = component_cost(lv, rv, vowel_groups, "vowel")
            cc, ct = component_cost(lc, rc, coda_groups, "coda")
            sub_total = (oc + vc + cc) / 3.0

            cand_sub = (
                dp_total[i - 1][j - 1] + sub_total,
                dp_o[i - 1][j - 1] + oc,
                dp_v[i - 1][j - 1] + vc,
                dp_c[i - 1][j - 1] + cc,
            )
            cand_del = (
                dp_total[i - 1][j] + insdel,
                dp_o[i - 1][j] + insdel,
                dp_v[i - 1][j] + insdel,
                dp_c[i - 1][j] + insdel,
            )
            cand_ins = (
                dp_total[i][j - 1] + insdel,
                dp_o[i][j - 1] + insdel,
                dp_v[i][j - 1] + insdel,
                dp_c[i][j - 1] + insdel,
            )

            best = ("sub", i - 1, j - 1, {"oc": oc, "vc": vc, "cc": cc, "ot": ot, "vt": vt, "ct": ct})
            best_val = cand_sub
            if better(cand_del, best_val):
                best = ("del", i - 1, j, {})
                best_val = cand_del
            if better(cand_ins, best_val):
                best = ("ins", i, j - 1, {})
                best_val = cand_ins

            dp_total[i][j], dp_o[i][j], dp_v[i][j], dp_c[i][j] = best_val
            prev[i][j] = best

    denom = max(1.0, float(max(n, m)))

    def to_similarity(cost: float) -> int:
        norm = min(1.0, float(cost) / denom)
        return max(0, min(100, int(round(100 * (1.0 - norm)))))

    similarity = to_similarity(dp_total[-1][-1])
    onset_similarity = to_similarity(dp_o[-1][-1])
    vowel_similarity = to_similarity(dp_v[-1][-1])
    coda_similarity = to_similarity(dp_c[-1][-1])

    path_breakdown: list[dict] = []
    i = n
    j = m
    while i > 0 or j > 0:
        step = prev[i][j]
        if not step:
            break
        op, pi, pj, meta = step
        if op == "sub":
            a_syl = left_syllables[i - 1] if i - 1 < len(left_syllables) else ""
            b_syl = right_syllables[j - 1] if j - 1 < len(right_syllables) else ""
            lo, lv, lc = left[i - 1]
            ro, rv, rc = right[j - 1]
            path_breakdown.append(
                {
                    "op": "sub",
                    "a": a_syl,
                    "b": b_syl,
                    "a_jamo": {"onset": lo, "vowel": lv, "coda": lc},
                    "b_jamo": {"onset": ro, "vowel": rv, "coda": rc},
                    "onset": meta.get("ot", ""),
                    "vowel": meta.get("vt", ""),
                    "coda": meta.get("ct", ""),
                    "cost": round(float(meta.get("oc", 0.0) + meta.get("vc", 0.0) + meta.get("cc", 0.0)) / 3.0, 4),
                }
            )
            i, j = pi, pj
            continue
        if op == "del":
            a_syl = left_syllables[i - 1] if i - 1 < len(left_syllables) else ""
            path_breakdown.append({"op": "del", "a": a_syl, "b": "", "cost": round(insdel, 4)})
            i, j = pi, pj
            continue
        a_syl = ""
        b_syl = right_syllables[j - 1] if j - 1 < len(right_syllables) else ""
        path_breakdown.append({"op": "ins", "a": a_syl, "b": b_syl, "cost": round(insdel, 4)})
        i, j = pi, pj

    path_breakdown.reverse()

    def summarize_best_path() -> list[str]:
        steps: list[str] = []
        for row in path_breakdown:
            if row.get("op") != "sub":
                continue
            aj = row.get("a_jamo", {}) or {}
            bj = row.get("b_jamo", {}) or {}
            if row.get("onset") != "same":
                steps.append(f"초성 {aj.get('onset','')}→{bj.get('onset','')}")
            if row.get("vowel") != "same":
                steps.append(f"중성 {aj.get('vowel','')}→{bj.get('vowel','')}")
            if row.get("coda") != "same":
                left_coda = aj.get("coda", "")
                right_coda = bj.get("coda", "")
                if left_coda == "" or right_coda == "":
                    steps.append(f"종성 약화 {left_coda or '∅'}→{right_coda or '∅'}")
                else:
                    steps.append(f"종성 {left_coda}→{right_coda}")
            if len(steps) >= 3:
                break
        return steps

    return {
        "similarity": similarity,
        "onset_similarity": onset_similarity,
        "vowel_similarity": vowel_similarity,
        "coda_similarity": coda_similarity,
        "best_path": summarize_best_path(),
        "path_breakdown": path_breakdown[:12],
    }


def roman_mark_to_korean_pronunciation_candidates(mark: str) -> list[dict]:
    raw_text = str(mark or "").strip()
    if any(_is_hangul_syllable(ch) for ch in raw_text):
        return []
    roman = _normalize_roman(mark)
    if not roman:
        return []

    def map_onset(ch: str) -> list[tuple[str, float, str]]:
        if ch in {"P"}:
            return [("ㅍ", 1.0, "P->ㅍ")]
        if ch in {"B"}:
            return [("ㅂ", 1.0, "B->ㅂ")]
        if ch in {"F"}:
            return [("ㅍ", 1.0, "F->ㅍ"), ("ㅎ", 0.68, "F->ㅎ(weak)")]
        if ch in {"V"}:
            return [("ㅂ", 0.78, "V->ㅂ(weak)"), ("ㅍ", 0.70, "V->ㅍ(weak)")]
        if ch in {"K", "C", "Q"}:
            return [("ㅋ", 1.0, f"{ch}->ㅋ")]
        if ch in {"G"}:
            return [("ㄱ", 0.85, "G->ㄱ(weak)")]
        if ch in {"T"}:
            return [("ㅌ", 1.0, "T->ㅌ")]
        if ch in {"D"}:
            return [("ㄷ", 0.86, "D->ㄷ(weak)")]
        if ch in {"S", "Z"}:
            return [("ㅅ", 0.9, f"{ch}->ㅅ(weak)")]
        if ch in {"J"}:
            return [("ㅈ", 0.9, "J->ㅈ(weak)")]
        if ch in {"R", "L"}:
            return [("ㄹ", 0.92, f"{ch}->ㄹ")]
        if ch in {"M"}:
            return [("ㅁ", 1.0, "M->ㅁ")]
        if ch in {"N"}:
            return [("ㄴ", 1.0, "N->ㄴ")]
        if ch in {"H"}:
            return [("ㅎ", 0.9, "H->ㅎ(weak)")]
        if ch in {"W"}:
            return [("ㅇ", 0.62, "W->ㅇ(weak)")]
        return [("ㅇ", 0.55, f"{ch}->ㅇ(weak)")]

    def map_vowel(chunk: str) -> tuple[str, float, str]:
        if chunk in {"OO", "OU", "U", "UE", "EW"}:
            return "ㅜ", 1.0, f"{chunk}->ㅜ"
        if chunk in {"EE", "I", "IE", "Y"}:
            return "ㅣ", 1.0, f"{chunk}->ㅣ"
        if chunk in {"AI", "AY", "EI"}:
            return "ㅔ", 0.9, f"{chunk}->ㅔ(weak)"
        if chunk in {"OI", "OY"}:
            return "ㅚ", 0.88, f"{chunk}->ㅚ(weak)"
        if chunk in {"AU", "AW", "O"}:
            return "ㅗ", 0.88, f"{chunk}->ㅗ(weak)"
        if chunk in {"A", "AE", "E"}:
            return "ㅐ", 0.8, f"{chunk}->ㅐ(weak)"
        return "ㅏ", 0.62, f"{chunk or '∅'}->ㅏ(implied)"

    def compose(onset: str, vowel: str) -> str:
        if onset not in _CHOSUNG or vowel not in _JUNGSUNG:
            return ""
        choseong = _CHOSUNG.index(onset)
        jungseong = _JUNGSUNG.index(vowel)
        code = 0xAC00 + choseong * 588 + jungseong * 28
        return chr(code)

    tokens: list[str] = []
    i = 0
    while i < len(roman):
        matched = None
        for chunk in _EN_VOWEL_CHUNKS:
            if roman.startswith(chunk, i):
                matched = chunk
                break
        if matched:
            tokens.append(matched)
            i += len(matched)
            continue
        tokens.append(roman[i])
        i += 1

    syllables: list[dict] = [{"seq": [], "weight": 1.0, "path": []}]
    idx = 0
    while idx < len(tokens):
        t = tokens[idx]
        if re.fullmatch(r"[A-Z]", t) and t not in {"A", "E", "I", "O", "U", "Y"}:
            onsets = map_onset(t)
            vowel = "ㅏ"
            vowel_w = 0.62
            vowel_path = "∅->ㅏ(implied)"
            if idx + 1 < len(tokens) and (
                tokens[idx + 1] in _EN_VOWEL_CHUNKS or tokens[idx + 1] in {"A", "E", "I", "O", "U", "Y"}
            ):
                nxt = tokens[idx + 1]
                chunk = nxt if nxt in _EN_VOWEL_CHUNKS else nxt
                vowel, vowel_w, vowel_path = map_vowel(chunk)
                idx += 1
            expanded: list[dict] = []
            for base in syllables:
                for onset, onset_w, onset_path in onsets:
                    syl = compose(onset, vowel)
                    if syl:
                        expanded.append(
                            {
                                "seq": [*base["seq"], syl],
                                "weight": float(base["weight"]) * float(onset_w) * float(vowel_w),
                                "path": [*base["path"], onset_path, vowel_path],
                            }
                        )
            syllables = expanded or syllables
        idx += 1

    candidates: list[dict] = []
    for item in syllables:
        seq = item.get("seq", [])
        if not seq:
            continue
        pron = "".join(seq)
        w = max(0.35, min(1.0, float(item.get("weight", 0.0))))
        candidates.append({"pronunciation": pron, "weight": round(w, 4), "path": item.get("path", [])})

    ranked = sorted(candidates, key=lambda r: (-float(r.get("weight", 0.0)), len(str(r.get("pronunciation", "")))))
    deduped: dict[str, dict] = {}
    for row in ranked:
        key = str(row.get("pronunciation", "")).strip()
        if not key:
            continue
        if key not in deduped:
            deduped[key] = row

    extended: list[dict] = []
    for row in list(deduped.values())[:8]:
        extended.append(row)
        pron = str(row.get("pronunciation", ""))
        if pron.endswith("키"):
            extended.append({"pronunciation": pron + "이", "weight": round(float(row.get("weight", 0.0)) * 0.88, 4), "path": [*list(row.get("path", []) or []), "키->키이(weak)"]})

    final: list[dict] = []
    seen = set()
    for row in extended:
        key = str(row.get("pronunciation", "")).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        final.append(row)
        if len(final) >= 8:
            break
    return final


def roman_mark_to_korean_pronunciations(mark: str) -> list[str]:
    return [row.get("pronunciation", "") for row in roman_mark_to_korean_pronunciation_candidates(mark) if row.get("pronunciation")]


def _apply_digraph_variants(value: str) -> list[tuple[str, list[str], float]]:
    weights = get_rule_weights()
    upper = str(value or "").upper()
    variants = [(upper, [], 0.0)]
    for src, outs in DIGRAPH_RULES.items():
        next_variants: list[tuple[str, list[str], float]] = []
        for current, path, cost in variants:
            if src not in current:
                next_variants.append((current, path, cost))
                continue
            for out in outs:
                next_variants.append(
                    (
                        current.replace(src, out),
                        [*path, f"{src}->{out or '∅'}"],
                        cost + float(weights.get("digraph", 0.10)),
                    )
                )
        variants = next_variants
    return variants


def _variant_similarity_score(variant: str, target: str, path_cost: float) -> int:
    base = int(round(SequenceMatcher(None, variant, target).ratio() * 100))
    penalty = int(round(min(1.0, float(path_cost or 0.0)) * 70))
    return max(0, min(100, base - penalty))


def generate_phonetic_variants(mark: str, max_variants: int = 48) -> list[dict]:
    weights = get_rule_weights()
    roman = _normalize_roman(mark)
    if not roman:
        return [{"variant": str(mark or ""), "path": [], "path_cost": 0.0, "path_score": 100, "path_type": "identity"}]

    base_variants = _apply_digraph_variants(roman)
    best_cost: dict[str, float] = {}
    queue = deque()

    results: list[dict] = []
    seen = set()

    def push(variant: str, path: list[str], cost: float, kind: str) -> None:
        key = variant
        prev = best_cost.get(key)
        if prev is not None and prev <= cost:
            return
        best_cost[key] = cost
        queue.append((variant, path, cost))
        if (variant, tuple(path)) not in seen:
            results.append(
                {
                    "variant": variant,
                    "path": path,
                    "path_cost": round(cost, 4),
                    "path_score": max(0, min(100, int(round((1.0 - min(1.0, cost)) * 100)))),
                    "path_type": kind,
                }
            )
            seen.add((variant, tuple(path)))

    for base, path, cost in base_variants:
        kind = "identity" if not path else "digraph"
        push(base, path, cost, kind)

    consonant_swaps = {
        "P": [("B", float(weights.get("P/B", 0.32)), "consonant_swap_weak"), ("F", float(weights.get("P/F", 0.22)), "consonant_swap_medium")],
        "B": [("P", float(weights.get("P/B", 0.32)), "consonant_swap_weak")],
        "F": [("P", float(weights.get("P/F", 0.22)), "consonant_swap_medium")],
        "K": [("G", float(weights.get("K/G", 0.32)), "consonant_swap_weak")],
        "G": [("K", float(weights.get("K/G", 0.32)), "consonant_swap_weak")],
        "T": [("D", float(weights.get("T/D", 0.32)), "consonant_swap_weak")],
        "D": [("T", float(weights.get("T/D", 0.32)), "consonant_swap_weak")],
        "R": [("L", float(weights.get("R/L", 0.22)), "consonant_swap_medium")],
        "L": [("R", float(weights.get("R/L", 0.22)), "consonant_swap_medium")],
    }

    while queue and len(results) < max_variants:
        current, path, cost = queue.popleft()
        if not current:
            continue
        if cost > 0.85:
            continue

        if current.endswith("IE"):
            push(current[:-2] + "Y", [*path, "IE->Y"], cost + float(weights.get("end_vowel", 0.08)), "vowel_ending")
        if current.endswith("EE"):
            push(current[:-2] + "Y", [*path, "EE->Y"], cost + float(weights.get("end_vowel", 0.08)), "vowel_ending")
        if current.endswith("E") and len(current) >= 4:
            push(current[:-1], [*path, "E->∅"], cost + float(weights.get("silent_e", 0.10)), "silent_e")
        if "OO" in current:
            push(current.replace("OO", "U"), [*path, "OO->U"], cost + float(weights.get("double_vowel", 0.18)), "vowel_group")
        if "OU" in current:
            push(current.replace("OU", "U"), [*path, "OU->U"], cost + float(weights.get("double_vowel", 0.18)), "vowel_group")
        if "IE" in current and not current.endswith("IE"):
            push(current.replace("IE", "I"), [*path, "IE->I"], cost + float(weights.get("double_vowel", 0.18)), "vowel_group")
        if "EE" in current:
            push(current.replace("EE", "I"), [*path, "EE->I"], cost + float(weights.get("double_vowel", 0.18)), "vowel_group")
        if current.endswith("Y"):
            push(current[:-1] + "I", [*path, "Y->I"], cost + float(weights.get("end_vowel", 0.08)), "vowel_ending")

        first = current[0]
        swaps = consonant_swaps.get(first, [])
        for rep, rep_cost, kind in swaps:
            if rep == first:
                continue
            push(rep + current[1:], [*path, f"{first}->{rep}"], cost + rep_cost, kind)

        if len(current) >= 2 and current[-1] == current[-2]:
            push(current[:-1], [*path, f"{current[-1]}{current[-1]}->{current[-1]}"], cost + 0.12, "repeat_collapse")

    deduped: dict[str, dict] = {}
    for row in results:
        key = row["variant"]
        prev = deduped.get(key)
        if prev is None or row["path_cost"] < prev["path_cost"]:
            deduped[key] = row
    final = sorted(deduped.values(), key=lambda r: (r["path_cost"], -r["path_score"], len(r["variant"])))
    return final[:max_variants]


def analyze_phonetic_similarity(source: str, target: str, max_paths: int = 12) -> dict:
    source_has_hangul = any(_is_hangul_syllable(ch) for ch in str(source or ""))
    target_has_hangul = any(_is_hangul_syllable(ch) for ch in str(target or ""))
    cross_script = bool(source_has_hangul or target_has_hangul)

    src = _normalize_roman(source)
    tgt = _normalize_roman(target)
    roman_key_similarity = int(round(SequenceMatcher(None, src, tgt).ratio() * 100)) if src and tgt else 0
    roman_reliable = bool(src and tgt and min(len(src), len(tgt)) >= 3)
    if not roman_reliable and roman_key_similarity:
        roman_key_similarity = min(roman_key_similarity, 80)

    src_variants = generate_phonetic_variants(source, max_variants=max_paths * 4) if roman_reliable else []
    tgt_variants = generate_phonetic_variants(target, max_variants=max_paths * 4) if roman_reliable else []

    pairs: list[dict] = []
    for sv in src_variants:
        for tv in tgt_variants[: max(8, max_paths)]:
            score = _variant_similarity_score(str(sv["variant"]), str(tv["variant"]), float(sv["path_cost"]) + float(tv["path_cost"]))
            pairs.append(
                {
                    "path": [*sv["path"], *tv["path"]],
                    "score": score,
                    "source_variant": sv["variant"],
                    "target_variant": tv["variant"],
                    "path_cost": round(float(sv["path_cost"]) + float(tv["path_cost"]), 4),
                }
            )
    pairs.sort(key=lambda r: (-r["score"], r["path_cost"]))
    top_pairs = pairs[:max_paths]
    best = top_pairs[0] if top_pairs else {"score": roman_key_similarity, "path": []}
    breakdown_pairs: list[dict] = []
    seen_paths: set[tuple[str, ...]] = set()

    def _add_breakdown(match: dict | None) -> None:
        if not match:
            return
        key = tuple(str(step or "") for step in (match.get("path", []) or []))
        if key in seen_paths:
            return
        seen_paths.add(key)
        breakdown_pairs.append(match)

    def _first_pair_with_steps(needles: set[str]) -> dict | None:
        for row in pairs[: max(120, max_paths * 20)]:
            path = set(str(step or "") for step in (row.get("path", []) or []))
            if path & needles:
                return row
        return None

    _add_breakdown(best if isinstance(best, dict) else None)
    _add_breakdown(
        _first_pair_with_steps({"IE->Y", "EE->Y", "Y->I", "E->∅", "OO->U", "OU->U"})
    )
    _add_breakdown(_first_pair_with_steps({"P->F", "F->P", "R->L", "L->R"}))
    _add_breakdown(_first_pair_with_steps({"P->B", "B->P", "K->G", "G->K", "T->D", "D->T"}))
    for row in top_pairs:
        if len(breakdown_pairs) >= 3:
            break
        _add_breakdown(row)

    def hangul_only(text: str) -> str:
        return "".join(ch for ch in str(text or "").strip() if _is_hangul_syllable(ch))

    src_hangul_candidates: list[dict] = []
    tgt_hangul_candidates: list[dict] = []
    if source_has_hangul:
        src_hangul_candidates.append({"text": hangul_only(source), "weight": 1.0, "origin": "hangul", "path": []})
    else:
        for row in roman_mark_to_korean_pronunciation_candidates(source):
            src_hangul_candidates.append(
                {"text": row.get("pronunciation", ""), "weight": float(row.get("weight", 0.0)), "origin": "roman", "path": row.get("path", [])}
            )
    if target_has_hangul:
        tgt_hangul_candidates.append({"text": hangul_only(target), "weight": 1.0, "origin": "hangul", "path": []})
    else:
        for row in roman_mark_to_korean_pronunciation_candidates(target):
            tgt_hangul_candidates.append(
                {"text": row.get("pronunciation", ""), "weight": float(row.get("weight", 0.0)), "origin": "roman", "path": row.get("path", [])}
            )

    hangul_best_raw = 0
    hangul_best_effective = 0
    hangul_best_onset = 0
    hangul_best_vowel = 0
    hangul_best_coda = 0
    hangul_best_path: list[str] = []
    hangul_path_breakdown: list[dict] = []
    hangul_best_pair: dict = {}

    for a in (src_hangul_candidates[:8] or []):
        a_text = str(a.get("text", "")).strip()
        if not a_text:
            continue
        for b in (tgt_hangul_candidates[:8] or []):
            b_text = str(b.get("text", "")).strip()
            if not b_text:
                continue
            analysis = hangul_pronunciation_similarity(a_text, b_text) or {}
            raw = int(analysis.get("similarity", 0) or 0)
            wa = max(0.0, min(1.0, float(a.get("weight", 0.0) or 0.0)))
            wb = max(0.0, min(1.0, float(b.get("weight", 0.0) or 0.0)))
            effective = int(round(raw * wa * wb))
            if effective < hangul_best_effective:
                continue
            if effective == hangul_best_effective and raw <= hangul_best_raw:
                continue
            hangul_best_effective = effective
            hangul_best_raw = raw
            hangul_best_onset = int(round(int(analysis.get("onset_similarity", 0) or 0) * wa * wb))
            hangul_best_vowel = int(round(int(analysis.get("vowel_similarity", 0) or 0) * wa * wb))
            hangul_best_coda = int(round(int(analysis.get("coda_similarity", 0) or 0) * wa * wb))
            hangul_best_path = list(analysis.get("best_path", []) or [])
            hangul_path_breakdown = list(analysis.get("path_breakdown", []) or [])
            hangul_best_pair = {
                "source_pronunciation": a_text,
                "target_pronunciation": b_text,
                "source_weight": round(wa, 4),
                "target_weight": round(wb, 4),
                "source_origin": a.get("origin", ""),
                "target_origin": b.get("origin", ""),
                "source_path": a.get("path", []),
                "target_path": b.get("path", []),
            }

    best_path_score = int(best.get("score", 0))
    aggregate = 0
    if top_pairs:
        weights = [max(0.15, 1.0 - float(p["path_cost"])) for p in top_pairs[:3]]
        aggregate = int(round(sum(p["score"] * w for p, w in zip(top_pairs[:3], weights)) / sum(weights)))
    roman_signal = roman_key_similarity if roman_reliable else 0
    hangul_signal = int(hangul_best_effective)
    if not cross_script:
        hangul_signal = int(round(hangul_signal * 0.82))
        if best_path_score:
            hangul_signal = min(hangul_signal, best_path_score + 6)
        hangul_signal = min(hangul_signal, 92)
    phonetic_similarity_raw = int(max(best_path_score, aggregate, hangul_signal, roman_signal))

    guardrail_flags: list[str] = []
    phonetic_similarity = phonetic_similarity_raw

    src_hg = _hangul_only(source)
    tgt_hg = _hangul_only(target)
    src_rm = src
    tgt_rm = tgt

    if (src_hg and tgt_hg and src_hg == tgt_hg) or (src_rm and tgt_rm and src_rm == tgt_rm):
        pass
    else:
        a_key = src_rm if src_rm else src_hg
        b_key = tgt_rm if tgt_rm else tgt_hg
        min_len = min(len(a_key), len(b_key))
        if 3 <= min_len <= 4:
            dist = _edit_distance_small(a_key, b_key, limit=1)
            if dist <= 1 and phonetic_similarity > 84:
                phonetic_similarity = 84
                guardrail_flags.append("short_mark_no_overhigh")

        common_suffix_len = _longest_common_suffix_len(a_key, b_key)
        if common_suffix_len >= 3 and min_len >= 6:
            if src_hg and tgt_hg:
                head_a = src_hg[:1]
                head_b = tgt_hg[:1]
                head_sim = hangul_pronunciation_similarity(head_a, head_b).get("similarity", 0)
                if int(head_sim or 0) < 55 and phonetic_similarity > 78:
                    phonetic_similarity = 78
                    guardrail_flags.append("prefix_mismatch_tail_only")
            else:
                head_a = src_rm[:1]
                head_b = tgt_rm[:1]
                head_same_group = False
                for group in CONSONANT_GROUPS_EN:
                    if head_a in group and head_b in group:
                        head_same_group = True
                        break
                if head_a and head_b and (head_a != head_b) and not head_same_group and phonetic_similarity > 78:
                    phonetic_similarity = 78
                    guardrail_flags.append("prefix_mismatch_tail_only")

        if src_rm and tgt_rm:
            for suf in _COMMON_SUFFIXES_EN:
                if src_rm.endswith(suf) and tgt_rm.endswith(suf) and len(src_rm) > len(suf) + 1 and len(tgt_rm) > len(suf) + 1:
                    stem_a = src_rm[: -len(suf)]
                    stem_b = tgt_rm[: -len(suf)]
                    if SequenceMatcher(None, stem_a, stem_b).ratio() < 0.55 and phonetic_similarity > 72:
                        phonetic_similarity = 72
                        guardrail_flags.append("common_suffix_only")
                    break
        if src_hg and tgt_hg:
            for suf in _COMMON_SUFFIXES_KO:
                if src_hg.endswith(suf) and tgt_hg.endswith(suf) and len(src_hg) > len(suf) + 1 and len(tgt_hg) > len(suf) + 1:
                    stem_a = src_hg[: -len(suf)]
                    stem_b = tgt_hg[: -len(suf)]
                    if hangul_pronunciation_similarity(stem_a, stem_b).get("similarity", 0) < 55 and phonetic_similarity > 72:
                        phonetic_similarity = 72
                        guardrail_flags.append("common_suffix_only")
                    break

        if src_rm and tgt_rm:
            if _roman_cv_pattern(src_rm) and _roman_cv_pattern(src_rm) == _roman_cv_pattern(tgt_rm):
                if SequenceMatcher(None, src_rm, tgt_rm).ratio() < 0.6 and phonetic_similarity > 82:
                    phonetic_similarity = 82
                    guardrail_flags.append("pattern_only_no_high")
        if src_hg and tgt_hg:
            left_parts = _decompose_hangul(src_hg)
            right_parts = _decompose_hangul(tgt_hg)
            if left_parts and right_parts:
                left_vowels = "".join(v for _, v, _ in left_parts)
                right_vowels = "".join(v for _, v, _ in right_parts)
                if left_vowels and left_vowels == right_vowels:
                    onset_sim = hangul_pronunciation_similarity(src_hg, tgt_hg).get("onset_similarity", 0)
                    if int(onset_sim or 0) < 70 and phonetic_similarity > 82:
                        phonetic_similarity = 82
                        guardrail_flags.append("pattern_only_no_high")

    label = "발음 유사"
    label_score = max(best_path_score, hangul_signal)
    if label_score >= 92:
        label = "발음 매우 유사"
    elif label_score >= 80:
        label = "발음 유사"
    elif label_score >= 65:
        label = "발음 일부 유사"
    else:
        label = "발음 유사 낮음"

    onset_similarity = max(int(roman_key_similarity), int(hangul_best_onset))
    vowel_similarity = max(int(roman_key_similarity), int(hangul_best_vowel))
    coda_similarity = max(int(roman_key_similarity), int(hangul_best_coda))

    return {
        "phonetic_similarity": int(max(0, min(100, phonetic_similarity))),
        "best_path_score": int(best_path_score),
        "aggregate_path_score": int(aggregate),
        "best_path": best.get("path", []),
        "best_path_label": label,
        "roman_key_similarity": int(roman_key_similarity),
        "phonetic_similarity_raw": int(max(0, min(100, phonetic_similarity_raw))),
        "phonetic_guardrail_flags": guardrail_flags,
        "hangul_pronunciation_similarity": int(hangul_signal),
        "hangul_pronunciation_raw": int(hangul_best_raw),
        "hangul_best_path": hangul_best_path,
        "hangul_path_breakdown": hangul_path_breakdown,
        "hangul_best_pair": hangul_best_pair,
        "syllable_structure_similarity": int(max(roman_key_similarity, hangul_best_raw)),
        "onset_similarity": int(onset_similarity),
        "vowel_similarity": int(vowel_similarity),
        "coda_similarity": int(coda_similarity),
        "path_breakdown": [{"path": p["path"], "score": p["score"]} for p in breakdown_pairs[:3]],
    }


from __future__ import annotations

from collections import defaultdict
import re
import unicodedata

_INITIAL = re.compile(r"^[A-Za-z]$")


def _clean(raw: str) -> str:
    text = unicodedata.normalize("NFKD", str(raw or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _title(name: str) -> str:
    parts: list[str] = []
    for token in _clean(name).split(" "):
        if "-" in token:
            parts.append("-".join(p.capitalize() for p in token.split("-") if p))
        else:
            parts.append(token.capitalize())
    return " ".join(parts)


def _first_last(name: str) -> tuple[str, str]:
    tokens = _title(name).split(" ")
    if not tokens:
        return "", ""
    if len(tokens) == 1:
        return tokens[0], ""
    return tokens[0], tokens[-1]


def _compatible(a: str, b: str) -> bool:
    fa, la = _first_last(a)
    fb, lb = _first_last(b)
    if not fa or not fb:
        return False
    if la and lb and la.casefold() != lb.casefold():
        return False

    same_first = fa.casefold() == fb.casefold()
    shorter, longer = sorted([fa, fb], key=lambda item: (len(item), item))
    prefix = len(shorter) >= 3 and longer.casefold().startswith(shorter.casefold())
    initial_match = False
    if la and lb and la.casefold() == lb.casefold():
        initial_match = (_INITIAL.match(fa) and fb.casefold().startswith(fa.casefold())) or (
            _INITIAL.match(fb) and fa.casefold().startswith(fb.casefold())
        )
    return same_first or prefix or initial_match


def cluster_names(raw_names: list[str]) -> dict[str, str]:
    """Map each raw name to a canonical form discovered only from this CSV."""
    cleaned = [_title(name) for name in raw_names if _clean(name)]
    unique: list[str] = []
    for name in cleaned:
        if name and name not in unique:
            unique.append(name)

    parent = {name: name for name in unique}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, left in enumerate(unique):
        for right in unique[i + 1 :]:
            if _compatible(left, right):
                a, b = find(left), find(right)
                if a != b:
                    parent[b] = a

    groups: dict[str, list[str]] = defaultdict(list)
    for name in unique:
        groups[find(name)].append(name)

    canonical_for_root = {
        root: max(members, key=lambda item: (len(item), item))
        for root, members in groups.items()
    }
    mapping: dict[str, str] = {}
    for raw in raw_names:
        titled = _title(raw)
        if not titled:
            continue
        mapping[raw] = canonical_for_root[find(titled)]
        mapping[titled] = mapping[raw]
        mapping[raw.casefold()] = mapping[raw]
        mapping[titled.casefold()] = mapping[raw]
    return mapping

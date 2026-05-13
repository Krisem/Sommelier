"""
Score-database-leser for knowledge/scores/*.md

Indekserer alle markdown-kilder i knowledge/scores/ etter Polets varenummer.
Brukes som høyeste-prioritets kvalitetssignal i value_score.py.

Schema for hver vin (i markdown):
    ### [<score>] <navn> — Varenummer <varenr>
    - **Produsent:** ...
    - **Pris:** ...
    - **Notat:** ...

Frontmatter (--- ... ---) på toppen av hver fil ekstraheres som metadata
(kilde, dato, forfatter, skala).
"""

import functools
import re
from pathlib import Path
from typing import Optional

SCORES_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "scores"


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Returnerer (metadata, body)."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end < 0:
        return {}, text
    fm_text = text[3:end].strip()
    body = text[end + 4:].lstrip("\n")
    meta: dict = {}
    for ln in fm_text.splitlines():
        if ":" in ln:
            k, _, v = ln.partition(":")
            meta[k.strip()] = v.strip()
    return meta, body


def _parse_entries(body: str, source_meta: dict) -> list[dict]:
    """Trekk ut alle vin-entries fra én markdown-body."""
    entries: list[dict] = []
    # Match overskrift: ### [<score>] <navn> — Varenummer <varenr>
    heading_re = re.compile(
        r"^###\s*\[(\d{1,3}(?:[.,]\d)?)\]\s*(.+?)\s*[—–-]\s*Varenummer\s*(\d+)\s*$",
        re.MULTILINE,
    )
    matches = list(heading_re.finditer(body))
    for i, m in enumerate(matches):
        score = float(m.group(1).replace(",", "."))
        name = m.group(2).strip()
        varenr = m.group(3).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        block = body[start:end]

        entry: dict = {
            "score": score,
            "name": name,
            "varenummer": varenr,
            "kilde": source_meta.get("kilde", ""),
            "test": source_meta.get("test", ""),
            "dato": source_meta.get("dato", ""),
            "skala": source_meta.get("skala", ""),
            "kilde_url": source_meta.get("url", ""),
        }
        for field, key in [
            ("Produsent", "produsent"),
            ("Pris", "pris"),
            ("Utvalg", "utvalg"),
            ("Importør", "importor"),
            ("Anmelder", "anmelder"),
            ("Notat", "notat"),
        ]:
            fm = re.search(
                rf"-\s*\*\*{field}:\*\*\s*(.+?)(?=\n-\s*\*\*|\n###|\n##|\Z)",
                block,
                re.DOTALL,
            )
            if fm:
                entry[key] = re.sub(r"\s+", " ", fm.group(1)).strip()
        entries.append(entry)
    return entries


@functools.lru_cache(maxsize=1)
def index() -> dict[str, list[dict]]:
    """
    Bygg in-memory indeks over alle viner i knowledge/scores/.

    Returnerer dict {polet_varenr: [entry, entry, ...]}. En vin kan ha
    flere entries hvis den er vurdert i flere kilder.
    """
    out: dict[str, list[dict]] = {}
    if not SCORES_DIR.exists():
        return out
    for path in sorted(SCORES_DIR.glob("*.md")):
        if path.name == "INDEX.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        meta, body = _parse_frontmatter(text)
        meta["_file"] = path.name
        for e in _parse_entries(body, meta):
            out.setdefault(e["varenummer"], []).append(e)
    return out


def get_user_scores(polet_id: str) -> list[dict]:
    """
    Slå opp alle kuraterte scores for et Polet-varenummer.
    Returnerer tom liste hvis ingen treff.
    """
    return index().get(str(polet_id), [])


def best_score(polet_id: str) -> Optional[dict]:
    """Snarvei: høyeste score for varenr, eller None."""
    matches = get_user_scores(polet_id)
    if not matches:
        return None
    return max(matches, key=lambda e: e["score"])


if __name__ == "__main__":
    import sys
    idx = index()
    print(f"Indeksert {sum(len(v) for v in idx.values())} entries "
          f"fra {len(idx)} unike viner")
    if len(sys.argv) > 1:
        for e in get_user_scores(sys.argv[1]):
            print(f"  [{e['score']}] {e['name']} ({e['kilde']}, {e['test']})")
            print(f"    {e.get('notat', '')[:200]}")

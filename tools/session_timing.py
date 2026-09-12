"""
Tidsbruksanalyse av en Claude Code-økt (JSONL-transkript).

Bryter veggklokketida ned i verktøytid (tid inne i verktøykall) og modelltid
(resten: tenking, skriving, venting). Erstatter engangsskriptene timeline.py,
detail.py, agg.py, split.py og phases.py.

Bruk:
    python3 -m tools.session_timing <transkript.jsonl> [--fra HH:MM:SS]
        [--til HH:MM:SS] [--faser faser.json] [--json]

Verktøytid = sum av (tool_result-tid − tool_use-tid), paret på `tool_use_id`.
Et kall som starter i vinduet teller med hele varigheten sin. Per fase klippes
varigheten mot fasegrensene, slik at en fase aldri får mer verktøytid enn den
har veggklokke — det var nettopp den klippinga split.py manglet.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

BLOKKTYPER = ("text", "thinking", "tool_use", "tool_result")


@dataclass
class Hendelse:
    """Én innholdsblokk med tidsstempel."""

    tid: datetime
    art: str
    navn: str = ""
    uid: str = ""
    innhold: str = ""
    storrelse: int = 0


@dataclass
class Kall:
    """Et verktøykall, paret med resultatet sitt (slutt=None om uparet)."""

    uid: str
    navn: str
    innhold: str
    start: datetime
    slutt: Optional[datetime] = None
    storrelse: int = 0
    gap: float = 0.0

    @property
    def varighet(self) -> float:
        return (self.slutt - self.start).total_seconds() if self.slutt else 0.0


def _tid(raa) -> Optional[datetime]:
    """ISO-streng eller millisekunder (int) -> lokal naiv tid. None om ubrukelig."""
    if raa is None:
        return None
    if isinstance(raa, (int, float)) and not isinstance(raa, bool):
        return datetime.fromtimestamp(raa / 1000)
    try:
        stempel = datetime.fromisoformat(str(raa).replace("Z", "+00:00"))
    except ValueError:
        return None
    return stempel.astimezone().replace(tzinfo=None) if stempel.tzinfo else stempel


def _blokker(melding) -> list[dict]:
    """message.content er enten en streng eller en liste av blokker."""
    innhold = (melding or {}).get("content") if isinstance(melding, dict) else None
    if isinstance(innhold, str):
        return [{"type": "text", "text": innhold}]
    if isinstance(innhold, list):
        return [b for b in innhold if isinstance(b, dict)]
    return []


def les_hendelser(sti) -> list[Hendelse]:
    """Leser transkriptet. Linjer uten tidsstempel hoppes over."""
    hendelser: list[Hendelse] = []
    with open(sti, encoding="utf-8") as fil:
        for linje in fil:
            linje = linje.strip()
            if not linje:
                continue
            try:
                rad = json.loads(linje)
            except json.JSONDecodeError:
                continue
            if not isinstance(rad, dict):
                continue
            tid = _tid(rad.get("timestamp"))
            if tid is None:  # mode, permission-mode, attachment, snapshot ...
                continue
            for blokk in _blokker(rad.get("message")):
                art = blokk.get("type")
                if art not in BLOKKTYPER:
                    continue
                if art == "tool_use":
                    inn = json.dumps(blokk.get("input", {}), ensure_ascii=False)
                    hendelser.append(Hendelse(tid, art, navn=str(blokk.get("name") or ""),
                                              uid=str(blokk.get("id") or ""), innhold=inn))
                elif art == "tool_result":
                    ut = blokk.get("content")
                    hendelser.append(Hendelse(tid, art, uid=str(blokk.get("tool_use_id") or ""),
                                              storrelse=len(json.dumps(ut, ensure_ascii=False)) if ut else 0))
                else:
                    hendelser.append(Hendelse(tid, art, storrelse=len(blokk.get(art) or "")))
    hendelser.sort(key=lambda h: h.tid)  # stabil: filrekkefølge ved likt stempel
    return hendelser


def par_verktoy(hendelser: list[Hendelse]) -> list[Kall]:
    """Parer tool_use med tool_result på tool_use_id."""
    apne: dict[str, Kall] = {}
    rekke: list[Kall] = []
    for h in hendelser:
        if h.art == "tool_use":
            kall = Kall(h.uid, h.navn, h.innhold, h.tid)
            rekke.append(kall)
            if h.uid:
                apne[h.uid] = kall
        elif h.art == "tool_result":
            kall = apne.pop(h.uid, None)
            if kall is not None:
                kall.slutt, kall.storrelse = h.tid, h.storrelse
    return rekke


def _tidspunkt(klokke: str, hendelser: list[Hendelse]) -> datetime:
    """HH:MM:SS forankres i den datoen i transkriptet som gir et punkt i økta."""
    klokkeslett = datetime.strptime(klokke, "%H:%M:%S").time()
    for dato in sorted({h.tid.date() for h in hendelser}):
        kandidat = datetime.combine(dato, klokkeslett)
        if kandidat >= hendelser[0].tid:
            return kandidat
    return datetime.combine(hendelser[0].tid.date(), klokkeslett)


def _overlapp(a0: datetime, a1: datetime, b0: datetime, b1: datetime) -> float:
    """Sekunder [a0,a1] og [b0,b1] deler."""
    return max(0.0, (min(a1, b1) - max(a0, b0)).total_seconds())


def _pct(andel: float, helhet: float) -> float:
    return round(andel / helhet * 100, 1) if helhet > 0 else 0.0


def maal(hendelser: list[Hendelse], fra: Optional[str] = None, til: Optional[str] = None,
         faser: Optional[list[dict]] = None) -> dict:
    """Måler vinduet og returnerer rapporten som en dict."""
    if not hendelser:
        raise ValueError("transkriptet har ingen hendelser med tidsstempel")
    start = _tidspunkt(fra, hendelser) if fra else hendelser[0].tid
    slutt = _tidspunkt(til, hendelser) if til else hendelser[-1].tid
    veggklokke = (slutt - start).total_seconds()

    alle = par_verktoy(hendelser)
    etter_uid = {k.uid: k for k in alle if k.uid}
    forrige = start
    for h in hendelser:  # gap klippes mot vindusstart, aldri før den
        if h.art == "tool_use" and h.uid in etter_uid:
            etter_uid[h.uid].gap = (h.tid - max(forrige, start)).total_seconds()
        forrige = max(forrige, h.tid)

    kall = [k for k in alle if start <= k.start <= slutt]
    verktoytid = sum(k.varighet for k in kall)
    modelltid = veggklokke - verktoytid

    rapport = {
        "fra": start.strftime("%H:%M:%S"),
        "til": slutt.strftime("%H:%M:%S"),
        "veggklokke_s": round(veggklokke),
        "verktoykall": len(kall),
        "uparede_kall": sum(1 for k in kall if k.slutt is None),
        "verktoytid_s": round(verktoytid),
        "verktoytid_pct": _pct(verktoytid, veggklokke),
        "modelltid_s": round(modelltid),
        "modelltid_pct": _pct(modelltid, veggklokke),
        "tidslinje": [{"tid": k.start.strftime("%H:%M:%S"), "gap_s": round(k.gap),
                       "verktoy": k.navn, "input": re.sub(r"\s+", " ", k.innhold)[:120],
                       "varighet_s": round(k.varighet, 1), "resultat_tegn": k.storrelse}
                      for k in kall],
        "faser": [],
    }
    for fase in faser or []:
        f0, f1 = _tidspunkt(fase["fra"], hendelser), _tidspunkt(fase["til"], hendelser)
        lengde = (f1 - f0).total_seconds()
        # Et kall telles i fasen det STARTER i, men sekundene fordeles dit de
        # ble brukt: varigheten klippes mot fasegrensene. En fase kan derfor ha
        # verktøytid uten å ha noen kall — og får aldri mer enn veggklokka si.
        i_fasen = [k for k in kall if f0 <= k.start < f1]
        fase_vt = sum(_overlapp(k.start, k.slutt, f0, f1) for k in kall if k.slutt)
        rapport["faser"].append({
            "navn": fase.get("navn", ""), "fra": fase["fra"], "til": fase["til"],
            "veggklokke_s": round(lengde), "andel_pct": _pct(lengde, veggklokke),
            "verktoykall": len(i_fasen), "verktoytid_s": round(fase_vt),
        })
    return rapport


def formater(rapport: dict, sti: str = "") -> str:
    """Rapporten som tekst."""
    ut = []
    if sti:
        ut.append(f"Økt: {sti}")
    vegg = rapport["veggklokke_s"]
    ut.append(f"Vindu {rapport['fra']} -> {rapport['til']}   veggklokke {vegg} s = {vegg / 60:.1f} min")
    ut.append(f"Verktøykall: {rapport['verktoykall']}, verktøytid {rapport['verktoytid_s']} s "
              f"({rapport['verktoytid_pct']:.0f} %), modelltid {rapport['modelltid_s']} s "
              f"({rapport['modelltid_pct']:.0f} %)")
    if rapport["uparede_kall"]:
        ut.append(f"  (uparede kall uten resultat: {rapport['uparede_kall']} — teller 0 s)")
    if rapport["verktoytid_s"] > vegg:
        ut.append("  NB: verktøytid > veggklokke — kall har kjørt parallelt; modelltid er ikke meningsfull")
    ut.append("")
    ut.append(f"{'tid':8s} {'gap':>6s} {'brukt':>7s}  {'verktøy':16s} input / resultat")
    for rad in rapport["tidslinje"]:
        ut.append(f"{rad['tid']:8s} {rad['gap_s']:5.0f}s {rad['varighet_s']:6.1f}s  "
                  f"{rad['verktoy']:16s} {rad['input'][:70]}  -> {rad['resultat_tegn']} tegn")
    if rapport["faser"]:
        ut.append("")
        ut.append("Faser")
        for f in rapport["faser"]:
            ut.append(f"  {f['navn']:32s} {f['veggklokke_s']:5d}s ({f['andel_pct']:4.1f} %)  "
                      f"{f['verktoykall']:3d} kall, {f['verktoytid_s']:4d}s verktøytid")
    return "\n".join(ut)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bryt ned tidsbruken i en Claude Code-økt.")
    ap.add_argument("transkript", help="sti til .jsonl-transkriptet")
    ap.add_argument("--fra", help="startklokkeslett HH:MM:SS (standard: første hendelse)")
    ap.add_argument("--til", help="sluttklokkeslett HH:MM:SS (standard: siste hendelse)")
    ap.add_argument("--faser", help="JSON-fil med liste av {navn, fra, til}")
    ap.add_argument("--json", action="store_true", help="skriv rapporten som JSON")
    args = ap.parse_args(argv)

    faser = None
    if args.faser:
        with open(args.faser, encoding="utf-8") as fil:
            faser = json.load(fil)
    rapport = maal(les_hendelser(args.transkript), args.fra, args.til, faser)
    print(json.dumps(rapport, ensure_ascii=False, indent=2) if args.json
          else formater(rapport, args.transkript))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

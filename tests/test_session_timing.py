"""
Tester for tools/session_timing.py.

Transkriptet bygges syntetisk i tmp_path — ingen avhengighet til en økt på
disk. Tidsstempler lages fra lokale naive klokkeslett og serialiseres med det
lokale offsetet, så testene er uavhengige av tidssone.
"""

import json
from datetime import datetime, timedelta

import pytest

from tools.session_timing import (Hendelse, _blokker, _overlapp, _tid, formater,
                                  les_hendelser, maal, main, par_verktoy)

DAG = datetime(2026, 3, 4)


def kl(hms: str) -> datetime:
    """'10:00:05' -> lokal naiv datetime på testdagen."""
    t = datetime.strptime(hms, "%H:%M:%S").time()
    return datetime.combine(DAG.date(), t)


def iso(hms: str) -> str:
    return kl(hms).astimezone().isoformat()


def ms(hms: str) -> int:
    return int(kl(hms).timestamp() * 1000)


def _rad(stempel, rolle, blokker):
    return {"type": rolle, "timestamp": stempel, "message": {"role": rolle, "content": blokker}}


def skriv_transkript(sti) -> str:
    """Syntetisk økt: 10:00:00–10:02:00, kall A=10s, B=30s (ms-stempel), C uparet."""
    rader = [
        # content som ren streng
        {"type": "user", "timestamp": iso("10:00:00"), "message": {"role": "user", "content": "start"}},
        # linjer uten tidsstempel — skal hoppes over, ikke krasje
        {"type": "mode", "mode": "default"},
        {"type": "permission-mode", "permissionMode": "auto"},
        {"type": "file-history-snapshot", "snapshot": {}},
        {"type": "attachment", "attachment": {"type": "file"}},
        _rad(iso("10:00:05"), "assistant", [
            {"type": "thinking", "thinking": "x" * 42},
            {"type": "tool_use", "id": "A", "name": "Bash", "input": {"command": "ls -la"}},
        ]),
        _rad(iso("10:00:15"), "user", [
            {"type": "tool_result", "tool_use_id": "A", "content": "fire"},
        ]),
        # tidsstempel som millisekunder (int)
        _rad(ms("10:00:20"), "assistant", [
            {"type": "tool_use", "id": "B", "name": "Read", "input": {"file_path": "/tmp/x"}},
        ]),
        _rad(ms("10:00:50"), "user", [
            {"type": "tool_result", "tool_use_id": "B", "content": [{"type": "text", "text": "hei"}]},
        ]),
        # kall uten resultat
        _rad(iso("10:01:00"), "assistant", [
            {"type": "tool_use", "id": "C", "name": "Grep", "input": {"pattern": "x"}},
        ]),
        _rad(iso("10:02:00"), "assistant", [{"type": "text", "text": "ferdig"}]),
    ]
    fil = sti / "okt.jsonl"
    linjer = [json.dumps(r, ensure_ascii=False) for r in rader]
    linjer.insert(3, "")           # tom linje
    linjer.insert(4, "{ikke json")  # ødelagt linje
    fil.write_text("\n".join(linjer) + "\n", encoding="utf-8")
    return str(fil)


@pytest.fixture
def transkript(tmp_path):
    return skriv_transkript(tmp_path)


# --- parsing ---------------------------------------------------------------

def test_tid_takler_iso_og_millisekunder():
    assert _tid(iso("10:00:05")) == kl("10:00:05")
    assert _tid(ms("10:00:05")) == kl("10:00:05")
    assert _tid(None) is None
    assert _tid("ikke en dato") is None


def test_blokker_takler_streng_og_liste():
    assert _blokker({"content": "hei"}) == [{"type": "text", "text": "hei"}]
    assert _blokker({"content": [{"type": "text", "text": "a"}, "søppel"]}) == [{"type": "text", "text": "a"}]
    assert _blokker({}) == [] and _blokker(None) == []


def test_les_hendelser_hopper_over_linjer_uten_tidsstempel(transkript):
    hendelser = les_hendelser(transkript)
    arter = [h.art for h in hendelser]
    assert arter == ["text", "thinking", "tool_use", "tool_result",
                     "tool_use", "tool_result", "tool_use", "text"]
    assert hendelser == sorted(hendelser, key=lambda h: h.tid)


def test_par_verktoy_parer_paa_tool_use_id(transkript):
    kall = par_verktoy(les_hendelser(transkript))
    assert [k.uid for k in kall] == ["A", "B", "C"]
    assert [k.varighet for k in kall] == [10.0, 30.0, 0.0]
    assert kall[2].slutt is None  # uparet
    assert kall[1].storrelse > 0  # tool_result med liste-innhold


# --- måling ----------------------------------------------------------------

def test_maal_splitter_verktoytid_og_modelltid(transkript):
    r = maal(les_hendelser(transkript))
    assert (r["fra"], r["til"]) == ("10:00:00", "10:02:00")
    assert r["veggklokke_s"] == 120
    assert r["verktoykall"] == 3 and r["uparede_kall"] == 1
    assert r["verktoytid_s"] == 40 and r["verktoytid_pct"] == pytest.approx(33.3)
    assert r["modelltid_s"] == 80 and r["modelltid_pct"] == pytest.approx(66.7)
    assert r["verktoytid_s"] + r["modelltid_s"] == r["veggklokke_s"]


def test_fra_og_til_avgrenser_vinduet(transkript):
    r = maal(les_hendelser(transkript), fra="10:00:18", til="10:01:00")
    assert r["veggklokke_s"] == 42
    assert r["verktoykall"] == 2  # B og C; A startet før vinduet
    assert r["verktoytid_s"] == 30


def test_gap_klippes_mot_vindusstart(transkript):
    """Et gap skal aldri strekke seg inn i tida før --fra (split.py-feilen)."""
    r = maal(les_hendelser(transkript), fra="10:00:18")
    forste = r["tidslinje"][0]
    assert forste["tid"] == "10:00:20" and forste["gap_s"] == 2
    assert sum(rad["gap_s"] for rad in r["tidslinje"]) <= r["veggklokke_s"]


def test_tidslinje_har_navn_input_og_resultatstorrelse(transkript):
    rad = maal(les_hendelser(transkript))["tidslinje"][0]
    assert rad["verktoy"] == "Bash" and "ls -la" in rad["input"]
    assert rad["varighet_s"] == 10.0 and rad["resultat_tegn"] > 0


def test_maal_krever_hendelser():
    with pytest.raises(ValueError):
        maal([])


# --- faser -----------------------------------------------------------------

def test_fase_verktoytid_klippes_mot_fasegrensa(transkript):
    """Kall B (10:00:20–10:00:50) krysser fasegrensa 10:00:30 og skal telle 10 s."""
    faser = [{"navn": "P1", "fra": "10:00:00", "til": "10:00:30"},
             {"navn": "P2", "fra": "10:00:30", "til": "10:02:00"}]
    r = maal(les_hendelser(transkript), faser=faser)
    p1, p2 = r["faser"]
    assert p1["veggklokke_s"] == 30 and p1["verktoykall"] == 2 and p1["verktoytid_s"] == 10 + 10
    assert p2["veggklokke_s"] == 90 and p2["verktoykall"] == 1 and p2["verktoytid_s"] == 20
    for fase in r["faser"]:
        assert fase["verktoytid_s"] <= fase["veggklokke_s"]
    assert sum(f["verktoytid_s"] for f in r["faser"]) == r["verktoytid_s"]
    assert sum(f["verktoykall"] for f in r["faser"]) == r["verktoykall"]


def test_fase_uten_egne_kall_faar_klippet_verktoytid(transkript):
    """Fase som verken dekker vinduet eller starten på et kall: 10 s av B, ikke 30 s.

    Guard mot split.py-feilen som ikke hviler på at fasene fliselegger vinduet.
    """
    faser = [{"navn": "smal", "fra": "10:00:25", "til": "10:00:35"}]
    fase = maal(les_hendelser(transkript), faser=faser)["faser"][0]
    assert fase["veggklokke_s"] == 10
    assert fase["verktoykall"] == 0  # B startet før fasen
    assert fase["verktoytid_s"] == 10 <= fase["veggklokke_s"]


def test_overlapp():
    a, b = kl("10:00:00"), kl("10:00:30")
    assert _overlapp(a, b, kl("10:00:20"), kl("10:01:00")) == 10.0
    assert _overlapp(a, b, kl("10:01:00"), kl("10:02:00")) == 0.0


def test_klokkeslett_forankres_i_transkriptets_dato():
    """Økt over midnatt: et klokkeslett før første hendelse legges på neste døgn."""
    hendelser = [Hendelse(datetime(2026, 3, 4, 23, 50), "text"),
                 Hendelse(datetime(2026, 3, 5, 0, 20), "text")]
    r = maal(hendelser, fra="23:55:00", til="00:10:00")
    assert r["veggklokke_s"] == 15 * 60


# --- CLI -------------------------------------------------------------------

def test_cli_json(transkript, capsys):
    assert main([transkript, "--json"]) == 0
    r = json.loads(capsys.readouterr().out)
    assert r["veggklokke_s"] == 120 and r["verktoykall"] == 3


def test_cli_tekst_med_faser(transkript, tmp_path, capsys):
    fasefil = tmp_path / "faser.json"
    fasefil.write_text(json.dumps([{"navn": "P1", "fra": "10:00:00", "til": "10:01:00"}]), encoding="utf-8")
    assert main([transkript, "--fra", "10:00:00", "--faser", str(fasefil)]) == 0
    ut = capsys.readouterr().out
    assert "Verktøykall: 3" in ut and "modelltid 80 s" in ut
    assert "P1" in ut and "Faser" in ut
    assert "uparede kall uten resultat: 1" in ut


def test_parallelle_kall_gir_ikke_krasj(tmp_path):
    """To kall som overlapper kan gi verktøytid > veggklokke; det skal rapporteres, ikke krasje."""
    t0 = kl("10:00:00")
    rader = [
        _rad(t0.astimezone().isoformat(), "assistant", [
            {"type": "tool_use", "id": "A", "name": "Bash", "input": {}},
            {"type": "tool_use", "id": "B", "name": "Bash", "input": {}},
        ]),
        _rad((t0 + timedelta(seconds=20)).astimezone().isoformat(), "user",
             [{"type": "tool_result", "tool_use_id": "A", "content": "x"},
              {"type": "tool_result", "tool_use_id": "B", "content": "y"}]),
    ]
    fil = tmp_path / "parallell.jsonl"
    fil.write_text("\n".join(json.dumps(r) for r in rader) + "\n", encoding="utf-8")
    r = maal(les_hendelser(str(fil)))
    assert r["veggklokke_s"] == 20 and r["verktoytid_s"] == 40
    assert r["modelltid_s"] == -20  # rapporteres rått, ingen krasj
    assert "NB: verktøytid > veggklokke" in formater(r)

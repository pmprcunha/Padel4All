import json
from datetime import datetime
from pathlib import Path
from typing import Dict

from core.constants import TOURNAMENTS

TOURNAMENTS_DIR = Path("tournaments")
TOURNAMENTS_DIR.mkdir(exist_ok=True)

HISTORY_DIR = TOURNAMENTS_DIR / "history"
HISTORY_DIR.mkdir(exist_ok=True)


def _t_path(tid: str) -> Path:
    return TOURNAMENTS_DIR / f"{tid}.json"


def _snapshot_tournament(obj: Dict) -> None:
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    snap_path = HISTORY_DIR / f"{obj['id']}_{ts}.json"
    with snap_path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def save_tournament(obj: Dict) -> None:
    path = _t_path(obj["id"])
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    _snapshot_tournament(obj)


def event_exists(tid: str) -> bool:
    return _t_path(tid).exists()


def load_tournament(tid: str) -> Dict:
    p = _t_path(tid)
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _event_id_from(model_id: str, y: int, m: int, d: int) -> str:
    return f"{model_id}_{y:04d}{m:02d}{d:02d}"


def create_or_open_event_for_model(model_id: str, y: int, m: int, d: int) -> Dict:
    tid = _event_id_from(model_id, y, m, d)
    p = _t_path(tid)

    if p.exists():
        with p.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    tname = next((t["nome"] for t in TOURNAMENTS if t["id"] == model_id), model_id)

    obj = {
        "id": tid,
        "nome": f"{tname} — {y:04d}-{m:02d}-{d:02d}",
        "model": model_id,
        "tipo": None,
        "expected_pairs": None,
        "created": datetime.now().isoformat(),
        "date": {"year": y, "month": m, "day": d},
        "pairs": [],
        "courts": [],
        "rounds": [],
        "matches": [],
        "state": "setup",
        "notices": {"tipo": "", "duplas": "", "campos": "", "jornadas": ""},
    }

    save_tournament(obj)
    return obj

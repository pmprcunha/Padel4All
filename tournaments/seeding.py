from typing import Dict, List, Tuple
import pandas as pd

from data.ranking import compute_ranking


def pair_key(a: str, b: str) -> str:
    return f"{a.strip()} / {b.strip()}"


def players_points_map(expanded: pd.DataFrame) -> Dict[str, int]:
    if expanded.empty:
        return {}
    r = compute_ranking(expanded)
    return {row["Jogador(a)"]: int(row["Pontos Totais"]) for _, row in r.iterrows()}


def seed_pairs(pairs: List[Tuple[str, str]], ppoints: Dict[str, int]) -> List[Tuple[str, str, int]]:
    out = []
    for a, b in pairs:
        pts = ppoints.get(a, 0) + ppoints.get(b, 0)
        out.append((a, b, pts))
    out.sort(key=lambda x: (-x[2], x[0], x[1]))
    return out

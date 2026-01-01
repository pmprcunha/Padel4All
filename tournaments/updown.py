import random
from typing import Dict, List, Tuple

import pandas as pd

from core.constants import ALL_COURTS
from tournaments.scheduling import parse_score


def order_courts_desc(courts: List[str]) -> List[str]:
    priority = {name: i for i, name in enumerate(ALL_COURTS)}
    return sorted(courts, key=lambda c: priority.get(c, 9999))


def _rebuild_matches(t: Dict) -> None:
    t["matches"] = sum([r["games"] for r in t.get("rounds", [])], [])


def generate_updown_rounds(t: Dict) -> None:
    num_pairs = len(t.get("pairs", []))
    expected = int(t.get("expected_pairs") or 0)
    if expected <= 0 or num_pairs != expected:
        raise ValueError(f"UPDOWN: nº de duplas inválido. Esperado {expected}, recebeu {num_pairs}.")
    if num_pairs % 2 != 0:
        raise ValueError("UPDOWN: nº de duplas tem de ser par.")

    courts_raw = t.get("courts", [])
    courts_ord = order_courts_desc(courts_raw)
    if len(courts_ord) * 2 != num_pairs:
        raise ValueError("UPDOWN: nº de campos tem de ser exatamente nº_duplas/2.")

    pair_names = [p["name"] for p in t["pairs"]]
    random.shuffle(pair_names)

    round1_games = []
    for idx_court, court_name in enumerate(courts_ord):
        team_a = pair_names[2 * idx_court]
        team_b = pair_names[2 * idx_court + 1]
        round1_games.append(
            {"phase": "updown", "round": 1, "team_a": team_a, "team_b": team_b, "court": court_name, "score": ""}
        )

    t["rounds"] = [
        {"n": 1, "games": round1_games},
        {"n": 2, "games": []},
        {"n": 3, "games": []},
        {"n": 4, "games": []},
        {"n": 5, "games": []},
    ]
    _rebuild_matches(t)
    t["state"] = "scheduled"


def regenerate_updown_round1_distribution(t: Dict) -> Tuple[bool, str]:
    if t.get("tipo") != "UPDOWN":
        return False, "Este torneio não é formato UP & DOWN."

    rounds_map = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
    r1 = rounds_map.get(1)
    if not r1:
        return False, "Jornada 1 não existe."

    for g in r1.get("games", []):
        if g.get("score"):
            return False, "Já existem resultados na Jornada 1; não é possível baralhar."

    for rn in [2, 3, 4, 5]:
        rr = rounds_map.get(rn)
        if rr and rr.get("games"):
            return False, "Já existem jornadas seguintes geradas. Não é possível voltar a baralhar."

    num_pairs = len(t.get("pairs", []))
    expected = int(t.get("expected_pairs") or 0)
    if expected <= 0 or num_pairs != expected:
        return False, "Número de duplas não corresponde ao esperado."

    courts_ord = order_courts_desc(t.get("courts", []))
    if len(courts_ord) * 2 != num_pairs:
        return False, "Número de campos não corresponde a nº_duplas/2."

    pair_names = [p["name"] for p in t["pairs"]]
    random.shuffle(pair_names)

    new_games = []
    for idx_court, court_name in enumerate(courts_ord):
        team_a = pair_names[2 * idx_court]
        team_b = pair_names[2 * idx_court + 1]
        new_games.append(
            {"phase": "updown", "round": 1, "team_a": team_a, "team_b": team_b, "court": court_name, "score": ""}
        )

    r1["games"] = new_games
    for rn in [2, 3, 4, 5]:
        if rn in rounds_map:
            rounds_map[rn]["games"] = []

    t["rounds"] = [rounds_map[rn] for rn in sorted(rounds_map.keys())]
    _rebuild_matches(t)
    return True, "Nova configuração inicial gerada com sucesso."


def updown_build_next_round(t: Dict, current_round_num: int) -> bool:
    if t.get("tipo") != "UPDOWN":
        return False

    rounds_map = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
    r_curr = rounds_map.get(current_round_num)
    next_round_num = current_round_num + 1
    if not r_curr or next_round_num > 5:
        return False

    courts_ord = order_courts_desc(t.get("courts", []))
    court_priority = {c: i for i, c in enumerate(courts_ord)}

    games_curr = sorted(r_curr.get("games", []), key=lambda g: court_priority.get(g.get("court", ""), 9999))

    results_by_idx = []
    for gm in games_curr:
        score_txt = gm.get("score", "").strip()
        jg, jp = parse_score(score_txt)
        team_a = gm.get("team_a", "")
        team_b = gm.get("team_b", "")

        if not score_txt or jg == jp:
            return False

        winner = team_a if jg > jp else team_b
        loser = team_b if jg > jp else team_a

        idx = court_priority.get(gm.get("court", ""), None)
        if idx is None:
            return False

        results_by_idx.append((idx, winner, loser))

    results_by_idx.sort(key=lambda x: x[0])
    num_courts = len(courts_ord)
    last_idx = num_courts - 1

    dest = [[] for _ in range(num_courts)]
    for idx, winner, loser in results_by_idx:
        up_idx = max(idx - 1, 0)
        down_idx = min(idx + 1, last_idx)
        dest[up_idx].append(winner)
        dest[down_idx].append(loser)

    for lst in dest:
        if len(lst) != 2:
            return False

    next_games = []
    for court_idx, court_name in enumerate(courts_ord):
        team_a, team_b = dest[court_idx]
        next_games.append(
            {"phase": "updown", "round": next_round_num, "team_a": team_a, "team_b": team_b, "court": court_name, "score": ""}
        )

    if next_round_num in rounds_map:
        rounds_map[next_round_num]["games"] = next_games
    else:
        rounds_map[next_round_num] = {"n": next_round_num, "games": next_games}

    t["rounds"] = [rounds_map[k] for k in sorted(rounds_map.keys())]
    _rebuild_matches(t)
    return True


def compute_final_classification_from_updown(t: Dict) -> pd.DataFrame:
    if t.get("tipo") != "UPDOWN":
        return pd.DataFrame(columns=["Pos", "Dupla / Equipa"])

    rounds_map = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
    r5 = rounds_map.get(5)
    if not r5:
        return pd.DataFrame(columns=["Pos", "Dupla / Equipa"])

    games_round5 = r5.get("games", [])
    if not games_round5:
        return pd.DataFrame(columns=["Pos", "Dupla / Equipa"])

    court_order = t.get("courts", [])
    court_priority = {court_name: i for i, court_name in enumerate(court_order)}

    games_sorted = sorted(games_round5, key=lambda g: court_priority.get(g.get("court", ""), 9999))

    placements = []
    next_pos = 1

    for gm in games_sorted:
        team_a = gm.get("team_a", "")
        team_b = gm.get("team_b", "")
        score_txt = gm.get("score", "").strip()
        jg, jp = parse_score(score_txt)

        if not score_txt or jg == jp:
            winner = f"Vencedor {team_a} vs {team_b}"
            loser = f"Perdedor {team_a} vs {team_b}"
        else:
            winner, loser = (team_a, team_b) if jg > jp else (team_b, team_a)

        placements.append({"Pos": next_pos, "Dupla / Equipa": winner})
        placements.append({"Pos": next_pos + 1, "Dupla / Equipa": loser})
        next_pos += 2

    return pd.DataFrame(placements, columns=["Pos", "Dupla / Equipa"])

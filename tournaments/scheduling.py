import random
from typing import Dict, List, Tuple

import pandas as pd


def round_robin_pairs(n: int) -> List[List[Tuple[int, int]]]:
    if n % 2 != 0:
        raise ValueError("Número de equipas deve ser par para round-robin")

    teams = list(range(n))
    half = n // 2
    jornadas = []

    for _ in range(n - 1):
        left = teams[:half]
        right = teams[half:][::-1]
        round_pairs = [(left[i], right[i]) for i in range(half)]
        jornadas.append(round_pairs)
        teams = [teams[0]] + [teams[-1]] + teams[1:-1]

    return jornadas


def group_distribution(
    seeded_pairs: List[Tuple[str, str, int]],
    groups: int,
    size: int,
    mode: str,
) -> Dict[str, List[int]]:
    N = len(seeded_pairs)
    assert groups * size == N, "Tamanho total não corresponde"

    idxs = list(range(N))
    by_group: Dict[str, List[int]] = {chr(65 + i): [] for i in range(groups)}

    if mode == "G2x4":
        by_group["A"].extend([0, 2])
        by_group["B"].extend([1, 3])
        remaining = idxs[4:]
        random.shuffle(remaining)
        for k, ix in enumerate(remaining):
            g = "A" if len(by_group["A"]) < size and (k % 2 == 0) else "B"
            if len(by_group[g]) >= size:
                g = "A" if g == "B" else "B"
            by_group[g].append(ix)

    elif mode == "G3x4":
        base = {"A": [0, 3], "B": [1, 4], "C": [2, 5]}
        remaining = idxs[6:]
        random.shuffle(remaining)
        by_group.update({k: v[:] for k, v in base.items()})
        cycle = ["A", "B", "C"]
        i = 0
        for ix in remaining:
            g = cycle[i % 3]
            while len(by_group[g]) >= size:
                i += 1
                g = cycle[i % 3]
            by_group[g].append(ix)
            i += 1

    elif mode == "G4x4":
        order = list(range(N))
        gnames = [chr(65 + i) for i in range(4)]
        direction = 1
        pos = 0
        for ix in order:
            g = gnames[pos]
            by_group[g].append(ix)
            if (len(by_group[g]) % size) == 0:
                if direction == 1:
                    pos += 1
                    if pos >= 3:
                        direction = -1
                else:
                    pos -= 1
                    if pos <= 0:
                        direction = 1
    else:
        raise ValueError("Modo de grupos desconhecido")

    for g, lst in by_group.items():
        if len(lst) != size:
            raise ValueError(f"Grupo {g} tamanho incorreto: {len(lst)} != {size}")

    return by_group


def parse_score(score: str) -> Tuple[int, int]:
    try:
        a, b = score.strip().split("-")
        return int(a), int(b)
    except Exception:
        return 0, 0


def update_table(
    table: Dict[str, Dict],
    team_a: str,
    team_b: str,
    score: str,
    cd_map: Dict[Tuple[str, str], int],
):
    jg, jp = parse_score(score)

    def ensure_team(team: str):
        if team not in table:
            table[team] = {
                "J": 0, "P": 0, "V": 0, "E": 0, "D": 0,
                "JG": 0, "JP": 0, "Dif": 0, "CD": 0,
            }

    ensure_team(team_a)
    ensure_team(team_b)

    table[team_a]["J"] += 1
    table[team_b]["J"] += 1

    table[team_a]["JG"] += jg
    table[team_a]["JP"] += jp
    table[team_b]["JG"] += jp
    table[team_b]["JP"] += jg

    table[team_a]["Dif"] = table[team_a]["JG"] - table[team_a]["JP"]
    table[team_b]["Dif"] = table[team_b]["JG"] - table[team_b]["JP"]

    if jg > jp:
        table[team_a]["V"] += 1
        table[team_b]["D"] += 1
        table[team_a]["P"] += 3
        cd_map[(team_a, team_b)] = 1
        cd_map[(team_b, team_a)] = 0
    elif jp > jg:
        table[team_b]["V"] += 1
        table[team_a]["D"] += 1
        table[team_b]["P"] += 3
        cd_map[(team_b, team_a)] = 1
        cd_map[(team_a, team_b)] = 0
    else:
        table[team_a]["E"] += 1
        table[team_b]["E"] += 1
        table[team_a]["P"] += 1
        table[team_b]["P"] += 1
        cd_map[(team_a, team_b)] = 0
        cd_map[(team_b, team_a)] = 0


def ranking_dataframe_from_results(matches: List[Dict]) -> pd.DataFrame:
    table: Dict[str, Dict] = {}
    cd_map: Dict[Tuple[str, str], int] = {}

    for m in matches:
        if not m.get("score"):
            continue
        update_table(table, m["team_a"], m["team_b"], m["score"], cd_map)

    if not table:
        return pd.DataFrame(
            columns=["Pos","Dupla / Equipa","J","P","V","E","D","JG","JP","Dif","CD"]
        )

    def sort_key(team):
        P = table[team]["P"]
        Dif = table[team]["Dif"]
        return (-P, -Dif, team)

    prelim = sorted(table.keys(), key=sort_key)

    final_order = []
    i = 0
    while i < len(prelim):
        j = i + 1
        Pi = table[prelim[i]]["P"]
        Difi = table[prelim[i]]["Dif"]
        while j < len(prelim) and table[prelim[j]]["P"] == Pi and table[prelim[j]]["Dif"] == Difi:
            j += 1
        block = prelim[i:j]
        if len(block) > 1:
            block = sorted(
                block,
                key=lambda t: -sum(cd_map.get((t, u), 0) for u in block if u != t),
            )
        final_order.extend(block)
        i = j

    rows = []
    for pos, team in enumerate(final_order, start=1):
        d = table[team]
        rows.append(
            {
                "Pos": pos,
                "Dupla / Equipa": team,
                "J": d["J"],
                "P": d["P"],
                "V": d["V"],
                "E": d["E"],
                "D": d["D"],
                "JG": d["JG"],
                "JP": d["JP"],
                "Dif": d["Dif"],
                "CD": sum(cd_map.get((team, u), 0) for u in final_order if u != team),
            }
        )
    return pd.DataFrame(rows)


def assign_courts(jogos: List[Tuple[int, int]], courts: List[str]) -> List[Tuple[int, int, str]]:
    if len(jogos) > len(courts):
        raise ValueError("Número de jogos excede número de campos selecionados")
    shuffled = jogos[:]
    random.shuffle(shuffled)
    return [(a, b, courts[i]) for i, (a, b) in enumerate(shuffled)]

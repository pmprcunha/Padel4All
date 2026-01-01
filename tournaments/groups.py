import re
from typing import Dict, List, Tuple

import pandas as pd

from core.constants import get_data_file_for_model
from data.ranking import load_data, expand_results, split_team
from tournaments.seeding import players_points_map
from tournaments.scheduling import parse_score, ranking_dataframe_from_results


def _rebuild_matches(t: Dict) -> None:
    t["matches"] = sum([r["games"] for r in t.get("rounds", [])], [])


def _extract_groups_from_rounds(t: Dict) -> Dict[str, List[str]]:
    groups: Dict[str, List[str]] = {}
    for r in t.get("rounds", []):
        for m in r.get("games", []):
            if m.get("phase") == "groups":
                g = m.get("group", "?")
                groups.setdefault(g, [])
                for tm in (m["team_a"], m["team_b"]):
                    if tm not in groups[g]:
                        groups[g].append(tm)
    return dict(sorted(groups.items()))


def _group_matches_until_round(t: Dict, group: str, max_group_round: int = 3) -> List[Dict]:
    out = []
    for r in t.get("rounds", []):
        for m in r.get("games", []):
            if m.get("phase") == "groups" and m.get("group") == group and int(m.get("round", 0)) <= max_group_round:
                out.append(m)
    return out


def compute_group_tables_live(t: Dict) -> Dict[str, pd.DataFrame]:
    data_file = get_data_file_for_model(t.get("model", ""))
    df_raw = load_data(data_file)
    exp_df = expand_results(df_raw)
    pmap_now = players_points_map(exp_df)

    groups = _extract_groups_from_rounds(t)
    tables: Dict[str, pd.DataFrame] = {}

    def _team_rank(team_name: str) -> int:
        a, b = split_team(team_name)
        return int(pmap_now.get(a, 0) + pmap_now.get(b, 0))

    for g, teams in groups.items():
        matches = _group_matches_until_round(t, g, max_group_round=3)

        if matches:
            df = ranking_dataframe_from_results(matches).copy()
            rank_vals = df["Dupla / Equipa"].apply(_team_rank).astype(int)
            df.insert(1, "Rank", rank_vals)

            P_counts = df["P"].value_counts()
            tied_P = {P for P, cnt in P_counts.items() if cnt > 1}

            cd_list: List[str] = []
            for row in df.itertuples(index=False):
                row_P = int(getattr(row, "P"))
                if row_P in tied_P:
                    cd_list.append(str(getattr(row, "CD")))
                else:
                    cd_list.append("")
            df = df.drop(columns=["CD"])
            df["CD"] = pd.Series(cd_list, index=df.index, dtype="string")

            df = df[
                ["Pos","Rank","Dupla / Equipa","J","P","V","E","D","JG","JP","Dif","CD"]
            ]
        else:
            seeded = sorted(teams, key=lambda nm: -_team_rank(nm))
            rows = []
            for i, name in enumerate(seeded, start=1):
                rows.append(
                    {"Pos": i, "Rank": _team_rank(name), "Dupla / Equipa": name,
                     "J": 0,"P": 0,"V": 0,"E": 0,"D": 0,"JG": 0,"JP": 0,"Dif": 0,"CD": ""}
                )
            df = pd.DataFrame(
                rows,
                columns=["Pos","Rank","Dupla / Equipa","J","P","V","E","D","JG","JP","Dif","CD"],
            )
            df["CD"] = df["CD"].astype("string")

        tables[g] = df

    return tables


def _filter_rank_block(tables: Dict[str, pd.DataFrame], groups: List[str], teams_list: List[str]) -> List[str]:
    items = []
    for team in teams_list:
        for gx in groups:
            df = tables[gx]
            row = df[df["Dupla / Equipa"] == team]
            if not row.empty:
                items.append((team, int(row["P"].iloc[0]), int(row["Dif"].iloc[0])))
                break
    items.sort(key=lambda x: (-x[1], -x[2], x[0]))
    return [x[0] for x in items]


def generate_finals_from_pots_and_replace(t: Dict) -> Tuple[bool, str]:
    tables = compute_group_tables_live(t)
    if not tables:
        return False, "Não existem grupos para este evento."

    courts = t.get("courts", [])
    if not courts:
        return False, "Sem campos definidos."

    groups = sorted(tables.keys())
    nG = len(groups)
    if nG not in (2, 3, 4):
        return False, "Número de grupos não suportado para cruzamentos (esperado: 2, 3 ou 4)."

    pos_map: Dict[str, List[str]] = {}
    for g in groups:
        df = tables[g].sort_values("Pos")
        pos_map[g] = list(df["Dupla / Equipa"].values)

    round4_pairs: List[Tuple[str, str]] = []

    if nG == 2:
        A, B = groups
        A1, A2, A3, A4 = pos_map[A][:4]
        B1, B2, B3, B4 = pos_map[B][:4]
        round4_pairs += [(A1, B2), (B1, A2), (A3, B4), (B3, A4)]

    elif nG == 3:
        A, B, C = groups
        A1, A2, A3, A4 = pos_map[A][:4]
        B1, B2, B3, B4 = pos_map[B][:4]
        C1, C2, C3, C4 = pos_map[C][:4]

        seconds_sorted = _filter_rank_block(tables, groups, [A2, B2, C2])
        thirds_sorted = _filter_rank_block(tables, groups, [A3, B3, C3])
        fourths_sorted = _filter_rank_block(tables, groups, [A4, B4, C4])

        melhor2, segundo2, pior2 = seconds_sorted
        melhor3, segundo3, pior3 = thirds_sorted
        melhor4, segundo4, pior4 = fourths_sorted

        round4_pairs += [(A1, melhor2), (B1, C1)]
        round4_pairs += [(segundo2, segundo3), (pior2, melhor3)]
        round4_pairs += [(pior3, pior4), (melhor4, segundo4)]

    elif nG == 4:
        A, B, C, D = groups
        for pos in range(4):
            round4_pairs += [
                (pos_map[A][pos], pos_map[D][pos]),
                (pos_map[B][pos], pos_map[C][pos]),
            ]

    group_rr_len = 3
    r4_num = group_rr_len + 1
    r5_num = group_rr_len + 2

    round4_games = []
    for i, (A_team, B_team) in enumerate(round4_pairs):
        court = courts[i % len(courts)]
        round4_games.append(
            {"phase": "finals", "round": r4_num, "team_a": A_team, "team_b": B_team, "court": court, "score": ""}
        )

    round5_games = []
    for i in range(0, len(round4_games), 2):
        court_w = courts[(len(round5_games)) % len(courts)]
        round5_games.append(
            {
                "phase": "finals",
                "round": r5_num,
                "team_a": f"Vencedor R{r4_num}-{i+1}",
                "team_b": f"Vencedor R{r4_num}-{i+2}",
                "court": court_w,
                "score": "",
            }
        )
        court_l = courts[(len(round5_games)) % len(courts)]
        round5_games.append(
            {
                "phase": "finals",
                "round": r5_num,
                "team_a": f"Perdedor R{r4_num}-{i+1}",
                "team_b": f"Perdedor R{r4_num}-{i+2}",
                "court": court_l,
                "score": "",
            }
        )

    rounds_new = []
    for r in t.get("rounds", []):
        n = int(r.get("n", 0))
        if n <= group_rr_len:
            rounds_new.append(r)
    rounds_new.append({"n": r4_num, "games": round4_games})
    rounds_new.append({"n": r5_num, "games": round5_games})

    t["rounds"] = rounds_new
    _rebuild_matches(t)
    return True, "Potes (Jornadas 4 e 5) gerados/atualizados com base na classificação."


def recalculate_round5_from_round4(t: Dict) -> bool:
    rounds_map = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
    r4 = rounds_map.get(4)
    if not r4:
        return False

    r4_games = r4.get("games", [])
    if not r4_games or len(r4_games) < 2:
        return False

    courts_all = t.get("courts", []) or ["Campo ?"]

    def _decide_winner_loser(game: Dict, label_fallback: str) -> Tuple[str, str]:
        score_txt = game.get("score", "").strip()
        jg, jp = parse_score(score_txt)
        team_a = game.get("team_a", "A")
        team_b = game.get("team_b", "B")

        if not score_txt or jg == jp:
            return (f"Vencedor {label_fallback}", f"Perdedor {label_fallback}")

        return (team_a, team_b) if jg > jp else (team_b, team_a)

    new_r5_games: List[Dict] = []
    court_idx = 0

    for block_index in range(0, len(r4_games), 2):
        if block_index + 1 >= len(r4_games):
            break

        game1 = r4_games[block_index]
        game2 = r4_games[block_index + 1]

        w1, l1 = _decide_winner_loser(game1, f"R4-{block_index+1}")
        w2, l2 = _decide_winner_loser(game2, f"R4-{block_index+2}")

        base_place = block_index // 2 * 4 + 1
        winners_label = f"{base_place}º e {base_place+1}º lugar"
        losers_label = f"{base_place+2}º e {base_place+3}º lugar"

        court_w = courts_all[court_idx % len(courts_all)]
        court_idx += 1
        new_r5_games.append(
            {"phase": "finals", "round": 5, "placement": winners_label, "team_a": w1, "team_b": w2, "court": court_w, "score": ""}
        )

        court_l = courts_all[court_idx % len(courts_all)]
        court_idx += 1
        new_r5_games.append(
            {"phase": "finals", "round": 5, "placement": losers_label, "team_a": l1, "team_b": l2, "court": court_l, "score": ""}
        )

    if not new_r5_games:
        return False

    updated_rounds: List[Dict] = []
    seen_5 = False
    for r in t.get("rounds", []):
        n_val = int(r.get("n", 0))
        if n_val == 5:
            updated_rounds.append({"n": 5, "games": new_r5_games})
            seen_5 = True
        else:
            updated_rounds.append(r)

    if not seen_5:
        updated_rounds.append({"n": 5, "games": new_r5_games})

    updated_rounds = sorted(updated_rounds, key=lambda R: int(R.get("n", 0)))
    t["rounds"] = updated_rounds
    _rebuild_matches(t)
    return True


def compute_final_classification_from_round5(t: Dict) -> pd.DataFrame:
    rounds_map = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
    r5 = rounds_map.get(5)
    if not r5:
        return pd.DataFrame(columns=["Pos", "Dupla / Equipa"])

    games = r5.get("games", [])
    if not games:
        return pd.DataFrame(columns=["Pos", "Dupla / Equipa"])

    placements = []
    for g in games:
        placement_label = g.get("placement", "")
        m = re.search(r"(\d+)", placement_label or "")
        if not m:
            continue
        base_pos = int(m.group(1))
        team_a = g.get("team_a", "")
        team_b = g.get("team_b", "")
        score_txt = g.get("score", "").strip()
        jg, jp = parse_score(score_txt)

        if not score_txt or jg == jp:
            winner = f"Vencedor {placement_label}".strip()
            loser = f"Perdedor {placement_label}".strip()
        else:
            winner, loser = (team_a, team_b) if jg > jp else (team_b, team_a)

        placements.append((base_pos, winner))
        placements.append((base_pos + 1, loser))

    placements.sort(key=lambda x: x[0])
    rows = [{"Pos": pos, "Dupla / Equipa": team} for pos, team in placements]
    return pd.DataFrame(rows, columns=["Pos", "Dupla / Equipa"])

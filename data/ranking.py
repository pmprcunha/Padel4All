from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
import streamlit as st

from core.constants import MONTH_INDEX, MONTH_ORDER, POINTS_SYSTEM


@st.cache_data(show_spinner=False)
def load_data(file_path: Path) -> pd.DataFrame:
    if not file_path.exists():
        return pd.DataFrame(columns=["Year", "Month", "Day", "Position", "Team"])

    df = pd.read_csv(
        file_path,
        dtype={
            "Year": "Int64",
            "Month": "string",
            "Day": "Int64",
            "Position": "Int64",
            "Team": "string",
        },
    )
    df = df.dropna(subset=["Year", "Month", "Day", "Position", "Team"])
    df["Month"] = df["Month"].str.strip()
    df["Team"] = (
        df["Team"]
        .str.replace(r"\s*/\s*", " / ", regex=True)
        .str.strip()
    )
    df["Team"] = df["Team"].apply(lambda s: " / ".join([p.strip() for p in s.split("/")]))
    return df


def split_team(team: str) -> Tuple[str, str]:
    parts = [p.strip() for p in str(team).split("/")]
    if len(parts) == 2:
        return parts[0], parts[1]
    return str(team).strip(), ""


@st.cache_data(show_spinner=False)
def expand_results(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(
            columns=["Year","Month","Day","Data","Team","Player","Position","Points"]
        )

    reg = []
    for (year, month, day), group in df.groupby(["Year", "Month", "Day"], dropna=True):
        n_teams = len(group)
        pts_list = POINTS_SYSTEM.get(int(n_teams))

        try:
            mo = MONTH_INDEX.get(str(month), 0)
            d_obj = date(int(year), int(mo) + 1, int(day)) if mo in range(12) else None
            data_fmt = d_obj.isoformat() if d_obj else f"{int(year)}-{str(month)}-{int(day):02d}"
        except Exception:
            data_fmt = f"{int(year)}-{str(month)}-{int(day):02d}"

        for _, row in group.iterrows():
            pos = int(row["Position"])
            a, b = split_team(row["Team"])
            pts = pts_list[pos - 1] if pts_list and 1 <= pos <= len(pts_list) else 0

            for player in [a, b]:
                if not player:
                    continue
                reg.append(
                    {
                        "Year": int(year),
                        "Month": str(month),
                        "Day": int(day),
                        "Data": data_fmt,
                        "Team": str(row["Team"]),
                        "Player": str(player),
                        "Position": pos,
                        "Points": int(pts),
                    }
                )

    out = pd.DataFrame(reg)
    if not out.empty:
        out["MonthOrder"] = out["Month"].map(MONTH_INDEX).fillna(99).astype(int)
        out = (
            out.sort_values(
                by=["Year", "MonthOrder", "Day", "Position"],
                ascending=[False, False, False, True],
            )
            .drop(columns=["MonthOrder"])
        )
    return out


@st.cache_data(show_spinner=False)
def compute_ranking(expanded: pd.DataFrame) -> pd.DataFrame:
    if expanded.empty:
        return pd.DataFrame(columns=["Jogador(a)", "Pontos Totais", "Participações", "Média de Pontos"])

    agg = (
        expanded.groupby("Player", dropna=True)
        .agg(
            Pontos_Totais=("Points", "sum"),
            Participações=("Day", "count"),
            Média=("Points", "mean"),
        )
        .reset_index()
        .rename(
            columns={
                "Player": "Jogador(a)",
                "Pontos_Totais": "Pontos Totais",
                "Média": "Média de Pontos",
            }
        )
    )
    agg["Média de Pontos"] = agg["Média de Pontos"].round(2)
    agg = (
        agg.sort_values(
            by=["Pontos Totais", "Média de Pontos", "Participações", "Jogador(a)"],
            ascending=[False, False, False, True],
        )
        .reset_index(drop=True)
    )
    agg.index = agg.index + 1
    return agg


@st.cache_data(show_spinner=False)
def players_index(expanded: pd.DataFrame) -> pd.DataFrame:
    if expanded.empty:
        return pd.DataFrame(columns=["Jogador(a)","Pontos Totais","Participações","Média de Pontos","Parceiras(os) frequentes"])

    expanded = expanded.copy()
    expanded["Player"] = expanded["Player"].astype("string")
    expanded["Team"] = expanded["Team"].astype("string")

    rows = []
    for ((player, _y, _m, _d, team, _pos, _pts), _grp) in expanded.groupby(
        ["Player", "Year", "Month", "Day", "Team", "Position", "Points"],
        dropna=True,
    ):
        a, b = split_team(team)
        partner = b if player == a else a
        rows.append({"Jogador(a)": str(player), "Parceiro(a)": str(partner)})

    partners_df = pd.DataFrame(rows)

    if partners_df.empty:
        tops = pd.DataFrame(columns=["Jogador(a)", "Parceiras(os) frequentes"])
    else:
        TOP_N = 5
        counts = (
            partners_df.groupby(["Jogador(a)", "Parceiro(a)"])
            .size()
            .reset_index(name="Contagem")
            .sort_values(["Jogador(a)", "Contagem", "Parceiro(a)"], ascending=[True, False, True])
        )

        def _fmt(g: pd.DataFrame) -> str:
            top = g.head(TOP_N)
            shown = ", ".join([f"{r['Parceiro(a)']} ({int(r['Contagem'])})" for _, r in top.iterrows()])
            total = int(g["Contagem"].sum())
            top_sum = int(top["Contagem"].sum())
            rest = total - top_sum
            if rest > 0:
                return f"{shown}, Outros ({rest})"
            return shown

        tops = (
            counts.groupby("Jogador(a)", group_keys=False)
            .apply(_fmt)
            .reset_index(name="Parceiras(os) frequentes")
        )

    r = compute_ranking(expanded).copy()
    idx = r.merge(tops, on="Jogador(a)", how="left").fillna({"Parceiras(os) frequentes": ""})
    idx.index = range(1, len(idx) + 1)
    return idx


def _all_event_dates(expanded: pd.DataFrame) -> List[Tuple[int, str, int]]:
    if expanded.empty:
        return []

    rows = []
    for (y, m, d) in expanded[["Year", "Month", "Day"]].drop_duplicates().itertuples(index=False):
        month_idx = MONTH_INDEX.get(str(m), 99)
        rows.append((int(y), int(month_idx), int(d)))

    rows = sorted(set(rows), key=lambda x: (x[0], x[1], x[2]))

    out: List[Tuple[int, str, int]] = []
    for y, mi, d in rows:
        month_name = MONTH_ORDER[mi] if 0 <= mi < len(MONTH_ORDER) else str(mi)
        out.append((y, month_name, d))
    return out


def _filter_until_dates(expanded: pd.DataFrame, dates_subset: List[Tuple[int, str, int]]) -> pd.DataFrame:
    if expanded.empty or not dates_subset:
        return pd.DataFrame(columns=expanded.columns)

    mask = pd.Series([False] * len(expanded))
    for (y, m, d) in dates_subset:
        mask = mask | ((expanded["Year"] == y) & (expanded["Month"] == m) & (expanded["Day"] == d))
    return expanded[mask].copy()


def compute_ranking_with_momentum(expanded: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    current_full = compute_ranking(expanded).copy()
    if current_full.empty:
        empty_cols = ["Pos","Var","Jogador(a)","Pontos Totais","Participações","Média de Pontos"]
        return current_full.head(3), pd.DataFrame(columns=empty_cols)

    dates_all = _all_event_dates(expanded)
    current_full["__PosAtual__"] = range(1, len(current_full) + 1)

    if len(dates_all) >= 2:
        prev_dates = dates_all[:-1]
        prev_df = _filter_until_dates(expanded, prev_dates)
        prev_ranking = compute_ranking(prev_df)
        prev_pos_map = {row["Jogador(a)"]: int(idx) for idx, row in prev_ranking.iterrows()}
    else:
        prev_pos_map = {}

    pos_list = []
    delta_list = []

    for _, row in current_full.iterrows():
        nome = row["Jogador(a)"]
        pos_now = int(row["__PosAtual__"])
        pos_prev = prev_pos_map.get(nome)

        pos_list.append(pos_now)

        if pos_prev is None:
            delta_list.append("")
        else:
            diff = pos_prev - pos_now
            if diff > 0:
                delta_list.append(f"▲ +{diff}")
            elif diff < 0:
                delta_list.append(f"▼ {diff}")
            else:
                delta_list.append("")

    current_full["Pos"] = pos_list
    current_full["Var"] = delta_list

    top3 = current_full.head(3).drop(columns=["__PosAtual__", "Pos", "Var"], errors="ignore")

    resto = current_full.iloc[3:].copy()
    if not resto.empty:
        resto = resto[["Pos","Var","Jogador(a)","Pontos Totais","Participações","Média de Pontos"]]

    if "__PosAtual__" in current_full.columns:
        del current_full["__PosAtual__"]

    return top3, resto

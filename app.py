import os
import sys
import json
import csv
import re
import random
from pathlib import Path
from typing import List, Dict, Tuple
from datetime import date, datetime


# =========================================================
# IMPORTS DA APP
# =========================================================
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


# =========================================================
# CONFIGURAÇÃO BASE
# =========================================================
st.set_page_config(
    page_title="Gestão de torneios e eventos",
    page_icon="▣",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Código do organizador (podes alterar aqui ou via env var PADEL4ALL_ADMIN_PASSWORD)
ADMIN_PASSWORD = os.environ.get("PADEL4ALL_ADMIN_PASSWORD", "padel4all")

# ficheiros históricos por modelo
MODEL_DATA_FILES = {
    "F5.2_20SEX": Path("tournament_results_F5.2.csv"),
    "M5.2_1830DOM": Path("tournament_results_M5.2.csv"),
    # adiciona aqui mais modelos/ficheiros no futuro
}

def get_data_file_for_model(model_id: str) -> Path:
    """
    Devolve o Path do CSV histórico correspondente a um dado modelo.
    Se não existir mapeamento, devolve um Path 'vazio' (não existente).
    """
    p = MODEL_DATA_FILES.get(model_id)
    return p if p is not None else Path("__no_data__.csv")

# diretório para torneios/eventos
TOURNAMENTS_DIR = Path("tournaments")
TOURNAMENTS_DIR.mkdir(exist_ok=True)

# diretório de histórico (snapshots de cada save)
HISTORY_DIR = TOURNAMENTS_DIR / "history"
HISTORY_DIR.mkdir(exist_ok=True)

# courts disponíveis
ALL_COURTS = [
    "Campo Central",
    "Campo 11",
    "Campo 10",
    "Campo 9",
    "Campo 8",
    "Campo 7",
    "Campo 6",
    "Campo 5",
    "Campo 4",
    "Campo 3",
    "Campo 2",
    "Campo 1",
]

# tipos de torneio suportados
TOURNEY_TYPES = {
    "LIGA6": {
        "label": "Liga Clássica (6 Equipas)",
        "teams": 6,
        "groups": None,
        "required_courts": 3,
        "desc": "Todos contra todos; 5 jornadas; 3 jogos/jornada",
    },
    "G2x4": {
        "label": "Fase de Grupos: 2 Grupos de 4",
        "teams": 8,
        "groups": (2, 4),
        "required_courts": 4,
        "desc": "2 grupos; 3 jornadas; meias-finais cruzadas; total 5 jogos",
    },
    "G3x4": {
        "label": "Fase de Grupos: 3 Grupos de 4",
        "teams": 12,
        "groups": (3, 4),
        "required_courts": 6,
        "desc": "3 grupos; 3 jornadas; potes finais; total 5 jogos",
    },
    "G4x4": {
        "label": "Fase de Grupos: 4 Grupos de 4",
        "teams": 16,
        "groups": (4, 4),
        "required_courts": 8,
        "desc": "4 grupos; 3 jornadas; potes finais; total 5 jogos",
    },
    "UPDOWN": {
        "label": "Torneio Americano (Up & Down)",
        "teams": None,
        "groups": None,
        "required_courts": None,
        "desc": "Formato dinâmico por campos, com subidas/descidas",
    },
}

# torneios "modelos" base
TOURNAMENTS = [
    {
        "id": "F5.2_20SEX",
        "nome": "PADEL4ALL EUL F5.2 / 6ª - Feira / 20h",
        "genero": "Feminino",
    },
    {
        "id": "M5.2_1830DOM",
        "nome": "PADEL4ALL EUL M5.2 / Dom / 18h30",
        "genero": "Masculino",
    },
    {
        "id": "M3.2_20DOM",
        "nome": "PADEL4ALL EUL M3.2 / Dom / 20h",
        "genero": "Masculino",
    },
]

# sistema de pontos por nº de equipas (expandido com 10 e 14)
POINTS_SYSTEM: Dict[int, List[int]] = {
    6:  [8, 6, 4, 3, 2, 1],
    8:  [11, 9, 7, 6, 4, 3, 2, 1],
    10: [14, 12, 10, 9, 7, 6, 5, 4, 2, 1],
    12: [16, 14, 12, 11, 9, 8, 7, 6, 4, 3, 2, 1],
    14: [19, 17, 15, 14, 12, 11, 10, 9, 7, 6, 5, 4, 2, 1],
    16: [21, 19, 17, 16, 14, 13, 12, 11, 9, 8, 7, 6, 4, 3, 2, 1],
}

MONTH_ORDER = [
    "Janeiro",
    "Fevereiro",
    "Março",
    "Abril",
    "Maio",
    "Junho",
    "Julho",
    "Agosto",
    "Setembro",
    "Outubro",
    "Novembro",
    "Dezembro",
]
MONTH_INDEX = {m: i for i, m in enumerate(MONTH_ORDER)}
MONTH_ABBR_PT = [
    "JAN",
    "FEV",
    "MAR",
    "ABR",
    "MAI",
    "JUN",
    "JUL",
    "AGO",
    "SET",
    "OUT",
    "NOV",
    "DEZ",
]

MODEL_DEFAULT_TYPE = {
    "F5.2_20SEX": "LIGA6",
    "M5.2_1830DOM": "LIGA6",
    "M3.2_20DOM": "LIGA6",
}

# =========================================================
# HELPERS DE ADMIN (ORGANIZADOR)
# =========================================================
def is_admin() -> bool:
    """Verifica se a sessão atual está autenticada como organizador."""
    return bool(st.session_state.get("is_admin", False))


def admin_login_sidebar() -> bool:
    """
    UI da área do organizador no sidebar.
    Retorna True se a sessão for admin.
    """
    if is_admin():
        st.success("Sessão de organizador ativa.")
        return True

    pwd = st.text_input(
        "Código de organizador",
        type="password",
        key="admin_pwd_sidebar",
        help="Área reservada ao organizador.",
    )
    if st.button("Entrar como organizador", key="btn_admin_login_sidebar"):
        if pwd and pwd == ADMIN_PASSWORD:
            st.session_state["is_admin"] = True
            st.success("Sessão de organizador ativa.")
            st.rerun()
        else:
            st.error("Código inválido.")
    return is_admin()


# =========================================================
# ESTILOS (CSS)
# =========================================================
def inject_styles():
    st.markdown(
        """
        <style>
        :root{
          --space:16px;
          --btn-h:92px;
          --bg:#0f1115; --panel:#151922; --panel-2:#1a1f2b; --text:#e7eaf0; --muted:#9aa4b2; --border:#2a2f3a;
          --gold:#d4af37; --silver:#c0c0c0; --bronze:#cd7f32;
        }
        .stApp{background:var(--bg);color:var(--text)}
        #MainMenu{display:none} footer{visibility:hidden;height:0}
        [data-testid="stVerticalBlock"] > div:not(:last-child),
        [data-testid="stVerticalBlock"] > section:not(:last-child),
        [data-testid="column"] [data-testid="stVerticalBlock"] > div:not(:last-child),
        [data-testid="column"] [data-testid="stVerticalBlock"] > section:not(:last-child),
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div:not(:last-child),
        [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > section:not(:last-child){
          margin-bottom:var(--space)!important;
        }
        hr{margin:var(--space)0!important;}

        .panel{
          background:linear-gradient(180deg,var(--panel),var(--panel-2));
          border:1px solid var(--border);border-radius:16px;padding:18px;
          box-shadow:0 6px 24px rgba(0,0,0,.28);
        }
        .panel > * + *{margin-top:var(--space);}
        .hdr{font-size:26px;font-weight:700;letter-spacing:.2px;margin:0}
        .sub{font-size:13px;color:var(--muted);margin:0}
        .div{height:1px;background:var(--border);}

        .metric{
          background:linear-gradient(180deg,#141926,#0f141f);
          border:1px solid var(--border);border-radius:14px;padding:16px
        }
        .metric .lbl{font-size:12px;color:var(--muted)}
        .metric .val{font-size:28px;font-weight:800;margin-top:6px;letter-spacing:.3px}

        .hero{
          position:relative;overflow:hidden;border-radius:18px;padding:22px 22px;
          background:
            radial-gradient(1200px 400px at 10% -10%, rgba(99,122,255,.18), transparent 60%),
            radial-gradient(900px 300px at 110% 10%, rgba(244,182,215,.16), transparent 60%),
            linear-gradient(180deg,#111523,#0e121c);
          border:1px solid var(--border);box-shadow:0 12px 32px rgba(0,0,0,.35)
        }
        .hero h1{margin:0 0 6px 0;font-size:28px;font-weight:900;letter-spacing:.2px}
        .hero p{margin:0;color:var(--muted)}

        #home-row + div{display:flex;gap:16px;width:100%;}
        #home-row + div [data-testid="column"]{flex:1 1 0!important;display:flex;}
        #home-row + div [data-testid="column"] .stButton{width:100%;display:flex;flex:1;}
        #home-row + div [data-testid="column"] .stButton>button{
          width:100%;height:var(--btn-h);min-height:var(--btn-h);max-height:var(--btn-h);
          border-radius:16px;padding:18px 20px;
          border:1px solid rgba(255,255,255,.14);
          background:linear-gradient(180deg,#161b28,#131826);
          color:#e7eaf0;font-weight:800;font-size:16px;letter-spacing:.2px;
          display:flex;align-items:center;justify-content:center;text-align:center;
          box-shadow:0 8px 22px rgba(0,0,0,.28);
          transition:transform .14s ease, box-shadow .14s ease, filter .14s ease;
          white-space:normal;word-break:break-word;
        }
        #home-row + div [data-testid="column"] .stButton>button:hover{
          transform:translateY(-2px);filter:brightness(1.02);
          box-shadow:0 12px 28px rgba(0,0,0,.36);
        }
        #home-row + div [data-testid="column"] .stButton>button:active{transform:translateY(-1px);}

        .select-card{
          background:linear-gradient(180deg,#121828,#0f1522);
          border:1px solid var(--border);
          border-radius:16px;
          padding:16px;
          box-shadow:0 8px 24px rgba(0,0,0,.28);
        }
        .select-card .title{font-weight:700;margin-bottom:8px}
        .select-card .hint{color:var(--muted);font-size:13px;margin-top:6px}

        .enter-wrap .stButton>button{
          width:100%;border-radius:12px;padding:12px 14px;
          border:1px solid rgba(255,255,255,.14);
          background:linear-gradient(180deg,#1a2132,#121826);
          color:#e7eaf0;font-weight:800;letter-spacing:.2px;
          box-shadow:0 8px 22px rgba(0,0,0,.28);
          transition:transform .14s ease, box-shadow .14s ease, filter .14s ease;
        }
        .enter-wrap .stButton>button:hover{
          transform:translateY(-1px);filter:brightness(1.02);
          box-shadow:0 12px 28px rgba(0,0,0,.36);
        }

        .select-center [data-baseweb="select"]{text-align:center;}
        .select-center [data-baseweb="select"] *{text-align:center!important;}
        .select-center [data-baseweb="select"]>div{justify-content:center!important;}

        .podium{text-align:center;position:relative}
        .badge{display:inline-block;padding:3px 10px;border:1px solid var(--border);border-radius:999px;font-size:12px}
        .gold{border-color:var(--gold);color:var(--gold)}
        .silver{border-color:var(--silver);color:var(--silver)}
        .bronze{border-color:var(--bronze);color:var(--bronze)}
        .tip{
            position:absolute;left:50%;transform:translateX(-50%);
            bottom:-6px;opacity:0;pointer-events:none;
            background:#0e1117;color:#e6e9ef;border:1px solid var(--border);
            padding:10px 12px;border-radius:10px;
            font-size:12px;white-space:nowrap;
            transition:opacity .15s ease,bottom .15s ease;
            box-shadow:0 10px 24px rgba(0,0,0,.35)
        }
        .podium:hover .tip{opacity:1;bottom:-10px}
        </style>
        """,
        unsafe_allow_html=True,
    )


def header(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="panel">
            <div class="hdr">{title}</div>
            <div class="sub">{subtitle}</div>
            <div class="div"></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def metric(label: str, value: str):
    st.markdown(
        f"""
        <div class="metric">
            <div class="lbl">{label}</div>
            <div class="val">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =========================================================
# DATA / RANKING BASE HISTÓRICO
# =========================================================
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
    # transforma o CSV legado em registos por-jogador
    if df.empty:
        return pd.DataFrame(
            columns=[
                "Year",
                "Month",
                "Day",
                "Data",
                "Team",
                "Player",
                "Position",
                "Points",
            ]
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
        return pd.DataFrame(
            columns=["Jogador(a)", "Pontos Totais", "Participações", "Média de Pontos"]
        )

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
        return pd.DataFrame(
            columns=[
                "Jogador(a)",
                "Pontos Totais",
                "Participações",
                "Média de Pontos",
                "Parceiras(os) frequentes",
            ]
        )

    expanded = expanded.copy()
    expanded["Player"] = expanded["Player"].astype("string")
    expanded["Team"] = expanded["Team"].astype("string")

    rows = []
    for ((player, y, m, d, team, pos, pts), _grp) in expanded.groupby(
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
        tops = (
            partners_df.groupby(["Jogador(a)", "Parceiro(a)"])
            .size()
            .reset_index(name="Contagem")
            .sort_values(["Jogador(a)", "Contagem"], ascending=[True, False])
            .groupby("Jogador(a)")
            .apply(
                lambda g: ", ".join(
                    [
                        f"{r['Parceiro(a)']} ({int(r['Contagem'])})"
                        for _, r in g.head(3).iterrows()
                    ]
                )
            )
            .reset_index(name="Parceiras(os) frequentes")
        )

    r = compute_ranking(expanded).copy()
    idx = (
        r.merge(tops, on="Jogador(a)", how="left")
        .fillna({"Parceiras(os) frequentes": ""})
    )
    idx.index = range(1, len(idx) + 1)
    return idx


def _all_event_dates(expanded: pd.DataFrame) -> List[Tuple[int,int,int,int]]:
    """
    Devolve lista ordenada cronologicamente de datas únicas (ano, mês_idx, dia).
    """
    if expanded.empty:
        return []

    rows = []
    for (y, m, d) in expanded[["Year", "Month", "Day"]].drop_duplicates().itertuples(index=False):
        month_idx = MONTH_INDEX.get(str(m), 99)
        rows.append((int(y), int(month_idx), int(d)))

    rows = sorted(set(rows), key=lambda x: (x[0], x[1], x[2]))

    out = []
    for y, mi, d in rows:
        month_name = MONTH_ORDER[mi] if 0 <= mi < len(MONTH_ORDER) else str(mi)
        out.append((y, month_name, d))
    return out


def _filter_until_dates(expanded: pd.DataFrame, dates_subset: List[Tuple[int,str,int]]) -> pd.DataFrame:
    """
    Mantém apenas linhas cujo (Year, Month, Day) esteja no conjunto dates_subset.
    """
    if expanded.empty or not dates_subset:
        return pd.DataFrame(columns=expanded.columns)

    mask = pd.Series([False] * len(expanded))
    for (y, m, d) in dates_subset:
        mask = mask | (
            (expanded["Year"] == y)
            & (expanded["Month"] == m)
            & (expanded["Day"] == d)
        )
    return expanded[mask].copy()


def compute_ranking_with_momentum(expanded: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Devolve (top3, resto_formatado)

    top3 -> para o pódio, sem mudanças.
    resto_formatado -> DataFrame do 4.º lugar em diante com:
        Pos  (posição atual)
        Var    (variação, ex: '▲ +3', '▼ -2', '')
        Jogador(a)
        Pontos Totais
        Participações
        Média de Pontos
    """

    current_full = compute_ranking(expanded).copy()
    if current_full.empty:
        empty_cols = [
            "Pos",
            "Var",
            "Jogador(a)",
            "Pontos Totais",
            "Participações",
            "Média de Pontos",
        ]
        return current_full.head(3), pd.DataFrame(columns=empty_cols)

    # datas cronológicas de torneios
    dates_all = _all_event_dates(expanded)

    # posição atual (1..N)
    current_full["__PosAtual__"] = range(1, len(current_full) + 1)

    # mapa de posições anteriores (se houver histórico anterior)
    if len(dates_all) >= 2:
        prev_dates = dates_all[:-1]  # tudo menos o último torneio
        prev_df = _filter_until_dates(expanded, prev_dates)
        prev_ranking = compute_ranking(prev_df)
        prev_pos_map = {
            row["Jogador(a)"]: int(idx)
            for idx, row in prev_ranking.iterrows()
        }
    else:
        prev_pos_map = {}

    # construir colunas Pos e Var
    pos_list = []
    delta_list = []

    for _, row in current_full.iterrows():
        nome = row["Jogador(a)"]
        pos_now = int(row["__PosAtual__"])
        pos_prev = prev_pos_map.get(nome)

        pos_list.append(pos_now)

        if pos_prev is None:
            # jogador(a) não existia antes -> sem seta
            delta_list.append("")
        else:
            diff = pos_prev - pos_now  # positivo = subiu
            if diff > 0:
                delta_list.append(f"▲ +{diff}")
            elif diff < 0:
                delta_list.append(f"▼ {diff}")  # diff já vem negativo
            else:
                delta_list.append("")

    current_full["Pos"] = pos_list
    current_full["Var"] = delta_list

    # top3 para o pódio (não precisa das novas colunas)
    top3 = current_full.head(3).drop(
        columns=["__PosAtual__", "Pos", "Var"], errors="ignore"
    )

    # resto formatado
    resto = current_full.iloc[3:].copy()
    if not resto.empty:
        resto = resto[
            [
                "Pos",
                "Var",
                "Jogador(a)",
                "Pontos Totais",
                "Participações",
                "Média de Pontos",
            ]
        ]

    # limpeza coluna técnica
    if "__PosAtual__" in current_full.columns:
        del current_full["__PosAtual__"]

    return top3, resto


# =========================================================
# UI: PÓDIO
# =========================================================
def podium_with_tooltips(rk: pd.DataFrame):
    cols = st.columns(3)
    labels = [("1.º", "gold"), ("2.º", "silver"), ("3.º", "bronze")]

    for i, ((place, cls), col) in enumerate(zip(labels, cols)):
        with col:
            if rk.shape[0] > i:
                row = rk.iloc[i]
                nome = row.get("Jogador(a)", row.get("Dupla / Equipa", "-"))
                pts = int(row.get("Pontos Totais", row.get("P", 0)))
                part = int(row.get("Participações", 0))
                avg = row.get("Média de Pontos", "-")

                st.markdown(
                    f"""
                    <div class="panel podium">
                        <div class="badge {cls}">{place}</div>
                        <div style="font-size:18px; margin-top:6px">{nome}</div>
                        <div class="sub" style="margin-top:4px">
                            Pontos: <b>{pts}</b>
                        </div>
                        <div class="tip">
                            Participações: <b>{part}</b> ·
                            Média: <b>{avg}</b>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div class="panel podium">
                        <div class="badge {cls}">{place}</div>
                        <div class="sub" style="margin-top:6px">—</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


# =========================================================
# PERSISTÊNCIA DE TORNEIOS (JSON + histórico)
# =========================================================
def _t_path(tid: str) -> Path:
    return TOURNAMENTS_DIR / f"{tid}.json"


def list_custom_tournaments() -> List[Dict]:
    out = []
    for p in sorted(TOURNAMENTS_DIR.glob("*.json")):
        try:
            with p.open("r", encoding="utf-8") as fh:
                obj = json.load(fh)
            out.append(obj)
        except Exception:
            continue
    return out


def _snapshot_tournament(obj: Dict) -> None:
    """
    Guarda um snapshot imutável com timestamp em tournaments/history/.
    Isto captura todas as alterações feitas pelo utilizador
    sempre que se chama save_tournament.
    """
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    snap_path = HISTORY_DIR / f"{obj['id']}_{ts}.json"
    with snap_path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)


def save_tournament(obj: Dict) -> None:
    """
    Guarda o estado atual (tournaments/<id>.json) e cria também
    um snapshot histórico (tournaments/history/<id>_<timestamp>.json).
    """
    path = _t_path(obj["id"])
    with path.open("w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
    _snapshot_tournament(obj)


# =========================================================
# SEEDS / RANKING DE DUPLAS
# =========================================================
def pair_key(a: str, b: str) -> str:
    return f"{a.strip()} / {b.strip()}"


def players_points_map(expanded: pd.DataFrame) -> Dict[str, int]:
    if expanded.empty:
        return {}
    r = compute_ranking(expanded)
    return {
        row["Jogador(a)"]: int(row["Pontos Totais"])
        for _, row in r.iterrows()
    }


def seed_pairs(
    pairs: List[Tuple[str, str]],
    ppoints: Dict[str, int],
) -> List[Tuple[str, str, int]]:
    out = []
    for a, b in pairs:
        pts = ppoints.get(a, 0) + ppoints.get(b, 0)
        out.append((a, b, pts))
    out.sort(key=lambda x: (-x[2], x[0], x[1]))
    return out  # index+1 => melhor seed


# =========================================================
# GERADORES DE CALENDÁRIO / GRUPOS
# =========================================================
def round_robin_pairs(n: int) -> List[List[Tuple[int, int]]]:
    """
    Geração clássica (método do círculo). n precisa ser par.
    Retorna lista de jornadas; cada jornada é lista de pares (i,j).
    """
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
    """
    Distribui índices (0..N-1) pelos grupos A,B,C,...
    Segue heurísticas específicas por modo 'G2x4', 'G3x4', 'G4x4'.
    """
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


# =========================================================
# CLASSIFICAÇÕES DE JOGOS / TABELAS DE GRUPO
# =========================================================
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
                "J": 0,
                "P": 0,
                "V": 0,
                "E": 0,
                "D": 0,
                "JG": 0,
                "JP": 0,
                "Dif": 0,
                "CD": 0,
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
            columns=[
                "Pos",
                "Dupla / Equipa",
                "J",
                "P",
                "V",
                "E",
                "D",
                "JG",
                "JP",
                "Dif",
                "CD",
            ]
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
        while (
            j < len(prelim)
            and table[prelim[j]]["P"] == Pi
            and table[prelim[j]]["Dif"] == Difi
        ):
            j += 1
        block = prelim[i:j]
        if len(block) > 1:
            block = sorted(
                block,
                key=lambda t: -sum(
                    cd_map.get((t, u), 0) for u in block if u != t
                ),
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
                "CD": sum(
                    cd_map.get((team, u), 0)
                    for u in final_order
                    if u != team
                ),
            }
        )
    return pd.DataFrame(rows)


def assign_courts(
    jogos: List[Tuple[int, int]],
    courts: List[str],
) -> List[Tuple[int, int, str]]:
    if len(jogos) > len(courts):
        raise ValueError("Número de jogos excede número de campos selecionados")
    shuffled = jogos[:]
    random.shuffle(shuffled)
    return [(a, b, courts[i]) for i, (a, b) in enumerate(shuffled)]


# =========================================================
# HELPERS / ESTATÍSTICAS PARA GRUPOS & POTES (Fases G2x4,G3x4,G4x4)
# =========================================================
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


def _initial_seed_points_for_team(
    t: Dict,
    team_name: str,
    pmap: Dict[str, int],
) -> int:
    a, b = split_team(team_name)
    return pmap.get(a, 0) + pmap.get(b, 0)


def _group_matches_until_round(
    t: Dict,
    group: str,
    max_group_round: int = 3,
) -> List[Dict]:
    out = []
    for r in t.get("rounds", []):
        for m in r.get("games", []):
            if (
                m.get("phase") == "groups"
                and m.get("group") == group
                and int(m.get("round", 0)) <= max_group_round
            ):
                out.append(m)
    return out


def compute_group_tables_live(t: Dict) -> Dict[str, pd.DataFrame]:
    """
    Devolve uma classificação por grupo (A,B,...) com:
    - Pos, Rank (seed pts), Dupla / Equipa, J/P/V/E/D/JG/JP/Dif/CD
    - CD só visível para equipas empatadas em P
    """
    # carregar histórico correto para o modelo deste torneio
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
                    cd_val = getattr(row, "CD")
                    cd_list.append(str(cd_val))
                else:
                    cd_list.append("")
            df = df.drop(columns=["CD"])
            df["CD"] = pd.Series(cd_list, index=df.index, dtype="string")

            order_cols = [
                "Pos","Rank","Dupla / Equipa","J","P","V","E","D","JG","JP","Dif","CD",
            ]
            df = df[order_cols]
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


def _rank_block_for_pots(
    team_list: List[str],
    tables_by_group: Dict[str, pd.DataFrame],
    groups: List[str],
) -> List[str]:
    """
    Ordena equipas por P desc, Dif desc, nome asc,
    para comparar 2.ºs/3.ºs/etc entre grupos.
    """
    items = []
    for team in team_list:
        for g in groups:
            df = tables_by_group[g]
            row = df[df["Dupla / Equipa"] == team]
            if not row.empty:
                items.append(
                    (
                        team,
                        int(row["P"].iloc[0]),
                        int(row["Dif"].iloc[0]),
                    )
                )
                break
    items.sort(key=lambda x: (-x[1], -x[2], x[0]))
    return [x[0] for x in items]


def _select_pots_from_standings(
    t: Dict,
    tables_by_group: Dict[str, pd.DataFrame],
) -> List[List[str]]:
    """
    Cria potes para as jornadas finais (modelos G2x4/G3x4/G4x4).
    """
    tipo = t.get("tipo")
    groups = sorted(tables_by_group.keys())

    if tipo == "G2x4":
        A = tables_by_group["A"].sort_values("Pos")
        B = tables_by_group["B"].sort_values("Pos")
        pot1 = [
            A.iloc[0]["Dupla / Equipa"],
            A.iloc[1]["Dupla / Equipa"],
            B.iloc[0]["Dupla / Equipa"],
            B.iloc[1]["Dupla / Equipa"],
        ]
        pot2 = [
            A.iloc[2]["Dupla / Equipa"],
            A.iloc[3]["Dupla / Equipa"],
            B.iloc[2]["Dupla / Equipa"],
            B.iloc[3]["Dupla / Equipa"],
        ]
        return [pot1, pot2]

    if tipo == "G3x4":
        A = tables_by_group["A"].sort_values("Pos")
        B = tables_by_group["B"].sort_values("Pos")
        C = tables_by_group["C"].sort_values("Pos")

        firsts = [A.iloc[0]["Dupla / Equipa"], B.iloc[0]["Dupla / Equipa"], C.iloc[0]["Dupla / Equipa"]]
        seconds = [A.iloc[1]["Dupla / Equipa"], B.iloc[1]["Dupla / Equipa"], C.iloc[1]["Dupla / Equipa"]]
        thirds = [A.iloc[2]["Dupla / Equipa"], B.iloc[2]["Dupla / Equipa"], C.iloc[2]["Dupla / Equipa"]]
        fourths = [A.iloc[3]["Dupla / Equipa"], B.iloc[3]["Dupla / Equipa"], C.iloc[3]["Dupla / Equipa"]]

        firsts_sorted = _rank_block_for_pots(firsts, tables_by_group, groups)
        seconds_sorted = _rank_block_for_pots(seconds, tables_by_group, groups)
        thirds_sorted = _rank_block_for_pots(thirds, tables_by_group, groups)

        pot1 = (firsts_sorted + [seconds_sorted[0]])[:4]
        pot2 = seconds_sorted[1:] + thirds_sorted[:2]
        pot3 = thirds_sorted[2:] + fourths
        return [pot1, pot2, pot3]

    if tipo == "G4x4":
        pots = []
        for pos in range(1, 5):
            pots.append(
                [
                    tables_by_group[g].sort_values("Pos").iloc[pos - 1]["Dupla / Equipa"]
                    for g in groups
                ]
            )
        return pots

    return []


def _rebuild_matches(t: Dict) -> None:
    """
    Garante que t["matches"] corresponde sempre à concatenação
    de todos os jogos em t["rounds"].
    """
    t["matches"] = sum([r["games"] for r in t.get("rounds", [])], [])


def _generate_finals_from_pots_and_replace(t: Dict) -> Tuple[bool, str]:
    """
    Para formatos G2x4 / G3x4 / G4x4:
    - Usa a classificação após 3 jornadas de grupos
    - Cria Jornada 4 (cruzamentos / potes)
    - Cria Jornada 5 (vencedores vs vencedores / perdedores vs perdedores)
    - Substitui as jornadas 4 e 5 no torneio.
    """
    tables = compute_group_tables_live(t)
    if not tables:
        return False, "Não existem grupos para este evento."

    courts = t.get("courts", [])
    if not courts:
        return False, "Sem campos definidos."

    groups = sorted(tables.keys())
    nG = len(groups)
    if nG not in (2, 3, 4):
        return (
            False,
            "Número de grupos não suportado para cruzamentos (esperado: 2, 3 ou 4).",
        )

    pos_map: Dict[str, List[str]] = {}
    for g in groups:
        df = tables[g].sort_values("Pos")
        pos_map[g] = list(df["Dupla / Equipa"].values)

    def _rank_block(teams_list: List[str]) -> List[str]:
        items = []
        for team in teams_list:
            for gx in groups:
                df = tables[gx]
                row = df[df["Dupla / Equipa"] == team]
                if not row.empty:
                    items.append(
                        (
                            team,
                            int(row["P"].iloc[0]),
                            int(row["Dif"].iloc[0]),
                        )
                    )
                    break
        items.sort(key=lambda x: (-x[1], -x[2], x[0]))
        return [x[0] for x in items]

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

        seconds_sorted = _rank_block([A2, B2, C2])
        thirds_sorted = _rank_block([A3, B3, C3])
        fourths_sorted = _rank_block([A4, B4, C4])

        melhor2, segundo2, pior2 = (
            seconds_sorted[0],
            seconds_sorted[1],
            seconds_sorted[2],
        )
        melhor3, segundo3, pior3 = (
            thirds_sorted[0],
            thirds_sorted[1],
            thirds_sorted[2],
        )
        melhor4, segundo4, pior4 = (
            fourths_sorted[0],
            fourths_sorted[1],
            fourths_sorted[2],
        )

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
            {
                "phase": "finals",
                "round": r4_num,
                "team_a": A_team,
                "team_b": B_team,
                "court": court,
                "score": "",
            }
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
    return (
        True,
        "Potes (Jornadas 4 e 5) gerados/atualizados com base na classificação.",
    )


def _recalculate_round5_from_round4(t: Dict) -> bool:
    """
    Para formatos de grupos: gera/atualiza Jornada 5 com 'placement'
    (1º/2º lugar, 3º/4º lugar, etc.) com base nos vencedores/perdedores da Jornada 4.
    """
    rounds_map = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
    r4 = rounds_map.get(4)
    if not r4:
        return False

    r4_games = r4.get("games", [])
    if not r4_games:
        return False

    if len(r4_games) < 2:
        return False

    courts_all = t.get("courts", []) or ["Campo ?"]

    def _decide_winner_loser(game: Dict, label_fallback: str) -> Tuple[str, str]:
        score_txt = game.get("score", "").strip()
        jg, jp = parse_score(score_txt)
        team_a = game.get("team_a", "A")
        team_b = game.get("team_b", "B")

        if not score_txt or jg == jp:
            return (f"Vencedor {label_fallback}", f"Perdedor {label_fallback}")

        if jg > jp:
            return (team_a, team_b)
        else:
            return (team_b, team_a)

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
            {
                "phase": "finals",
                "round": 5,
                "placement": winners_label,
                "team_a": w1,
                "team_b": w2,
                "court": court_w,
                "score": "",
            }
        )

        court_l = courts_all[court_idx % len(courts_all)]
        court_idx += 1
        new_r5_games.append(
            {
                "phase": "finals",
                "round": 5,
                "placement": losers_label,
                "team_a": l1,
                "team_b": l2,
                "court": court_l,
                "score": "",
            }
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
    """
    Classificação final para formatos de grupos:
    usa Jornada 5 com campo 'placement'
    ('1º e 2º lugar', etc.).
    """
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
            if jg > jp:
                winner, loser = team_a, team_b
            else:
                winner, loser = team_b, team_a

        placements.append((base_pos, winner))
        placements.append((base_pos + 1, loser))

    placements.sort(key=lambda x: x[0])
    rows = [{"Pos": pos, "Dupla / Equipa": team} for pos, team in placements]
    return pd.DataFrame(rows, columns=["Pos", "Dupla / Equipa"])


# =========================================================
# UP & DOWN: HELPERS ESPECÍFICOS
# =========================================================
def order_courts_desc(courts: List[str]) -> List[str]:
    """
    Ordena courts de "mais alto" -> "mais baixo" segundo ALL_COURTS.
    """
    priority = {name: i for i, name in enumerate(ALL_COURTS)}
    return sorted(courts, key=lambda c: priority.get(c, 9999))


def _generate_updown_rounds(t: Dict) -> None:
    """
    Cria toda a grelha base do formato UPDOWN:
    - Jornada 1 aleatória, pares distribuídos de court mais alto -> mais baixo.
    - Jornadas 2..5 criadas vazias.
    Regras:
      * nº_duplas == expected_pairs e par
      * nº_courts == nº_duplas/2
    """
    num_pairs = len(t.get("pairs", []))
    expected = int(t.get("expected_pairs") or 0)
    if expected <= 0 or num_pairs != expected:
        raise ValueError(
            f"UPDOWN: nº de duplas inválido. Esperado {expected}, recebeu {num_pairs}."
        )
    if num_pairs % 2 != 0:
        raise ValueError("UPDOWN: nº de duplas tem de ser par.")

    courts_raw = t.get("courts", [])
    courts_ord = order_courts_desc(courts_raw)
    if len(courts_ord) * 2 != num_pairs:
        raise ValueError(
            "UPDOWN: nº de campos tem de ser exatamente nº_duplas/2."
        )

    pair_names = [p["name"] for p in t["pairs"]]
    random.shuffle(pair_names)

    round1_games = []
    for idx_court, court_name in enumerate(courts_ord):
        team_a = pair_names[2 * idx_court]
        team_b = pair_names[2 * idx_court + 1]
        round1_games.append(
            {
                "phase": "updown",
                "round": 1,
                "team_a": team_a,
                "team_b": team_b,
                "court": court_name,
                "score": "",
            }
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
    """
    Baralha de novo a Jornada 1 (antes de começar), mantendo nº de duplas/courts.
    Só se não houver resultados na Jornada 1 e se jornadas 2..5 estiverem vazias.
    """
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
            return (
                False,
                "Já existem jornadas seguintes geradas. Não é possível voltar a baralhar.",
            )

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
            {
                "phase": "updown",
                "round": 1,
                "team_a": team_a,
                "team_b": team_b,
                "court": court_name,
                "score": "",
            }
        )

    r1["games"] = new_games
    for rn in [2, 3, 4, 5]:
        if rn in rounds_map:
            rounds_map[rn]["games"] = []

    t["rounds"] = [rounds_map[rn] for rn in sorted(rounds_map.keys())]
    _rebuild_matches(t)
    return True, "Nova configuração inicial gerada com sucesso."


def _updown_build_next_round(t: Dict, current_round_num: int) -> bool:
    """
    Depois de guardar resultados da jornada X, gera a jornada X+1 automaticamente:
    - Vencedores sobem um court (mais alto),
    - Perdedoras descem um court (mais baixo),
    - Top court e bottom court tratam limites (ficam no topo/fundo).
    """
    if t.get("tipo") != "UPDOWN":
        return False

    rounds_map = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
    r_curr = rounds_map.get(current_round_num)
    next_round_num = current_round_num + 1
    if not r_curr or next_round_num > 5:
        return False

    courts_ord = order_courts_desc(t.get("courts", []))
    court_priority = {c: i for i, c in enumerate(courts_ord)}

    games_curr = sorted(
        r_curr.get("games", []),
        key=lambda g: court_priority.get(g.get("court", ""), 9999),
    )

    results_by_idx = []
    for gm in games_curr:
        score_txt = gm.get("score", "").strip()
        jg, jp = parse_score(score_txt)
        team_a = gm.get("team_a", "")
        team_b = gm.get("team_b", "")

        if not score_txt or jg == jp:
            return False  # precisamos de vencedor claro

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
            {
                "phase": "updown",
                "round": next_round_num,
                "team_a": team_a,
                "team_b": team_b,
                "court": court_name,
                "score": "",
            }
        )

    if next_round_num in rounds_map:
        rounds_map[next_round_num]["games"] = next_games
    else:
        rounds_map[next_round_num] = {
            "n": next_round_num,
            "games": next_games,
        }

    t["rounds"] = [rounds_map[k] for k in sorted(rounds_map.keys())]
    _rebuild_matches(t)
    return True


def compute_final_classification_from_updown(t: Dict) -> pd.DataFrame:
    """
    Classificação final para torneios UP & DOWN:
    - Usa a Jornada 5 (round n=5).
    - Assume que t["courts"] está ordenado do campo mais alto para o mais baixo.
      Exemplo: ["Campo Central", "Campo 10", "Campo 9", ...]
    - Ordena os jogos da jornada 5 por essa hierarquia dos courts.
    - Para cada jogo (nessa ordem):
        vencedor -> próxima posição disponível (1º, 3º, 5º, ...)
        perdedor -> posição seguinte (2º, 4º, 6º, ...)
    Retorna DataFrame com colunas ["Pos", "Dupla / Equipa"].
    """

    # Só faz sentido neste tipo
    if t.get("tipo") != "UPDOWN":
        return pd.DataFrame(columns=["Pos", "Dupla / Equipa"])

    # Ir buscar a ronda 5
    rounds_map = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
    r5 = rounds_map.get(5)
    if not r5:
        return pd.DataFrame(columns=["Pos", "Dupla / Equipa"])

    games_round5 = r5.get("games", [])
    if not games_round5:
        return pd.DataFrame(columns=["Pos", "Dupla / Equipa"])

    # Hierarquia de courts (melhor -> pior) já guardada no torneio
    court_order = t.get("courts", [])

    court_priority = {court_name: i for i, court_name in enumerate(court_order)}

    games_sorted = sorted(
        games_round5,
        key=lambda g: court_priority.get(g.get("court", ""), 9999),
    )

    placements = []
    next_pos = 1  # começamos a atribuir 1º lugar

    for gm in games_sorted:
        team_a = gm.get("team_a", "")
        team_b = gm.get("team_b", "")
        score_txt = gm.get("score", "").strip()
        jg, jp = parse_score(score_txt)

        if not score_txt or jg == jp:
            winner = f"Vencedor {team_a} vs {team_b}"
            loser = f"Perdedor {team_a} vs {team_b}"
        else:
            if jg > jp:
                winner, loser = team_a, team_b
            else:
                winner, loser = team_b, team_a

        placements.append({"Pos": next_pos, "Dupla / Equipa": winner})
        placements.append({"Pos": next_pos + 1, "Dupla / Equipa": loser})
        next_pos += 2

    return pd.DataFrame(placements, columns=["Pos", "Dupla / Equipa"])


# =========================================================
# SUPPORT / CSV LEGADO
# =========================================================
def _pt_month_name(m: int) -> str:
    return MONTH_ORDER[m - 1] if 1 <= m <= 12 else str(m)


def append_final_table_to_csv_if_applicable(t: Dict):
    """
    Acrescenta a classificação final deste evento ao CSV histórico do modelo correspondente.
    """

    model = t.get("model")
    # apenas modelos mapeados
    data_file = get_data_file_for_model(model)
    if not data_file or model not in MODEL_DATA_FILES:
        return

    # 2. Obter classificação final
    if t.get("tipo") == "UPDOWN":
        df_final = compute_final_classification_from_updown(t)
    else:
        df_final = compute_final_classification_from_round5(t)

    if df_final.empty:
        return

    # 3. Extrair data do torneio
    dy = int(t.get("date", {}).get("year", datetime.now().year))
    dm = int(t.get("date", {}).get("month", datetime.now().month))
    dd = int(t.get("date", {}).get("day", datetime.now().day))

    mname = _pt_month_name(dm)

    # 4. Preparar linhas a escrever
    rows = []
    for _, r in df_final.iterrows():
        rows.append(
            {
                "Year": dy,
                "Month": mname,
                "Day": dd,
                "Position": int(r["Pos"]),
                "Team": str(r["Dupla / Equipa"]),
            }
        )

    file_exists = data_file.exists()

    # 5. Garantir newline final se o ficheiro já existir
    if file_exists:
        with data_file.open("rb") as fh_check:
            fh_check.seek(0, os.SEEK_END)
            size = fh_check.tell()
            if size > 0:
                fh_check.seek(-1, os.SEEK_END)
                last_byte = fh_check.read(1)
            else:
                last_byte = b"\n"
        if last_byte not in (b"\n", b"\r"):
            with data_file.open("a", encoding="utf-8", newline="") as fh_fix:
                fh_fix.write("\n")

    # 6. Append das novas linhas
    with data_file.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["Year", "Month", "Day", "Position", "Team"],
        )
        if not file_exists:
            writer.writeheader()
        for row in rows:
            writer.writerow(row)


# =========================================================
# CRIAÇÃO / ABERTURA DE EVENTO POR MODELO + DATA
# =========================================================
def _event_id_from(model_id: str, y: int, m: int, d: int) -> str:
    return f"{model_id}_{y:04d}{m:02d}{d:02d}"


def create_or_open_event_for_model(
    model_id: str,
    y: int,
    m: int,
    d: int,
) -> Dict:
    """
    Cria (se não existir) ou carrega um evento JSON para um dado modelo e data.
    """
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
        "date": {
            "year": y,
            "month": m,
            "day": d,
        },
        "pairs": [],
        "courts": [],
        "rounds": [],
        "matches": [],
        "state": "setup",
        "notices": {
            "tipo": "",
            "duplas": "",
            "campos": "",
            "jornadas": "",
        },
    }

    save_tournament(obj)
    return obj


# =========================================================
# PÁGINA HOME (escolha de torneio base)
# =========================================================
def page_home():
    inject_styles()

    st.markdown(
        """
        <div class="hero">
            <h1>Gestão de torneios e eventos</h1>
            <p>Escolhe um torneio para entrar.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    dfs = []
    for p in MODEL_DATA_FILES.values():
        dfs.append(load_data(p))
    df_raw = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(
        columns=["Year","Month","Day","Position","Team"]
    )
    df_exp = expand_results(df_raw)

    total_torneios = (
        df_exp[["Year", "Month", "Day"]].drop_duplicates().shape[0]
        if not df_exp.empty
        else 0
    )
    num_jogadores = df_exp["Player"].nunique() if not df_exp.empty else 0
    registos = df_exp.shape[0] if not df_exp.empty else 0

    c1, c2, c3 = st.columns(3)
    with c1:
        metric("Torneios", str(total_torneios))
    with c2:
        metric("N.º de jogadores(as)", str(num_jogadores))
    with c3:
        metric("Registos", str(registos))

    st.markdown(
        '<div class="panel"><div class="hdr" style="font-size:20px;">'
        "Escolher torneio</div></div>",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="select-card select-center">', unsafe_allow_html=True)

    nomes = [t["nome"] for t in TOURNAMENTS]
    sel = st.selectbox(
        "Escolher torneio",
        options=nomes,
        index=None,
        placeholder="Selecione um torneio…",
        key="home_select",
        label_visibility="collapsed",
    )

    st.markdown("</div>", unsafe_allow_html=True)

    nome_para_id = {t["nome"]: t["id"] for t in TOURNAMENTS}

    st.markdown('<div class="enter-wrap">', unsafe_allow_html=True)
    if sel:
        if st.button("Entrar no torneio", key="btn_enter", use_container_width=True):
            st.session_state["torneio_sel"] = nome_para_id.get(sel)
            st.session_state["sec"] = "Ranking"
            st.rerun()
    else:
        st.button(
            "Entrar no torneio",
            key="btn_enter_disabled",
            disabled=True,
            use_container_width=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# PÁGINA DE GESTÃO DETALHADA DE UM EVENTO (JSON)
# =========================================================
def page_manage_tournament(tid: str):
    inject_styles()

    # proteção de organizador
    if not is_admin():
        header("Área reservada", "Apenas o organizador pode gerir eventos.")
        pwd = st.text_input(
            "Código de organizador",
            type="password",
            key="admin_pwd_manage",
            help="Introduza o código para aceder à gestão de eventos.",
        )
        if st.button("Entrar como organizador", key="btn_admin_login_manage"):
            if pwd and pwd == ADMIN_PASSWORD:
                st.session_state["is_admin"] = True
                st.success("Sessão de organizador ativa.")
                st.rerun()
            else:
                st.error("Código inválido.")
        return

    tpath = _t_path(tid)
    if not tpath.exists():
        st.error("Torneio não encontrado.")
        return

    with tpath.open("r", encoding="utf-8") as fh:
        t = json.load(fh)

    st.markdown(
        """
        <style>
        .back-one-line .stButton > button{
            white-space:nowrap;
            width:auto !important;
            display:inline-block;
            padding:0.4rem 0.75rem;
            font-weight:600;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="back-one-line">', unsafe_allow_html=True)
    if st.button("← Voltar ao torneio", key=f"btn_back_{tid}"):
        st.session_state["torneio_sel"] = t.get("model")
        st.session_state["sec"] = "Ranking"
        st.session_state["page"] = "home"
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

    label_tipo = TOURNEY_TYPES.get(t.get("tipo"), {}).get("label", "Tipo não definido")
    header(f"Gestor: {t['nome']}", f"{label_tipo}  ·  Modelo: {t.get('model','')}")

    t.setdefault("notices", {"tipo": "", "duplas": "", "campos": "", "jornadas": ""})

    tabs = st.tabs(["Configuração", "Jornadas & Resultados", "Classificação", "Exportar"])

    # -----------------------------------------------------
    # TAB 1: CONFIGURAÇÃO
    # -----------------------------------------------------
    with tabs[0]:
        # 1) Tipo
        st.markdown("#### 1) Tipo de torneio")
        if t["notices"].get("tipo"):
            st.success(t["notices"]["tipo"])

        tipo_keys = list(TOURNEY_TYPES.keys())
        tipo_labels = [TOURNEY_TYPES[k]["label"] for k in tipo_keys]
        label_to_key = {TOURNEY_TYPES[k]["label"]: k for k in tipo_keys}

        sel_tipo = st.selectbox(
            "Selecionar tipo de torneio",
            options=tipo_labels,
            index=None,
            placeholder="Escolher opção",
            help="Defina o formato; as duplas e os campos serão ajustados automaticamente.",
        )
        tipo_key = label_to_key[sel_tipo] if sel_tipo else None
        fixed_teams = TOURNEY_TYPES.get(tipo_key, {}).get("teams") if tipo_key else None

        col_a, col_b = st.columns([2, 1])
        with col_a:
            if tipo_key is None:
                st.info("Escolha um tipo para prosseguir.")
            elif fixed_teams:
                st.markdown(f"**Número de duplas (fixo): {fixed_teams}**")
            else:
                exp_def = t.get("expected_pairs") or max(
                    4,
                    len(t.get("pairs", [])) if t.get("pairs") else 8,
                )
                expected_pairs_input = st.number_input(
                    "Número de duplas (Americano / Up & Down)",
                    min_value=4,
                    step=2,
                    value=int(exp_def),
                )

        with col_b:
            st.markdown("&nbsp;", unsafe_allow_html=True)
            if st.button("Guardar tipo", key="btn_save_tipo", disabled=(tipo_key is None)):
                t["tipo"] = tipo_key
                t["expected_pairs"] = (
                    int(fixed_teams) if fixed_teams else int(expected_pairs_input)
                )

                pairs_sorted = sorted(
                    t.get("pairs", []),
                    key=lambda x: (-x.get("seed_pts", 0), x.get("name", "")),
                )
                if len(pairs_sorted) > t["expected_pairs"]:
                    t["pairs"] = pairs_sorted[: t["expected_pairs"]]

                def _required_courts(tipo: str, num_pairs: int) -> Tuple[int, int]:
                    if tipo == "LIGA6":
                        return (3, 3)
                    if tipo == "G2x4":
                        return (4, 4)
                    if tipo == "G3x4":
                        return (6, 6)
                    if tipo == "G4x4":
                        return (8, 8)
                    if tipo == "UPDOWN":
                        mx = max(1, num_pairs // 2)
                        return (mx, mx)
                    return (0, 0)

                min_c, max_c = _required_courts(t["tipo"], len(t.get("pairs", [])))
                if t["tipo"] == "UPDOWN":
                    t["courts"] = order_courts_desc(ALL_COURTS)[:max_c]
                else:
                    t["courts"] = order_courts_desc(ALL_COURTS)[:min_c]

                t["notices"]["tipo"] = (
                    f"Tipo de torneio guardado: {TOURNEY_TYPES[t['tipo']]['label']}."
                )
                save_tournament(t)
                st.success(t["notices"]["tipo"])
                st.rerun()

        st.markdown("---")

        # 2) Duplas
        st.markdown("#### 2) Definir duplas/equipas")
        if t["notices"].get("duplas"):
            st.success(t["notices"]["duplas"])

        data_file_cfg = get_data_file_for_model(t.get("model", ""))
        df_raw = load_data(data_file_cfg)
        exp_df = expand_results(df_raw)
        pmap = players_points_map(exp_df)
        known_players = sorted(exp_df["Player"].dropna().unique()) if not exp_df.empty else []

        expected_pairs = int(t.get("expected_pairs") or 0)

        if not t.get("tipo"):
            st.info("Defina o tipo de torneio no passo 1 para listar as duplas.")
        elif expected_pairs == 0 and t["tipo"] != "UPDOWN":
            st.info("Este formato requer um número fixo de duplas. Guarde o tipo para continuar.")
        else:
            if t["tipo"] == "UPDOWN":
                lines = expected_pairs
            else:
                lines = expected_pairs

            existing = (
                sorted(
                    t.get("pairs", []),
                    key=lambda x: (-x.get("seed_pts", 0), x["name"]),
                )
                if t.get("pairs")
                else []
            )

            st.caption(
                f"Duplas a preencher: **{lines}** "
                f"(existentes: {len(existing)})"
            )

            new_rows = []
            for i in range(lines):
                a_pref = existing[i]["a"] if i < len(existing) else ""
                b_pref = existing[i]["b"] if i < len(existing) else ""

                c1, c2, c3 = st.columns([3, 3, 1])
                with c1:
                    a_sel = st.selectbox(
                        f"Jogador(a) A — linha {i+1}",
                        options=[""] + known_players,
                        index=(1 + known_players.index(a_pref)) if a_pref in known_players else 0,
                        key=f"pair_a_sel_{tid}_{i}",
                        help="Escolha da lista ou deixe vazio e escreva ao lado.",
                    )
                    a_manual = st.text_input(
                        "Ou escrever A",
                        value="" if a_sel else a_pref,
                        key=f"pair_a_manual_{tid}_{i}",
                    )
                with c2:
                    b_sel = st.selectbox(
                        f"Jogador(a) B — linha {i+1}",
                        options=[""] + known_players,
                        index=(1 + known_players.index(b_pref)) if b_pref in known_players else 0,
                        key=f"pair_b_sel_{tid}_{i}",
                        help="Escolha da lista ou deixe vazio e escreva ao lado.",
                    )
                    b_manual = st.text_input(
                        "Ou escrever B",
                        value="" if b_sel else b_pref,
                        key=f"pair_b_manual_{tid}_{i}",
                    )
                with c3:
                    st.markdown("&nbsp;", unsafe_allow_html=True)
                    st.write(f"#{i+1}")

                a_val = (a_sel or a_manual).strip()
                b_val = (b_sel or b_manual).strip()
                if a_val or b_val:
                    new_rows.append((a_val, b_val))

            can_save = True
            full_pairs = [(a, b) for (a, b) in new_rows if a and b]
            if len(full_pairs) != expected_pairs:
                can_save = False
                st.warning(
                    f"Preencha exatamente **{expected_pairs}** duplas completas "
                    f"(tem {len(full_pairs)})."
                )

            if st.button("Guardar duplas", key=f"btn_save_pairs_{tid}", disabled=not can_save):
                pairs_to_keep = []
                for a, b in full_pairs:
                    seed_pts = pmap.get(a, 0) + pmap.get(b, 0)
                    pairs_to_keep.append(
                        {"a": a, "b": b, "name": pair_key(a, b), "seed_pts": seed_pts}
                    )

                if (
                    t["tipo"] != "UPDOWN"
                    and expected_pairs
                    and len(pairs_to_keep) > expected_pairs
                ):
                    pairs_to_keep = sorted(
                        pairs_to_keep,
                        key=lambda x: (-x["seed_pts"], x["name"]),
                    )[:expected_pairs]

                t["pairs"] = pairs_to_keep

                if t["tipo"] == "UPDOWN":
                    max_courts = max(1, len(t["pairs"]) // 2)
                    if not t.get("courts"):
                        t["courts"] = order_courts_desc(ALL_COURTS)[:max_courts]
                    elif len(t["courts"]) != max_courts:
                        t["courts"] = order_courts_desc(t["courts"])[:max_courts]
                else:
                    req_map = {"LIGA6": 3, "G2x4": 4, "G3x4": 6, "G4x4": 8}
                    req = req_map.get(t["tipo"])
                    if req:
                        t["courts"] = order_courts_desc(ALL_COURTS)[:req]

                t["notices"]["duplas"] = f"{len(t['pairs'])} duplas guardadas com sucesso."
                save_tournament(t)
                st.success(t["notices"]["duplas"])
                st.rerun()

        st.markdown("---")

        # 3) Campos
        st.markdown("#### 3) Selecionar campos")
        if t["notices"].get("campos"):
            st.success(t["notices"]["campos"])

        if not t.get("tipo"):
            st.info("Defina o tipo de torneio no passo 1).")
        else:
            n_pairs = len(t.get("pairs", []))
            tipo_lbl = TOURNEY_TYPES[t["tipo"]]["label"]

            if t["tipo"] == "LIGA6":
                required = 3
                min_ok = max_ok = required
                help_txt = f"{tipo_lbl}: escolha **exatamente {required}** campos."
            elif t["tipo"] == "G2x4":
                required = 4
                min_ok = max_ok = required
                help_txt = f"{tipo_lbl}: escolha **exatamente {required}** campos."
            elif t["tipo"] == "G3x4":
                required = 6
                min_ok = max_ok = required
                help_txt = f"{tipo_lbl}: escolha **exatamente {required}** campos."
            elif t["tipo"] == "G4x4":
                required = 8
                min_ok = max_ok = required
                help_txt = f"{tipo_lbl}: escolha **exatamente {required}** campos."
            else:
                expected_pairs_local = int(t.get("expected_pairs") or n_pairs)
                half = max(1, expected_pairs_local // 2)
                required = half
                min_ok = max_ok = required
                help_txt = (
                    f"{tipo_lbl}: escolha **exatamente {required}** campos "
                    "(2 duplas por campo)."
                )

            sel_courts = st.multiselect(
                help_txt,
                options=ALL_COURTS,
                default=t.get("courts", []),
                placeholder="Escolher opções",
            )

            valid = len(sel_courts) == required

            if st.button("Guardar campos", disabled=not valid):
                if not valid:
                    st.error("Seleção inválida de campos.")
                else:
                    if t["tipo"] == "UPDOWN":
                        t["courts"] = order_courts_desc(sel_courts)
                    else:
                        t["courts"] = sel_courts
                    t["notices"]["campos"] = f"Campos guardados: {', '.join(t['courts'])}."
                    save_tournament(t)
                    st.success(t["notices"]["campos"])
                    st.rerun()

        st.markdown("---")

        # 4) Gerar jornadas
        st.markdown("#### 4) Gerar jornadas automaticamente")
        if t["notices"].get("jornadas"):
            st.success(t["notices"]["jornadas"])

        if st.button("Gerar jornadas", type="primary"):
            if not t.get("tipo"):
                st.error("Defina o tipo de torneio no passo 1).")
                st.stop()

            tt = TOURNEY_TYPES[t["tipo"]]
            teams_needed = tt.get("teams")

            if t["tipo"] == "UPDOWN":
                if len(t.get("pairs", [])) != t.get("expected_pairs"):
                    st.error(
                        f"Este formato UP & DOWN requer {t['expected_pairs']} duplas "
                        f"(atualmente {len(t.get('pairs', []))})."
                    )
                    st.stop()

                expected_pairs_local = int(t["expected_pairs"])
                half = max(1, expected_pairs_local // 2)
                if len(t.get("courts", [])) != half:
                    st.error(
                        f"Selecione exatamente {half} campos para {expected_pairs_local} duplas."
                    )
                    st.stop()

            else:
                if t["tipo"] != "UPDOWN" and (
                    not teams_needed or len(t.get("pairs", [])) != teams_needed
                ):
                    st.error(
                        f"Este formato requer {teams_needed} duplas "
                        f"(atualmente {len(t.get('pairs', []))})."
                    )
                    st.stop()

                req_map = {"LIGA6": 3, "G2x4": 4, "G3x4": 6, "G4x4": 8}
                if t["tipo"] in req_map and len(t.get("courts", [])) != req_map[t["tipo"]]:
                    st.error(f"Selecione exatamente {req_map[t['tipo']]} campos.")
                    st.stop()

            exp_df_now = expand_results(load_data(get_data_file_for_model(t.get("model",""))))
            pmap_now = players_points_map(exp_df_now)
            pairs_seeded = seed_pairs(
                [(p["a"], p["b"]) for p in t.get("pairs", [])],
                pmap_now,
            )

            pmap_now = players_points_map(exp_df_now)
            pairs_seeded = seed_pairs(
                [(p["a"], p["b"]) for p in t.get("pairs", [])],
                pmap_now,
            )
            names = [pair_key(a, b) for a, b, _ in pairs_seeded]

            if t["tipo"] == "LIGA6":
                rr = round_robin_pairs(6)
                rounds = []
                for i, jogos in enumerate(rr, start=1):
                    ab = assign_courts(jogos, t["courts"])
                    rounds.append(
                        {
                            "n": i,
                            "games": [
                                {
                                    "team_a": names[a],
                                    "team_b": names[b],
                                    "court": c,
                                    "score": "",
                                }
                                for a, b, c in ab
                            ],
                        }
                    )
                t["rounds"] = rounds
                _rebuild_matches(t)
                t["state"] = "scheduled"

            elif t["tipo"] in ("G2x4", "G3x4", "G4x4"):
                G, S = tt["groups"]
                dist = group_distribution(pairs_seeded, G, S, t["tipo"])
                rounds = []
                matches = []

                for gi, gname in enumerate(sorted(dist.keys())):
                    lst = [names[ix] for ix in dist[gname]]
                    rr = round_robin_pairs(S)
                    for r_i, jogos in enumerate(rr, start=1):
                        ab = [(lst[a], lst[b]) for a, b in jogos]
                        courts_for_group = t["courts"][2 * gi : 2 * gi + max(2, len(ab))]
                        if len(courts_for_group) < len(ab):
                            courts_for_group = t["courts"]
                        for j, (A, B) in enumerate(ab):
                            m = {
                                "phase": "groups",
                                "group": gname,
                                "round": r_i,
                                "team_a": A,
                                "team_b": B,
                                "court": courts_for_group[j % len(courts_for_group)],
                                "score": "",
                            }
                            matches.append(m)

                t["rounds"] = []
                group_rr_len = len(round_robin_pairs(S))
                for r_i in range(1, group_rr_len + 1):
                    gs = [
                        m
                        for m in matches
                        if m["phase"] == "groups" and m["round"] == r_i
                    ]
                    t["rounds"].append({"n": r_i, "games": gs})

                t["rounds"].append({"n": group_rr_len + 1, "games": []})
                t["rounds"].append({"n": group_rr_len + 2, "games": []})
                _rebuild_matches(t)
                t["state"] = "scheduled"

            elif t["tipo"] == "UPDOWN":
                _generate_updown_rounds(t)

            t["notices"]["jornadas"] = "Jornadas geradas e guardadas com sucesso."
            save_tournament(t)
            st.success(t["notices"]["jornadas"])
            st.rerun()

    # -----------------------------------------------------
    # TAB 2: JORNADAS & RESULTADOS
    # -----------------------------------------------------
    with tabs[1]:
        tipo = t.get("tipo")
        is_groups = tipo in ("G2x4", "G3x4", "G4x4")
        is_updown = tipo == "UPDOWN"

        if not t.get("rounds"):
            st.info("Gere as jornadas na aba Configuração.")
        else:
            if is_updown:
                st.markdown("### Distribuição atual (Jornada 1)")
                rounds_map_local = {int(r.get("n", 0)): r for r in t.get("rounds", [])}
                r1_local = rounds_map_local.get(1, {"games": []})
                courts_ord_local = order_courts_desc(t.get("courts", []))
                court_idx_map_local = {
                    c: i for i, c in enumerate(courts_ord_local)
                }
                games_sorted_local = sorted(
                    r1_local.get("games", []),
                    key=lambda g: court_idx_map_local.get(g.get("court", ""), 9999),
                )
                for gm in games_sorted_local:
                    st.markdown(
                        f"**{gm.get('court','?')}**  \n"
                        f"{gm.get('team_a','?')} vs {gm.get('team_b','?')}"
                    )

                if st.button("Gerar outra configuração inicial", key="regen_updown_round1"):
                    ok_layout, msg_layout = regenerate_updown_round1_distribution(t)
                    save_tournament(t)
                    if ok_layout:
                        st.success(msg_layout)
                        st.rerun()
                    else:
                        st.error(msg_layout)

                st.markdown("---")

            if is_groups:
                st.markdown("### Fase de Grupos — Classificações em tempo real")
                tables_by_group = compute_group_tables_live(t)
                for g in sorted(tables_by_group.keys()):
                    st.markdown(f"#### Grupo {g}")
                    df_grp = tables_by_group[g].copy().reset_index(drop=True)
                    num_rows = max(len(df_grp), 1)
                    dyn_height = min(60 + num_rows * 36, 400)
                    st.dataframe(
                        df_grp,
                        use_container_width=True,
                        hide_index=True,
                        height=dyn_height,
                    )
                st.markdown("---")

            st.markdown("### Inserção de Resultados")

            rounds_sorted = sorted(
                t.get("rounds", []), key=lambda R: int(R.get("n", 0))
            )
            for rnd in rounds_sorted:
                jn = int(rnd.get("n", 0))
                st.markdown(f"#### Jornada {jn}")

                jornada_scores = []

                for i, m in enumerate(rnd["games"]):
                    c1, c2, c3, c4 = st.columns([3, 2, 2, 1])
                    with c1:
                        if m.get("phase") == "finals" and m.get("placement"):
                            label = f"**{m.get('placement')}** — {m['team_a']} vs {m['team_b']}"
                        else:
                            label = f"**{m['team_a']}** vs **{m['team_b']}**"
                            if m.get("phase") == "groups":
                                label += f"  ·  Grupo {m.get('group','-')}"
                        st.write(label)
                    with c2:
                        st.write(f"Campo: {m.get('court', '-')}")
                    with c3:
                        key = f"score_{t['id']}_{jn}_{i}"
                        new_score = st.text_input(
                            "Resultado (ex.: 4-1)",
                            value=m.get("score", ""),
                            key=key,
                        )
                        jornada_scores.append((i, new_score))
                    with c4:
                        if m.get("score"):
                            st.caption("✅ Guardado")

                if st.button(
                    f"Guardar resultados da jornada {jn}",
                    key=f"save_round_{t['id']}_{jn}",
                ):
                    for idx_jogo, score_val in jornada_scores:
                        rnd["games"][idx_jogo]["score"] = score_val.strip()

                    if is_updown:
                        _updown_build_next_round(t, jn)
                    elif jn == 4:
                        _recalculate_round5_from_round4(t)

                    save_tournament(t)
                    st.success(f"Resultados da jornada {jn} guardados.")
                    st.rerun()

                st.markdown("---")

            if is_groups:
                st.markdown("### Potes e Jornadas Finais")
                if st.button(
                    "Gerar/Atualizar potes (baseado nas 3 jornadas de grupos)",
                    type="primary",
                ):
                    ok, msg = _generate_finals_from_pots_and_replace(t)
                    if ok:
                        t["notices"]["jornadas"] = msg
                        save_tournament(t)
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

                rounds_map_local = {int(r["n"]): r for r in t.get("rounds", [])}
                for rn in (4, 5):
                    rfin = rounds_map_local.get(rn)
                    if rfin and any(m.get("phase") == "finals" for m in rfin.get("games", [])):
                        st.markdown(f"#### Jornada {rn} (Finais/Potes)")
                        show_lines = []
                        for j, m in enumerate(rfin["games"], start=1):
                            placement_txt = m.get("placement")
                            if placement_txt:
                                line = (
                                    f"{placement_txt}: {m['team_a']} vs {m['team_b']} "
                                    f"· Campo: {m.get('court','-')}"
                                )
                            else:
                                line = (
                                    f"J{j}: {m['team_a']} vs {m['team_b']} "
                                    f"· Campo: {m.get('court','-')}"
                                )
                            show_lines.append(line)
                        st.write("\n".join(f"- {ln}" for ln in show_lines))

    # -----------------------------------------------------
    # TAB 3: CLASSIFICAÇÃO FINAL
    # -----------------------------------------------------
    with tabs[2]:
        if t.get("tipo") == "UPDOWN":
            final_df = compute_final_classification_from_updown(t)
        else:
            final_df = compute_final_classification_from_round5(t)

        if final_df.empty:
            st.info(
                "Classificação final ainda não está definida. "
                "Introduza e guarde os resultados da última jornada."
            )
        else:
            num_rows = max(len(final_df), 1)
            dyn_height = min(60 + num_rows * 36, 500)
            st.dataframe(
                final_df,
                use_container_width=True,
                hide_index=True,
                height=dyn_height,
            )

            st.download_button(
                "Descarregar classificação final (CSV)",
                data=final_df.to_csv(index=False).encode("utf-8"),
                file_name=f"classificacao_{t['id']}.csv",
                mime="text/csv",
            )

            st.markdown("---")
            if st.button("Fechar evento e gravar no CSV", type="primary"):
                append_final_table_to_csv_if_applicable(t)
                t["state"] = "closed"
                save_tournament(t)
                st.success("Classificação final gravada e evento fechado.")

    # -----------------------------------------------------
    # TAB 4: EXPORTAR
    # -----------------------------------------------------
    with tabs[3]:
        st.download_button(
            "Exportar torneio (JSON)",
            data=json.dumps(t, ensure_ascii=False, indent=2),
            file_name=f"{t['id']}.json",
            mime="application/json",
        )
        if st.button("Eliminar este torneio", type="secondary"):
            try:
                _t_path(t["id"]).unlink()
                st.success("Eliminado.")
                st.session_state["page"] = "home"
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao eliminar: {e}")


# =========================================================
# PÁGINA DO TORNEIO "LEGADO" (CSV) + CRIAÇÃO DE EVENTO
# =========================================================
def page_tournament(t_id: str):
    inject_styles()

    torneio = next((t for t in TOURNAMENTS if t["id"] == t_id), None)
    nome = torneio["nome"] if torneio else "Torneio"

    flow_key = f"show_event_date_{t_id}"
    if flow_key not in st.session_state:
        st.session_state[flow_key] = False
    flow_active = st.session_state[flow_key]

    with st.sidebar:
        sidebar_width = "320px" if (flow_active and is_admin()) else "260px"
        st.markdown(
            f"""
            <style>
            section[data-testid="stSidebar"] {{
                width:{sidebar_width} !important;
                min-width:{sidebar_width} !important;
                max-width:{sidebar_width} !important;
            }}
            .sidebar-btn-inline .stButton > button{{
                width:auto !important;
                display:inline-block;
                white-space:nowrap;
                padding:0.4rem 0.75rem;
                font-weight:600;
            }}
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("### Navegação")
        sec = st.radio(
            "Navegação",
            options=["Ranking", "Resultados", "Estatísticas"],
            index=["Ranking", "Resultados", "Estatísticas"].index(
                st.session_state.get("sec", "Ranking")
            ),
            key="sec_radio",
            label_visibility="collapsed",
        )
        st.markdown("---")

        st.markdown("### Área do organizador")
        admin_ok = admin_login_sidebar()

        if admin_ok:
            if not flow_active:
                st.markdown('<div class="sidebar-btn-inline">', unsafe_allow_html=True)
                if st.button("+ Criar/Gerir evento", key=f"btn_open_flow_{t_id}"):
                    st.session_state[flow_key] = True
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                default_date = datetime.now().date()
                event_date = st.date_input(
                    "Selecionar data do torneio",
                    value=default_date,
                    format="DD/MM/YYYY",
                    key=f"event_date_{t_id}",
                )

                cols_action = st.columns(2)
                with cols_action[0]:
                    st.markdown('<div class="sidebar-btn-inline">', unsafe_allow_html=True)
                    if st.button("Cancelar", key=f"btn_cancel_flow_{t_id}"):
                        st.session_state[flow_key] = False
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

                with cols_action[1]:
                    st.markdown('<div class="sidebar-btn-inline">', unsafe_allow_html=True)
                    if st.button("Avançar", key=f"btn_go_event_{t_id}"):
                        ev = create_or_open_event_for_model(
                            t_id,
                            event_date.year,
                            event_date.month,
                            event_date.day,
                        )
                        st.session_state["manage_id"] = ev["id"]
                        st.session_state["page"] = "manage"
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

        #else:
            #st.info("Área reservada ao organizador.")

        st.markdown("---")

        st.markdown('<div class="sidebar-btn-inline">', unsafe_allow_html=True)
        if st.button("← Voltar à Home"):
            st.session_state["torneio_sel"] = None
            st.session_state["page"] = "home"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    st.session_state["sec"] = sec
    header(nome, "Ranking, resultados e estatísticas.")

    if t_id in ("F5.2_20SEX", "M5.2_1830DOM"):
        df_raw = load_data(get_data_file_for_model(t_id))
        expanded = expand_results(df_raw)
    else:
        expanded = pd.DataFrame(
            columns=[
                "Year","Month","Day","Data","Team","Player","Position","Points",
            ]
        )

    if sec == "Ranking":
        top3, tabela_restante = compute_ranking_with_momentum(expanded)

        podium_with_tooltips(top3)

        if not tabela_restante.empty:
            def _color_delta(val: str) -> str:
                if isinstance(val, str):
                    val_strip = val.strip()
                    if val_strip.startswith("▲"):
                        return "color: #3bd16f; font-weight: 700;"
                    if val_strip.startswith("▼"):
                        return "color: #ff4d4d; font-weight: 700;"
                return ""

            styled = (
                tabela_restante
                .style
                .applymap(_color_delta, subset=["Var"])
                .set_properties(subset=["Pos", "Var"], **{
                    "text-align": "center",
                    "font-weight": "600",
                })
                .format({"Média de Pontos": "{:.2f}"})
            )

            st.dataframe(
                styled,
                use_container_width=True,
                height=540,
                hide_index=True,
            )
        else:
            st.info("Ainda não existem jogadores(as) suficientes para tabela além do pódio.")

        st.download_button(
            "Descarregar ranking (CSV)",
            data=tabela_restante.to_csv(index=False).encode("utf-8"),
            file_name=f"ranking_{t_id}.csv",
            mime="text/csv",
        )

        if expanded.empty:
            st.info("Ainda não existem dados para este torneio.")

    elif sec == "Resultados":
        if expanded.empty:
            st.info("Ainda não existem resultados para este torneio.")
        else:
            st.markdown("**Introduza a data do torneio para abrir detalhes.**")
            col1, col2, col3 = st.columns(3)
            with col1:
                years = sorted(expanded["Year"].dropna().unique(), reverse=True)
                year = st.selectbox("Ano", options=years, index=0)
            with col2:
                months = sorted(
                    expanded[expanded["Year"] == year]["Month"].dropna().unique(),
                    key=lambda mm: MONTH_INDEX.get(mm, 99),
                )
                month = st.selectbox("Mês", options=months, index=0)
            with col3:
                days = sorted(
                    expanded[
                        (expanded["Year"] == year) & (expanded["Month"] == month)
                    ]["Day"]
                    .dropna()
                    .unique()
                )
                day = st.selectbox("Dia", options=days, index=0)

            filtered = expanded[
                (expanded["Year"] == year)
                & (expanded["Month"] == month)
                & (expanded["Day"] == day)
            ].copy()

            if filtered.empty:
                st.info("Sem registos para a data selecionada.")
            else:
                team_view = (
                    filtered.groupby(["Position", "Team"], dropna=True)
                    .agg(Pontos=("Points", "first"))
                    .reset_index()
                    .sort_values(by=["Position"])
                )

                podium_df = team_view.head(3).copy()
                rk_fake = pd.DataFrame(
                    {
                        "Jogador(a)": [
                            "/".join(t.split(" / ")) for t in podium_df["Team"]
                        ],
                        "Pontos Totais": podium_df["Pontos"].values,
                        "Participações": [1] * len(podium_df),
                        "Média de Pontos": podium_df["Pontos"].values,
                    }
                )
                podium_with_tooltips(rk_fake)

                restantes = (
                    team_view.iloc[3:].copy()
                    if team_view.shape[0] > 3
                    else pd.DataFrame(columns=team_view.columns)
                )
                restantes = restantes.rename(
                    columns={"Position": "Posição", "Team": "Equipa"}
                )

                if not restantes.empty:
                    st.dataframe(
                        restantes[["Posição", "Equipa", "Pontos"]],
                        use_container_width=True,
                        height=520,
                        hide_index=True,
                    )
                else:
                    st.info("Sem posições adicionais além do pódio.")

                st.download_button(
                    "Descarregar resultados (CSV)",
                    data=team_view.rename(
                        columns={"Position": "Posição", "Team": "Equipa"}
                    )
                    .to_csv(index=False)
                    .encode("utf-8"),
                    file_name=f"resultados_{t_id}_{year}_{month}_{day:02d}.csv",
                    mime="text/csv",
                )

    elif sec == "Estatísticas":
        if expanded.empty:
            st.info("Ainda não existem estatísticas para este torneio.")
        else:
            idx = players_index(expanded)

            st.markdown("#### Lista e indicadores")
            q = st.text_input("Procurar jogador(a)", key="players_search")

            df_list = idx.copy()
            if q:
                df_list = df_list[
                    df_list["Jogador(a)"].str.contains(q, case=False, na=False)
                ]
            df_list.index = range(1, len(df_list) + 1)

            st.dataframe(
                df_list,
                use_container_width=True,
                height=420,
                hide_index=True,
            )

            jogs = sorted(expanded["Player"].unique())
            sel = st.selectbox(
                "Selecionar jogador(a)",
                options=jogs,
                index=0 if jogs else None,
            )

            if sel:
                sub = expanded[expanded["Player"] == sel].copy()

                def _label_pt_short(dstr: str) -> str:
                    try:
                        dt = datetime.fromisoformat(str(dstr))
                        return f"{dt.day:02d} {MONTH_ABBR_PT[dt.month-1]} {str(dt.year)[-2:]}"
                    except Exception:
                        return str(dstr)

                serie = sub.groupby("Data")["Points"].sum().sort_index()
                labels = [_label_pt_short(x) for x in serie.index]
                cumul = serie.cumsum()

                plt.rcParams.update(
                    {
                        "figure.facecolor": "#0f1115",
                        "axes.facecolor": "#171a21",
                        "axes.edgecolor": "#2a2f3a",
                        "axes.labelcolor": "#e6e9ef",
                        "xtick.color": "#e6e9ef",
                        "ytick.color": "#e6e9ef",
                        "grid.color": "#2a2f3a",
                        "text.color": "#e6e9ef",
                    }
                )

                def _set_sparse_xticks(ax, lbls):
                    n = len(lbls)
                    if n <= 6:
                        ax.set_xticks(range(n))
                        ax.set_xticklabels(lbls, rotation=45, ha="right")
                    else:
                        step = max(1, n // 6)
                        idxs = list(range(0, n, step))
                        ax.set_xticks(idxs)
                        ax.set_xticklabels(
                            [lbls[i] for i in idxs], rotation=45, ha="right"
                        )

                g1, g2 = st.columns(2)
                with g1:
                    fig1, ax1 = plt.subplots(figsize=(5.0, 3.0), dpi=160)
                    ax1.plot(
                        range(len(serie)),
                        list(serie.values),
                        marker="o",
                        linewidth=1.8,
                    )
                    ax1.set_title(f"Pontos por torneio — {sel}", pad=8)
                    ax1.set_xlabel("Data")
                    ax1.set_ylabel("Pontos")
                    ax1.grid(alpha=0.35)
                    _set_sparse_xticks(ax1, labels)
                    st.pyplot(fig1, use_container_width=True)

                with g2:
                    fig2, ax2 = plt.subplots(figsize=(5.0, 3.0), dpi=160)
                    ax2.plot(
                        range(len(cumul)),
                        list(cumul.values),
                        marker="o",
                        linewidth=1.8,
                    )
                    ax2.set_title(f"Acumulado de pontos — {sel}", pad=8)
                    ax2.set_xlabel("Data")
                    ax2.set_ylabel("Pontos acumulados")
                    ax2.grid(alpha=0.35)
                    _set_sparse_xticks(ax2, labels)
                    st.pyplot(fig2, use_container_width=True)

            st.download_button(
                "Descarregar lista (CSV)",
                data=df_list.to_csv(index=True).encode("utf-8"),
                file_name=f"estatisticas_{t_id}.csv",
                mime="text/csv",
            )


# =========================================================
# MAIN
# =========================================================
def main():
    if "page" not in st.session_state:
        st.session_state["page"] = "home"
    if "torneio_sel" not in st.session_state:
        st.session_state["torneio_sel"] = None
    if "sec" not in st.session_state:
        st.session_state["sec"] = "Ranking"

    if st.session_state["page"] == "manage" and st.session_state.get("manage_id"):
        page_manage_tournament(st.session_state["manage_id"])
    elif not st.session_state["torneio_sel"]:
        page_home()
    else:
        page_tournament(st.session_state["torneio_sel"])


if __name__ == "__main__":
    main()



































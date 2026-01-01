import streamlit as st
import pandas as pd

from core.constants import TOURNAMENTS, MODEL_DATA_FILES
from core.styles import metric
from data.ranking import load_data, expand_results


def page_home():
    st.markdown(
        """
        <div class="hero">
            <h1>Gestão de torneios e eventos</h1>
            <p>Escolhe um torneio para entrar.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    dfs = [load_data(p) for p in MODEL_DATA_FILES.values()]
    df_raw = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame(columns=["Year","Month","Day","Position","Team"])
    df_exp = expand_results(df_raw)

    total_torneios = df_exp[["Year", "Month", "Day"]].drop_duplicates().shape[0] if not df_exp.empty else 0
    num_jogadores = df_exp["Player"].nunique() if not df_exp.empty else 0
    registos = df_exp.shape[0] if not df_exp.empty else 0

    c1, c2, c3 = st.columns(3)
    with c1: metric("Torneios", str(total_torneios))
    with c2: metric("N.º de jogadores(as)", str(num_jogadores))
    with c3: metric("Registos", str(registos))

    st.markdown(
        '<div class="panel"><div class="hdr" style="font-size:20px;">Escolher torneio</div></div>',
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
        st.button("Entrar no torneio", key="btn_enter_disabled", disabled=True, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

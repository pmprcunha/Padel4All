import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

from core.auth import admin_login_sidebar, is_admin
from core.constants import TOURNAMENTS, MONTH_INDEX, MONTH_ABBR_PT, get_data_file_for_model
from core.styles import header, podium_with_tooltips
from data.ranking import load_data, expand_results, compute_ranking, players_index, compute_ranking_with_momentum, compute_monthly_ranking_with_momentum
from tournaments.storage import create_or_open_event_for_model
from tournaments.updown import order_courts_desc


def page_tournament(t_id: str):
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
            index=["Ranking", "Resultados", "Estatísticas"].index(st.session_state.get("sec", "Ranking")),
            horizontal=False,
            label_visibility="collapsed",
        )
        st.session_state["sec"] = sec
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
                        ev = create_or_open_event_for_model(t_id, event_date.year, event_date.month, event_date.day)
                        st.session_state["manage_id"] = ev["id"]
                        st.session_state["page"] = "manage"
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown('<div class="sidebar-btn-inline">', unsafe_allow_html=True)
        if st.button("← Voltar à Home"):
            st.session_state["torneio_sel"] = None
            st.session_state["page"] = "home"
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    header(nome, "Ranking, resultados e estatísticas.")

    if t_id in ("F5.2_20SEX", "M5.2_1830DOM"):
        df_raw = load_data(get_data_file_for_model(t_id))
        expanded = expand_results(df_raw)
    else:
        expanded = pd.DataFrame(columns=["Year","Month","Day","Data","Team","Player","Position","Points"])

    if sec == "Ranking":
        if expanded.empty:
            st.info("Ainda não existem dados para este torneio.")
            return

        tab_global, tab_month = st.tabs(["Ranking Global", "Ranking Mensal"])

        # --------------------------
        # TAB 1 — RANKING GLOBAL
        # --------------------------
        with tab_global:
            top3, tabela_restante = compute_ranking_with_momentum(expanded)
            podium_with_tooltips(top3)

            if not tabela_restante.empty:
                def _color_delta(val: str) -> str:
                    if isinstance(val, str):
                        v = val.strip()
                        if v.startswith("▲"):
                            return "color: #3bd16f; font-weight: 700;"
                        if v.startswith("▼"):
                            return "color: #ff4d4d; font-weight: 700;"
                    return ""

                styled = (
                    tabela_restante.style
                    .applymap(_color_delta, subset=["Var"])
                    .set_properties(
                        subset=["Pos", "Var"],
                        **{"text-align": "center", "font-weight": "600"},
                    )
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

            ranking_full = pd.concat(
                [
                    top3.assign(Pos=[1, 2, 3], Var=["", "", ""])[
                        ["Pos", "Var", "Jogador(a)", "Pontos Totais", "Participações", "Média de Pontos"]
                    ],
                    tabela_restante[
                        ["Pos", "Var", "Jogador(a)", "Pontos Totais", "Participações", "Média de Pontos"]
                    ],
                ],
                ignore_index=True,
            )

            st.download_button(
                "Descarregar ranking",
                data=ranking_full.to_csv(index=False).encode("utf-8"),
                file_name=f"ranking_{t_id}.csv",
                mime="text/csv",
            )

        # --------------------------
        # TAB 2 — RANKING MENSAL
        # --------------------------
        with tab_month:
            # Selecionar Ano e Mês disponíveis neste torneio
            col1, col2 = st.columns(2)
            with col1:
                years = sorted(expanded["Year"].dropna().unique(), reverse=True)
                year_sel = st.selectbox("Ano", options=years, index=0, key=f"rk_year_{t_id}")
            with col2:
                months = sorted(
                    expanded[expanded["Year"] == year_sel]["Month"].dropna().unique(),
                    key=lambda mm: MONTH_INDEX.get(mm, 99),
                )
                default_month_idx = len(months) - 1 if months else 0
                month_sel = st.selectbox(
                    "Mês",
                    options=months,
                    index=default_month_idx,
                    key=f"rk_month_{t_id}",
                )

            # ⬇️ DAQUI PARA BAIXO FICA *DENTRO* DO TAB MENSAL
            # Filtrar apenas aquele ano/mês (para validação rápida)
            expanded_month = expanded[
                (expanded["Year"] == year_sel) & (expanded["Month"] == month_sel)
            ].copy()

            if expanded_month.empty:
                st.info("Sem dados para o ano/mês selecionado.")
            else:
                # ✅ Ranking mensal com Var (vs mês anterior disponível)
                top3_m, restante_m = compute_monthly_ranking_with_momentum(
                    expanded, year_sel, month_sel
                )

                # pódio mensal
                podium_with_tooltips(top3_m)

                # tabela (4.º lugar em diante) com Var
                if not restante_m.empty:
                    def _color_delta(val: str) -> str:
                        if isinstance(val, str):
                            v = val.strip()
                            if v.startswith("▲"):
                                return "color: #3bd16f; font-weight: 700;"
                            if v.startswith("▼"):
                                return "color: #ff4d4d; font-weight: 700;"
                        return ""

                    styled_m = (
                        restante_m
                        .style
                        .applymap(_color_delta, subset=["Var"])
                        .set_properties(
                            subset=["Pos", "Var"],
                            **{
                                "text-align": "center",
                                "font-weight": "600",
                            },
                        )
                        .format({"Média de Pontos": "{:.2f}"})
                    )

                    st.dataframe(
                        styled_m,
                        use_container_width=True,
                        height=540,
                        hide_index=True,
                    )
                else:
                    st.info("Sem posições adicionais além do pódio para este mês.")

                # export CSV mensal (com Pos e Var)
                ranking_full_m = pd.concat(
                    [
                        top3_m.assign(Pos=[1, 2, 3], Var=["", "", ""])[
                            ["Pos", "Var", "Jogador(a)", "Pontos Totais", "Participações", "Média de Pontos"]
                        ],
                        restante_m[
                            ["Pos", "Var", "Jogador(a)", "Pontos Totais", "Participações", "Média de Pontos"]
                        ],
                    ],
                    ignore_index=True,
                )

                st.download_button(
                    f"Descarregar ranking mensal ({month_sel} {year_sel})",
                    data=ranking_full_m.to_csv(index=False).encode("utf-8"),
                    file_name=f"ranking_mensal_{t_id}_{year_sel}_{month_sel}.csv",
                    mime="text/csv",
                )

    elif sec == "Resultados":
        if expanded.empty:
            st.info("Ainda não existem resultados para este torneio.")
            return

        st.markdown("**Introduza a data do torneio para abrir detalhes.**")
        col1, col2, col3 = st.columns(3)
        with col1:
            years = sorted(expanded["Year"].dropna().unique(), reverse=True)
            year = st.selectbox("Ano", options=years, index=0)
        with col2:
            months = sorted(expanded[expanded["Year"] == year]["Month"].dropna().unique(), key=lambda mm: MONTH_INDEX.get(mm, 99))
            month = st.selectbox("Mês", options=months, index=0)
        with col3:
            days = sorted(expanded[(expanded["Year"] == year) & (expanded["Month"] == month)]["Day"].dropna().unique())
            day = st.selectbox("Dia", options=days, index=0)

        filtered = expanded[(expanded["Year"] == year) & (expanded["Month"] == month) & (expanded["Day"] == day)].copy()
        if filtered.empty:
            st.info("Sem registos para a data selecionada.")
            return

        team_view = (
            filtered.groupby(["Position", "Team"], dropna=True)
            .agg(Pontos=("Points", "first"))
            .reset_index()
            .sort_values(by=["Position"])
        )

        podium_df = team_view.head(3).copy()
        rk_fake = pd.DataFrame(
            {
                "Jogador(a)": ["/".join(t.split(" / ")) for t in podium_df["Team"]],
                "Pontos Totais": podium_df["Pontos"].values,
                "Participações": [1] * len(podium_df),
                "Média de Pontos": podium_df["Pontos"].values,
            }
        )
        podium_with_tooltips(rk_fake)

        restantes = team_view.iloc[3:].copy() if team_view.shape[0] > 3 else pd.DataFrame(columns=team_view.columns)
        restantes = restantes.rename(columns={"Position": "Posição", "Team": "Equipa"})

        if not restantes.empty:
            st.dataframe(restantes[["Posição", "Equipa", "Pontos"]], use_container_width=True, height=520, hide_index=True)
        else:
            st.info("Sem posições adicionais além do pódio.")

        st.download_button(
            "Descarregar resultados",
            data=team_view.rename(columns={"Position": "Posição", "Team": "Equipa"}).to_csv(index=False).encode("utf-8"),
            file_name=f"resultados_{t_id}_{year}_{month}_{day:02d}.csv",
            mime="text/csv",
        )

    elif sec == "Estatísticas":
        if expanded.empty:
            st.info("Ainda não existem estatísticas para este torneio.")
            return

        idx = players_index(expanded)
        st.markdown("#### Lista e indicadores")
        q = st.text_input("Procurar jogador(a)", key="players_search")

        df_list = idx.copy()
        if q:
            df_list = df_list[df_list["Jogador(a)"].str.contains(q, case=False, na=False)]
        df_list.index = range(1, len(df_list) + 1)

        st.dataframe(df_list, use_container_width=True, height=420, hide_index=True)

        jogs = sorted(expanded["Player"].unique())
        sel = st.selectbox("Selecionar jogador(a)", options=jogs, index=0 if jogs else None)

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
                    ax.set_xticklabels([lbls[i] for i in idxs], rotation=45, ha="right")

            g1, g2 = st.columns(2)
            with g1:
                fig1, ax1 = plt.subplots(figsize=(5.0, 3.0), dpi=160)
                ax1.plot(range(len(serie)), list(serie.values), marker="o", linewidth=1.8)
                ax1.set_title(f"Pontos por torneio — {sel}", pad=8)
                ax1.set_xlabel("Data")
                ax1.set_ylabel("Pontos")
                ax1.grid(alpha=0.35)
                _set_sparse_xticks(ax1, labels)
                st.pyplot(fig1, use_container_width=True)

            with g2:
                fig2, ax2 = plt.subplots(figsize=(5.0, 3.0), dpi=160)
                ax2.plot(range(len(cumul)), list(cumul.values), marker="o", linewidth=1.8)
                ax2.set_title(f"Acumulado de pontos — {sel}", pad=8)
                ax2.set_xlabel("Data")
                ax2.set_ylabel("Pontos acumulados")
                ax2.grid(alpha=0.35)
                _set_sparse_xticks(ax2, labels)
                st.pyplot(fig2, use_container_width=True)

        st.download_button(
            "Descarregar lista",
            data=df_list.to_csv(index=True).encode("utf-8"),
            file_name=f"estatisticas_{t_id}.csv",
            mime="text/csv",
        )

import streamlit as st
import pandas as pd

from core.auth import is_admin, get_admin_password
from core.constants import ALL_COURTS, TOURNEY_TYPES, get_data_file_for_model
from core.styles import header
from data.ranking import load_data, expand_results
from tournaments.csv_legacy import append_final_table_to_csv_if_applicable
from tournaments.groups import (
    compute_group_tables_live,
    generate_finals_from_pots_and_replace,
    recalculate_round5_from_round4,
    compute_final_classification_from_round5,
)
from tournaments.seeding import seed_pairs, pair_key, players_points_map
from tournaments.scheduling import round_robin_pairs, group_distribution, assign_courts
from tournaments.storage import _t_path, load_tournament, save_tournament
from tournaments.updown import (
    order_courts_desc,
    generate_updown_rounds,
    regenerate_updown_round1_distribution,
    updown_build_next_round,
    compute_final_classification_from_updown,
)


def render_pairs_editor(t: dict, tid: str, known_players: list[str], pmap: dict[str, int]) -> None:
    expected_pairs = int(t.get("expected_pairs") or 0)

    if not t.get("tipo"):
        st.info("Defina o tipo de torneio no passo 1 para listar as duplas.")
        return

    if expected_pairs <= 0:
        st.info("Defina o número de duplas e guarde o tipo no passo 1.")
        return

    existing = (
        sorted(t.get("pairs", []), key=lambda x: (-x.get("seed_pts", 0), x.get("name", "")))
        if t.get("pairs") else []
    )

    rows = [{"Jogador A": "", "Jogador B": ""} for _ in range(expected_pairs)]
    for i in range(min(len(existing), expected_pairs)):
        rows[i]["Jogador A"] = existing[i].get("a", "")
        rows[i]["Jogador B"] = existing[i].get("b", "")

    df_pairs = pd.DataFrame(rows)
    st.caption(f"Duplas a preencher: **{expected_pairs}**")

    with st.form(key=f"form_pairs_{tid}"):
        edited = st.data_editor(
            df_pairs,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            column_config={
                "Jogador A": st.column_config.SelectboxColumn(
                    "Jogador A", options=[""] + list(known_players), required=False, help="Seleciona da lista."
                ),
                "Jogador B": st.column_config.SelectboxColumn(
                    "Jogador B", options=[""] + list(known_players), required=False, help="Seleciona da lista."
                ),
            },
        )
        save_pairs = st.form_submit_button("Guardar duplas", type="primary")

    if not save_pairs:
        return

    full_pairs: list[tuple[str, str]] = []
    for _, r in edited.iterrows():
        a = str(r.get("Jogador A", "")).strip()
        b = str(r.get("Jogador B", "")).strip()
        if a or b:
            if not a or not b:
                st.error("Há linhas incompletas. Preenche A e B em todas as duplas usadas.")
                return
            full_pairs.append((a, b))

    if len(full_pairs) != expected_pairs:
        st.error(f"Preencha exatamente **{expected_pairs}** duplas completas (tem {len(full_pairs)}).")
        return

    pairs_to_keep = []
    for a, b in full_pairs:
        seed_pts = int(pmap.get(a, 0) + pmap.get(b, 0))
        pairs_to_keep.append({"a": a, "b": b, "name": pair_key(a, b), "seed_pts": seed_pts})

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

    t.setdefault("notices", {})
    t["notices"]["duplas"] = f"{len(t['pairs'])} duplas guardadas com sucesso."
    save_tournament(t)
    st.success(t["notices"]["duplas"])
    st.rerun()


def render_round_results_editor(t: dict, rnd: dict, is_groups: bool, is_updown: bool) -> None:
    jn = int(rnd.get("n", 0))
    games = rnd.get("games", []) or []
    if not games:
        st.info("Sem jogos nesta jornada.")
        return

    rows = []
    for i, m in enumerate(games):
        score_now = (m.get("score") or "").strip()
        rows.append(
            {
                "Jogo": i + 1,
                "Fase": m.get("phase", ""),
                "Grupo": m.get("group", "") if m.get("phase") == "groups" else "",
                "Placement": m.get("placement", "") if m.get("phase") == "finals" else "",
                "Equipa A": m.get("team_a", ""),
                "Equipa B": m.get("team_b", ""),
                "Campo": m.get("court", ""),
                "Resultado": score_now,
                "Guardado": "✅" if score_now else "",
            }
        )

    df = pd.DataFrame(rows)

    with st.form(key=f"form_round_{t['id']}_{jn}"):
        edited = st.data_editor(
            df,
            hide_index=True,
            use_container_width=True,
            num_rows="fixed",
            disabled=["Jogo","Fase","Grupo","Placement","Equipa A","Equipa B","Campo","Guardado"],
            column_config={
                "Resultado": st.column_config.TextColumn("Resultado (ex.: 4-1)", help="Formato X-Y (ex.: 6-4). Evita empates."),
                "Guardado": st.column_config.TextColumn(""),
            },
        )
        submitted = st.form_submit_button(f"Guardar resultados da jornada {jn}", type="primary")

    if not submitted:
        return

    new_scores = edited["Resultado"].fillna("").tolist()
    for i, score_val in enumerate(new_scores):
        games[i]["score"] = str(score_val).strip()

    if is_updown:
        updown_build_next_round(t, jn)
    elif jn == 4:
        recalculate_round5_from_round4(t)

    save_tournament(t)
    st.success(f"Resultados da jornada {jn} guardados.")
    st.rerun()


def page_manage_tournament(tid: str):
    if not is_admin():
        header("Área reservada", "Apenas o organizador pode gerir eventos.")
        pwd = st.text_input("Código de organizador", type="password", key="admin_pwd_manage")
        if st.button("Entrar como organizador", key="btn_admin_login_manage"):
            if pwd and pwd == get_admin_password():
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

    t = load_tournament(tid)

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

    with tabs[0]:
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
                exp_def = t.get("expected_pairs") or max(4, len(t.get("pairs", [])) if t.get("pairs") else 8)
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
                t["expected_pairs"] = int(fixed_teams) if fixed_teams else int(expected_pairs_input)

                pairs_sorted = sorted(t.get("pairs", []), key=lambda x: (-x.get("seed_pts", 0), x.get("name", "")))
                if len(pairs_sorted) > t["expected_pairs"]:
                    t["pairs"] = pairs_sorted[: t["expected_pairs"]]

                def _required_courts(tipo: str, num_pairs: int) -> tuple[int, int]:
                    if tipo == "LIGA6": return (3, 3)
                    if tipo == "G2x4": return (4, 4)
                    if tipo == "G3x4": return (6, 6)
                    if tipo == "G4x4": return (8, 8)
                    if tipo == "UPDOWN":
                        mx = max(1, num_pairs // 2)
                        return (mx, mx)
                    return (0, 0)

                min_c, max_c = _required_courts(t["tipo"], len(t.get("pairs", [])))
                if t["tipo"] == "UPDOWN":
                    t["courts"] = order_courts_desc(ALL_COURTS)[:max_c]
                else:
                    t["courts"] = order_courts_desc(ALL_COURTS)[:min_c]

                t["notices"]["tipo"] = f"Tipo de torneio guardado: {TOURNEY_TYPES[t['tipo']]['label']}."
                save_tournament(t)
                st.success(t["notices"]["tipo"])
                st.rerun()

        st.markdown("---")

        st.markdown("#### 2) Definir duplas/equipas")
        if t["notices"].get("duplas"):
            st.success(t["notices"]["duplas"])

        data_file_cfg = get_data_file_for_model(t.get("model", ""))
        df_raw = load_data(data_file_cfg)
        exp_df = expand_results(df_raw)
        pmap = players_points_map(exp_df)
        known_players = sorted(exp_df["Player"].dropna().unique()) if not exp_df.empty else []

        render_pairs_editor(t=t, tid=tid, known_players=known_players, pmap=pmap)

        st.markdown("---")

        st.markdown("#### 3) Selecionar campos")
        if t["notices"].get("campos"):
            st.success(t["notices"]["campos"])

        if not t.get("tipo"):
            st.info("Defina o tipo de torneio no passo 1).")
        else:
            n_pairs = len(t.get("pairs", []))
            tipo_lbl = TOURNEY_TYPES[t["tipo"]]["label"]

            if t["tipo"] == "LIGA6": required = 3
            elif t["tipo"] == "G2x4": required = 4
            elif t["tipo"] == "G3x4": required = 6
            elif t["tipo"] == "G4x4": required = 8
            else:
                expected_pairs_local = int(t.get("expected_pairs") or n_pairs)
                required = max(1, expected_pairs_local // 2)

            help_txt = f"{tipo_lbl}: escolha **exatamente {required}** campos." if t["tipo"] != "UPDOWN" else (
                f"{tipo_lbl}: escolha **exatamente {required}** campos (2 duplas por campo)."
            )

            sel_courts = st.multiselect(help_txt, options=ALL_COURTS, default=t.get("courts", []), placeholder="Escolher opções")
            valid = len(sel_courts) == required

            if st.button("Guardar campos", disabled=not valid):
                if not valid:
                    st.error("Seleção inválida de campos.")
                else:
                    t["courts"] = order_courts_desc(sel_courts) if t["tipo"] == "UPDOWN" else sel_courts
                    t["notices"]["campos"] = f"Campos guardados: {', '.join(t['courts'])}."
                    save_tournament(t)
                    st.success(t["notices"]["campos"])
                    st.rerun()

        st.markdown("---")

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
                    st.error(f"Este formato UP & DOWN requer {t['expected_pairs']} duplas (atualmente {len(t.get('pairs', []))}).")
                    st.stop()

                expected_pairs_local = int(t["expected_pairs"])
                half = max(1, expected_pairs_local // 2)
                if len(t.get("courts", [])) != half:
                    st.error(f"Selecione exatamente {half} campos para {expected_pairs_local} duplas.")
                    st.stop()
            else:
                if not teams_needed or len(t.get("pairs", [])) != teams_needed:
                    st.error(f"Este formato requer {teams_needed} duplas (atualmente {len(t.get('pairs', []))}).")
                    st.stop()

                req_map = {"LIGA6": 3, "G2x4": 4, "G3x4": 6, "G4x4": 8}
                if t["tipo"] in req_map and len(t.get("courts", [])) != req_map[t["tipo"]]:
                    st.error(f"Selecione exatamente {req_map[t['tipo']]} campos.")
                    st.stop()

            exp_df_now = expand_results(load_data(get_data_file_for_model(t.get("model", ""))))
            pmap_now = players_points_map(exp_df_now)
            pairs_seeded = seed_pairs([(p["a"], p["b"]) for p in t.get("pairs", [])], pmap_now)
            names = [pair_key(a, b) for a, b, _ in pairs_seeded]

            if t["tipo"] == "LIGA6":
                rr = round_robin_pairs(6)
                rounds = []
                for i, jogos in enumerate(rr, start=1):
                    ab = assign_courts(jogos, t["courts"])
                    rounds.append(
                        {"n": i, "games": [{"team_a": names[a], "team_b": names[b], "court": c, "score": ""} for a, b, c in ab]}
                    )
                t["rounds"] = rounds
                t["matches"] = sum([r["games"] for r in t.get("rounds", [])], [])
                t["state"] = "scheduled"

            elif t["tipo"] in ("G2x4", "G3x4", "G4x4"):
                G, S = tt["groups"]
                dist = group_distribution(pairs_seeded, G, S, t["tipo"])
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
                            matches.append(
                                {
                                    "phase": "groups",
                                    "group": gname,
                                    "round": r_i,
                                    "team_a": A,
                                    "team_b": B,
                                    "court": courts_for_group[j % len(courts_for_group)],
                                    "score": "",
                                }
                            )

                t["rounds"] = []
                group_rr_len = len(round_robin_pairs(S))
                for r_i in range(1, group_rr_len + 1):
                    gs = [m for m in matches if m["phase"] == "groups" and m["round"] == r_i]
                    t["rounds"].append({"n": r_i, "games": gs})

                t["rounds"].append({"n": group_rr_len + 1, "games": []})
                t["rounds"].append({"n": group_rr_len + 2, "games": []})
                t["matches"] = sum([r["games"] for r in t.get("rounds", [])], [])
                t["state"] = "scheduled"

            elif t["tipo"] == "UPDOWN":
                generate_updown_rounds(t)

            t["notices"]["jornadas"] = "Jornadas geradas e guardadas com sucesso."
            save_tournament(t)
            st.success(t["notices"]["jornadas"])
            st.rerun()

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
                court_idx_map_local = {c: i for i, c in enumerate(courts_ord_local)}
                games_sorted_local = sorted(
                    r1_local.get("games", []),
                    key=lambda g: court_idx_map_local.get(g.get("court", ""), 9999),
                )
                for gm in games_sorted_local:
                    st.markdown(f"**{gm.get('court','?')}**  \n{gm.get('team_a','?')} vs {gm.get('team_b','?')}")

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
                    dyn_height = min(60 + max(len(df_grp), 1) * 36, 400)
                    st.dataframe(df_grp, use_container_width=True, hide_index=True, height=dyn_height)
                st.markdown("---")

            st.markdown("### Inserção de Resultados")
            rounds_sorted = sorted(t.get("rounds", []), key=lambda R: int(R.get("n", 0)))
            for rnd in rounds_sorted:
                jn = int(rnd.get("n", 0))
                st.markdown(f"#### Jornada {jn}")
                render_round_results_editor(t=t, rnd=rnd, is_groups=is_groups, is_updown=is_updown)
                st.markdown("---")

            if is_groups:
                st.markdown("### Potes e Jornadas Finais")
                if st.button("Gerar/Atualizar potes (baseado nas 3 jornadas de grupos)", type="primary"):
                    ok, msg = generate_finals_from_pots_and_replace(t)
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
                                line = f"{placement_txt}: {m['team_a']} vs {m['team_b']} · Campo: {m.get('court','-')}"
                            else:
                                line = f"J{j}: {m['team_a']} vs {m['team_b']} · Campo: {m.get('court','-')}"
                            show_lines.append(line)
                        st.write("\n".join(f"- {ln}" for ln in show_lines))

    with tabs[2]:
        final_df = compute_final_classification_from_updown(t) if t.get("tipo") == "UPDOWN" else compute_final_classification_from_round5(t)

        if final_df.empty:
            st.info("Classificação final ainda não está definida. Introduza e guarde os resultados da última jornada.")
        else:
            dyn_height = min(60 + max(len(final_df), 1) * 36, 500)
            st.dataframe(final_df, use_container_width=True, hide_index=True, height=dyn_height)

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

    with tabs[3]:
        import json
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

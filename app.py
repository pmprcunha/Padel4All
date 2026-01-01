import streamlit as st

from core.styles import inject_styles
from ui.home import page_home
from ui.manage import page_manage_tournament
from ui.tournament import page_tournament


def _set_page_config():
    st.set_page_config(
        page_title="Gestão de torneios e eventos",
        page_icon="▣",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def _init_session():
    if "page" not in st.session_state:
        st.session_state["page"] = "home"
    if "torneio_sel" not in st.session_state:
        st.session_state["torneio_sel"] = None
    if "sec" not in st.session_state:
        st.session_state["sec"] = "Ranking"


def main():
    _set_page_config()
    _init_session()
    inject_styles()

    if st.session_state["page"] == "manage" and st.session_state.get("manage_id"):
        page_manage_tournament(st.session_state["manage_id"])
        return

    if not st.session_state["torneio_sel"]:
        page_home()
        return

    page_tournament(st.session_state["torneio_sel"])


if __name__ == "__main__":
    main()




































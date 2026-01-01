import os
import streamlit as st


def get_admin_password() -> str:
    # 1) Streamlit Cloud secrets
    try:
        pwd = st.secrets.get("ADMIN_PASSWORD")
        if pwd:
            return str(pwd)
    except Exception:
        pass

    # 2) variável de ambiente
    env_pwd = os.environ.get("PADEL4ALL_ADMIN_PASSWORD")
    if env_pwd:
        return str(env_pwd)

    # 3) fallback
    return "padel4all"


def is_admin() -> bool:
    return bool(st.session_state.get("is_admin", False))


def admin_login_sidebar() -> bool:
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
        if pwd and pwd == get_admin_password():
            st.session_state["is_admin"] = True
            st.success("Sessão de organizador ativa.")
            st.rerun()
        else:
            st.error("Código inválido.")
    return is_admin()

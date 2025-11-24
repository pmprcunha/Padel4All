# app.py
import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

DB_PATH = "events.db"

def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def init_db():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        start_date TEXT,
        end_date TEXT,
        location TEXT,
        capacity INTEGER,
        format TEXT,
        registration_deadline TEXT,
        created_at TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS registrations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id INTEGER,
        name TEXT,
        email TEXT,
        team_name TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def add_event(title, description, start_date, end_date, location, capacity, fmt, reg_deadline):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
    INSERT INTO events (title, description, start_date, end_date, location, capacity, format, registration_deadline, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, description, start_date, end_date, location, capacity, fmt, reg_deadline, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def get_events():
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM events ORDER BY start_date", conn)
    conn.close()
    return df

def add_registration(event_id, name, email, team_name):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM registrations WHERE event_id = ?", (event_id,))
    count = cur.fetchone()[0]
    cur.execute("SELECT capacity FROM events WHERE id = ?", (event_id,))
    cap = cur.fetchone()
    if cap is not None:
        cap = cap[0]
        if cap is not None and cap > 0 and count >= cap:
            conn.close()
            return False, "Capacidade do evento atingida."
    cur.execute("""
    INSERT INTO registrations (event_id, name, email, team_name, created_at)
    VALUES (?, ?, ?, ?, ?)
    """, (event_id, name, email, team_name, datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()
    return True, "Inscrição registada com sucesso."

def get_registrations(event_id):
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM registrations WHERE event_id = ?", conn, params=(event_id,))
    conn.close()
    return df

# --- App UI ---
st.set_page_config(page_title="Gestor de Eventos - Protótipo", layout="wide")
init_db()

st.sidebar.title("Menu")
page = st.sidebar.selectbox("Ir para", ["Dashboard", "Criar Evento", "Registar Jogador", "Gerir Evento"])

if page == "Dashboard":
    st.header("Dashboard")
    events = get_events()
    st.subheader("Eventos")
    st.dataframe(events if not events.empty else pd.DataFrame(columns=["Nenhum evento criado"]))
    st.write("Dica: vai a 'Criar Evento' para adicionar um evento.")

elif page == "Criar Evento":
    st.header("Criar Evento")
    with st.form("form_event"):
        title = st.text_input("Título")
        description = st.text_area("Descrição")
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("Data de início")
            end_date = st.date_input("Data de fim")
        with col2:
            location = st.text_input("Local")
            capacity = st.number_input("Capacidade (0 = ilimitado)", min_value=0, value=0)
        fmt = st.selectbox("Formato", ["Round-Robin", "Eliminação", "Grupos"])
        reg_deadline = st.date_input("Data limite de inscrição")
        submitted = st.form_submit_button("Criar evento")
    if submitted:
        add_event(title, description, start_date.isoformat(), end_date.isoformat(), location, capacity, fmt, reg_deadline.isoformat())
        st.success("Evento criado com sucesso!")

elif page == "Registar Jogador":
    st.header("Registar Jogador")
    events = get_events()
    if events.empty:
        st.info("Ainda não há eventos. Cria um evento primeiro.")
    else:
        ev_map = {f"{row['id']} - {row['title']} ({row['start_date']})": row['id'] for _, row in events.iterrows()}
        chosen = st.selectbox("Escolhe evento", list(ev_map.keys()))
        name = st.text_input("Nome")
        email = st.text_input("Email")
        team = st.text_input("Nome da equipa (opcional)")
        if st.button("Registar"):
            success, msg = add_registration(ev_map[chosen], name, email, team)
            if success:
                st.success(msg)
            else:
                st.error(msg)

elif page == "Gerir Evento":
    st.header("Gerir Evento")
    events = get_events()
    if events.empty:
        st.info("Sem eventos para gerir.")
    else:
        ev_map = {f"{row['id']} - {row['title']}": row['id'] for _, row in events.iterrows()}
        sel = st.selectbox("Seleciona evento", list(ev_map.keys()))
        event_id = ev_map[sel]
        st.subheader("Inscrições")
        regs = get_registrations(event_id)
        if regs.empty:
            st.write("Sem inscrições ainda.")
        else:
            st.dataframe(regs)
            df = regs.copy()
            csv = df.to_csv(index=False).encode('utf-8')
            st.download_button("Exportar inscrições (CSV)", data=csv, file_name=f"registrations_event_{event_id}.csv", mime="text/csv")

st.markdown("---")
st.caption("Protótipo mínimo — serve para testar fluxo de criar evento e gerir inscrições.")

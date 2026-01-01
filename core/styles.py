import streamlit as st
import pandas as pd


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

        @media (max-width: 768px){
          :root{ --space:12px; --btn-h:64px; }
          .hdr{font-size:20px}
          .sub{font-size:12px}
          .hero{padding:16px;border-radius:16px}
          .hero h1{font-size:22px}
          .metric .val{font-size:22px}
          .panel{padding:14px;border-radius:14px}
          .select-card{padding:14px;border-radius:14px}
          input, textarea{font-size:16px !important;}
          #home-row + div{gap:12px;}
          #home-row + div [data-testid="column"] .stButton>button{
            border-radius:14px;padding:14px 14px;font-size:15px;
          }
          section[data-testid="stSidebar"]{
            width:auto !important;min-width:auto !important;max-width:auto !important;
          }
          .stDataFrame{max-height:420px;}
        }
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

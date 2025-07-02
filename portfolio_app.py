import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from curl_cffi.requests.exceptions import HTTPError

st.set_page_config(page_title="Mein Portfolio Tracker", layout="wide")

st.markdown("""
<style>
  .block-container { max-width:100% !important; padding:1rem; }
  table.dataframe { width:100% !important; }
  table.dataframe th, table.dataframe td { min-width:120px; }
  th.row_heading.level0, td.blank { display:none !important; }
</style>
""", unsafe_allow_html=True)

USERNAME = st.secrets["credentials"]["username"]
PASSWORD = st.secrets["credentials"]["password"]

# ───────────── Login-Maske (nur wenn NICHT eingeloggt) ─────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    col1, col2, col3 = st.columns([2,1,2])
    with col2:
        with st.form("login_form", clear_on_submit=False):
            st.markdown("### Login")
            entered_user = st.text_input("Username", key="login_user")
            entered_pw = st.text_input("Passwort", type="password", key="login_pw")
            login = st.form_submit_button("Login")
            if login:
                if entered_user == USERNAME and entered_pw == PASSWORD:
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("Falscher Username oder Passwort!")
    st.stop()

# ───────────── Portfolio Tracker ─────────────
st.title("📈 Mein Portfolio Tracker")
st.button("🔄 Aktualisieren")

portfolio = st.secrets["portfolio"]

rate_data = yf.Ticker("EURUSD=X").history(period="5d")["Close"]
rate = rate_data.dropna().iloc[-1] if not rate_data.empty else 1.0

rows = []
gesamtwert_usd = 0.0
gesamtgewinn   = 0.0
today = datetime.date.today()

for ticker, info in portfolio.items():
    anzahl, einstand = info["anzahl"], info["einstand"]
    aktie = yf.Ticker(ticker)

    try:
        hist = aktie.history(period="1d")
    except HTTPError as e:
        st.warning(f"⚠️ HTTP-Fehler beim Abruf für {ticker}: {e}")
        hist = pd.DataFrame()

    if hist.empty:
        kurs, wert_usd, gewinn, entwicklung = 0.0, 0.0, -einstand * anzahl, 0.0
    else:
        kurs = float(hist["Close"][0])
        wert_usd = kurs * anzahl
        gewinn = wert_usd - einstand * anzahl
        entwicklung = (kurs - einstand) / einstand * 100

     try:
        cal = aktie.calendar
        ne = cal.loc["Earnings Date"]
        if len(ne) == 0:
        next_earn = None
    elif hasattr(ne.iloc[0], "date") and (len(ne) == 1 or pd.isna(ne.iloc[1])):
        # Einzeltermin
        next_earn = ne.iloc[0].date()
    elif len(ne) > 1 and hasattr(ne.iloc[0], "to_pydatetime") and hasattr(ne.iloc[1], "to_pydatetime"):
        # Spanne, z.B. ["2025-07-30", "2025-08-04"]
        next_earn = f"{ne.iloc[0].strftime('%d.%m.%Y')} – {ne.iloc[1].strftime('%d.%m.%Y')}"
    else:
        next_earn = None
except Exception:
    # Fallback für einzelne Aktien mit timestamp (seltener Fall)
    info_dict = aktie.info
    ts = info_dict.get("earningsTimestamp") or info_dict.get("earningsTimestampStart")
    next_earn = datetime.datetime.fromtimestamp(ts).date() if ts else None


    gesamtwert_usd += wert_usd
    gesamtgewinn += gewinn
    wert_eur = wert_usd / rate

    rows.append({
        "Aktie": ticker,
        "Anzahl": anzahl,
        "Einstand ($)": einstand,
        "Kurs ($)": kurs,
        "Entwicklung (%)": entwicklung,
        "Gewinn/Verlust ($)": gewinn,
        "Wert ($)": wert_usd,
        "Wert (€)": wert_eur,
        "Nächste Q-Zahlen": next_earn or ""
    })

df = pd.DataFrame(rows)

def fmt_int(x): return f"{x:,.0f}".replace(",", ".")
def fmt_flt(x): return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
def fmt_pct(x): return fmt_flt(x) + " %"
def fmt_cash(x): return fmt_flt(x) + " $"
def fmt_eur(x): return fmt_flt(x) + " €"
def fmt_date(d): return d.strftime("%d.%m.%Y") if isinstance(d, datetime.date) else ""
def color_pos_neg(v): return "" if pd.isna(v) else ("color: green;" if v >= 0 else "color: red;")

styler = (
    df.style
    .hide(axis="index")
    .format({
        "Anzahl": fmt_int,
        "Einstand ($)": fmt_flt,
        "Kurs ($)": fmt_flt,
        "Entwicklung (%)": fmt_pct,
        "Gewinn/Verlust ($)": fmt_cash,
        "Wert ($)": fmt_flt,
        "Wert (€)": fmt_eur,
        "Nächste Q-Zahlen": fmt_date
    })
    .applymap(color_pos_neg, subset=["Entwicklung (%)", "Gewinn/Verlust ($)"])
)

# Dynamische Höhe: 40 px für Header, ca. 35 px pro Zeile
table_height = 40 + 35 * len(df)
st.dataframe(styler, use_container_width=True, height=table_height)

# Gesamtsumme unten, klein halten
total = pd.DataFrame([{
    "Gewinn/Verlust ($)": gesamtgewinn,
    "Wert ($)": gesamtwert_usd,
    "Wert (€)": gesamtwert_usd / rate
}])
total_styler = (
    total.style
    .hide(axis="index")
    .format({
        "Gewinn/Verlust ($)": fmt_cash,
        "Wert ($)": fmt_flt,
        "Wert (€)": fmt_eur
    })
    .applymap(color_pos_neg, subset=["Gewinn/Verlust ($)"])
)
st.dataframe(total_styler, use_container_width=True, height=80)

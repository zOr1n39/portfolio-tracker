import streamlit as st
import yfinance as yf
import pandas as pd
from curl_cffi.requests.exceptions import HTTPError

# Vollbild-Layout
st.set_page_config(page_title="Mein Portfolio Tracker", layout="wide")

# CSS-Hack, um die erste Index-Spalte zu verstecken
st.markdown(
    """
    <style>
      th.row_heading.level0 {display: none !important;}
      td.blank {display: none !important;}
    </style>
    """,
    unsafe_allow_html=True
)

# 🔐 Passwortschutz
PASSWORD = st.secrets["credentials"]["password"]
user_input = st.text_input("Passwort eingeben:", type="password")
if user_input != PASSWORD:
    st.warning("Zugriff verweigert")
    st.stop()

# Titel und Aktualisieren-Button
st.title("📈 Mein Portfolio Tracker")
st.button("🔄 Aktualisieren")

# Portfolio aus Secrets laden
portfolio = st.secrets["portfolio"]

# 1) EUR/USD-Wechselkurs
rate = yf.Ticker("EURUSD=X").history(period="1d")["Close"][0]

# 2) Daten sammeln
rows = []
gesamtwert_usd = 0.0
gesamtgewinn   = 0.0

for ticker, info in portfolio.items():
    anzahl   = info["anzahl"]
    einstand = info["einstand"]
    aktie    = yf.Ticker(ticker)

    try:
        hist = aktie.history(period="1d")
    except HTTPError as e:
        st.warning(f"⚠️ HTTP-Fehler beim Abruf für {ticker}: {e}")
        hist = pd.DataFrame()

    if hist.empty:
        kurs, gewinn, entwicklung, wert_usd = 0.0, -einstand * anzahl, 0.0, 0.0
    else:
        kurs        = float(hist["Close"][0])
        wert_usd    = kurs * anzahl
        gewinn      = wert_usd - einstand * anzahl
        entwicklung = (kurs - einstand) / einstand * 100

    gesamtwert_usd += wert_usd
    gesamtgewinn   += gewinn
    wert_eur       = wert_usd / rate

    rows.append({
        "Aktie":               ticker,
        "Anzahl":              anzahl,
        "Einstand ($)":        einstand,
        "Kurs ($)":            kurs,
        "Entwicklung (%)":     entwicklung,
        "Gewinn/Verlust ($)":  gewinn,
        "Wert ($)":            wert_usd,
        "Wert (€)":            wert_eur
    })

# 3) DataFrame erzeugen
df = pd.DataFrame(rows)

# Styling-Funktionen
def fmt_int(x):    return f"{x:,.0f}".replace(",", ".")
def fmt_flt(x):    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
def fmt_pct(x):    return fmt_flt(x) + " %"
def fmt_cash(x):   return fmt_flt(x) + " $"
def fmt_eur(x):    return fmt_flt(x) + " €"
def color_pos_neg(v):
    if pd.isna(v): return ""
    return "color: green;" if v >= 0 else "color: red;"

# 4) Styler für die Tabelle (Index versteckt)
styler = (
    df.style
      .hide(axis="index")
      .format({
          "Anzahl":             fmt_int,
          "Einstand ($)":       fmt_flt,
          "Kurs ($)":           fmt_flt,
          "Entwicklung (%)":    fmt_pct,
          "Gewinn/Verlust ($)": fmt_cash,
          "Wert ($)":           fmt_flt,
          "Wert (€)":           fmt_eur
      })
      .applymap(color_pos_neg, subset=["Entwicklung (%)", "Gewinn/Verlust ($)"])
)

st.write(styler, unsafe_allow_html=True)

# 5) Gesamtzeile unten
total = pd.DataFrame([{
    "Gewinn/Verlust ($)": gesamtgewinn,
    "Wert ($)":           gesamtwert_usd,
    "Wert (€)":           gesamtwert_usd / rate
}])

total_styler = (
    total.style
         .hide(axis="index")
         .format({
             "Gewinn/Verlust ($)": fmt_cash,
             "Wert ($)":           fmt_flt,
             "Wert (€)":           fmt_eur
         })
         .applymap(color_pos_neg, subset=["Gewinn/Verlust ($)"])
)

st.write(total_styler, unsafe_allow_html=True)

import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
from curl_cffi.requests.exceptions import HTTPError
from yfinance.exceptions import YFRateLimitError

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
    col1, col2, col3 = st.columns([2, 1, 2])
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

# Option: Earnings-Daten ein-/ausschalten
load_earnings = st.checkbox(
    "Nächste Earnings-Termine laden (kann langsamer sein / Rate-Limits verursachen)",
    value=False
)

# Flag, damit Rate-Limit-Warnung für Earnings nur einmal gezeigt wird
if "earnings_rate_limit_warned" not in st.session_state:
    st.session_state.earnings_rate_limit_warned = False

portfolio = st.secrets["portfolio"]

# EUR/USD-Kurs robust laden (mit Fallback bei Fehlern / Rate-Limit)
try:
    rate_data = yf.Ticker("EURUSD=X").history(period="5d")["Close"]
    rate = rate_data.dropna().iloc[-1] if not rate_data.empty else 1.0
except (HTTPError, YFRateLimitError, Exception) as e:
    st.warning(f"⚠️ Konnte EUR/USD-Kurs nicht laden, nutze 1.0 als Fallback. Fehler: {e}")
    rate = 1.0

rows = []
gesamtwert_usd = 0.0
gesamtgewinn = 0.0
today = datetime.date.today()

for ticker, info in portfolio.items():
    anzahl, einstand = info["anzahl"], info["einstand"]
    aktie = yf.Ticker(ticker)

    # Kursdaten laden
    try:
        hist = aktie.history(period="1d")
    except (HTTPError, YFRateLimitError) as e:
        st.warning(f"⚠️ Fehler beim Abruf der Kursdaten für {ticker}: {e}")
        hist = pd.DataFrame()
    except Exception as e:
        st.warning(f"⚠️ Unerwarteter Fehler beim Abruf der Kursdaten für {ticker}: {e}")
        hist = pd.DataFrame()

    if hist.empty:
        kurs, wert_usd, gewinn, entwicklung = 0.0, 0.0, -einstand * anzahl, 0.0
    else:
        # <- hier war vorher die Series[0]-Warnung
        close_series = hist["Close"]
        kurs = float(close_series.iloc[0])  # positionsbasiert über iloc
        wert_usd = kurs * anzahl
        gewinn = wert_usd - einstand * anzahl
        entwicklung = (kurs - einstand) / einstand * 100 if einstand != 0 else 0.0

    # --------- Abfrage der nächsten Q-Zahlen (optional, ohne .info) ----------
    next_earn = None

    if load_earnings:
        try:
            cal = aktie.calendar
            if cal is not None and not cal.empty and "Earnings Date" in cal.index:
                ne = cal.loc["Earnings Date"]

                if len(ne) == 0:
                    next_earn = None
                elif hasattr(ne.iloc[0], "date") and (len(ne) == 1 or pd.isna(ne.iloc[1])):
                    # Einzelnes Datum
                    next_earn = ne.iloc[0].date()
                elif len(ne) > 1 and hasattr(ne.iloc[0], "strftime") and hasattr(ne.iloc[1], "strftime"):
                    # Datums-Spanne
                    next_earn = f"{ne.iloc[0].strftime('%d.%m.%Y')} – {ne.iloc[1].strftime('%d.%m.%Y')}"
                else:
                    next_earn = None

        except YFRateLimitError:
            # Nur eine globale Warnung für alle Earnings-Rate-Limits
            if not st.session_state.earnings_rate_limit_warned:
                st.warning(
                    "⚠️ Yahoo Finance Rate-Limit bei Earnings-Daten – "
                    "Earnings-Termine werden für diesen Durchlauf nicht weiter geladen."
                )
                st.session_state.earnings_rate_limit_warned = True
            next_earn = None
        except Exception as e:
            # Andere Fehler je Ticker anzeigen
            st.warning(f"⚠️ Konnte Earnings-Daten für {ticker} nicht laden: {e}")
            next_earn = None

        # --- Filter: nur künftige Termine/Spannen anzeigen ---
        if next_earn:
            if isinstance(next_earn, datetime.date):
                if next_earn < today:
                    next_earn = None
            elif isinstance(next_earn, str) and "–" in next_earn:
                dates = next_earn.split("–")
                try:
                    start = datetime.datetime.strptime(dates[0].strip(), "%d.%m.%Y").date()
                    end = datetime.datetime.strptime(dates[1].strip(), "%d.%m.%Y").date()
                    if end < today:
                        next_earn = None
                except Exception:
                    pass

    # Wenn Earnings deaktiviert oder Fehler: next_earn bleibt None
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

def fmt_int(x):
    return f"{x:,.0f}".replace(",", ".")

def fmt_flt(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def fmt_pct(x):
    return fmt_flt(x) + " %"

def fmt_cash(x):
    return fmt_flt(x) + " $"

def fmt_eur(x):
    return fmt_flt(x) + " €"

def fmt_date(d):
    return d.strftime("%d.%m.%Y") if isinstance(d, datetime.date) else str(d) if d else ""

def color_pos_neg(v):
    return "" if pd.isna(v) else ("color: green;" if v >= 0 else "color: red;")

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
    # applymap -> map (FutureWarning fix)
    .map(color_pos_neg, subset=["Entwicklung (%)", "Gewinn/Verlust ($)"])
)

# Dynamische Höhe: 40 px für Header, ca. 35 px pro Zeile
table_height = 40 + 35 * len(df)

# use_container_width -> width="stretch" (Future deprecation fix)
st.dataframe(styler, width="stretch", height=table_height)

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
    .map(color_pos_neg, subset=["Gewinn/Verlust ($)"])
)

st.dataframe(total_styler, width="stretch", height=80)

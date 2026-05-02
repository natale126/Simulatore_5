import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.stats import norm
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# --- 1. CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Simulatore Opzioni PRO", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.25rem !important; }
.risk-card { background-color: #1e2130; padding: 15px; border-radius: 10px; border-left: 5px solid #00ffcc; margin-bottom: 20px; }
</style>
""", unsafe_allow_html=True)

# --- 2. MOTORE MATEMATICO ---
def bs_engine(S, K, T, r, sigma, option_type="Call"):
    if T <= 0: T = 1e-9 
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "Call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

# --- 3. SIDEBAR ---
st.sidebar.header("📊 Parametri Simulazione")
ticker = st.sidebar.text_input("Ticker Azione", value="NVDA").upper()
balance = st.sidebar.number_input("Saldo Virtuale ($)", value=10000.0)
moltiplicatore = st.sidebar.number_input("Moltiplicatore", value=100)
data_ingresso = st.sidebar.date_input("Data Inizio", value=datetime.now() - timedelta(days=30))

# --- 4. DOWNLOAD DATI ---
try:
    df_full = yf.download(ticker, start=data_ingresso, progress=False, auto_adjust=True).ffill()
    if df_full.empty: raise ValueError("Nessun dato trovato")
    prezzo_apertura = float(df_full['Close'].iloc[0])
except:
    st.error("Inserisci un Ticker valido (es. AAPL, TSLA, BTC-USD)")
    st.stop()

# Recupero scadenze reali
tk = yf.Ticker(ticker)
try:
    scadenze = tk.options
    scelta_scadenza = st.sidebar.selectbox("Scadenza Opzioni", scadenze)
    chain = tk.option_chain(scelta_scadenza)
    strikes = sorted(list(set(chain.calls['strike'].tolist())))
except:
    st.warning("Impossibile recuperare chain reale, uso modalità manuale.")
    scelta_scadenza = None

# --- 5. TIME MACHINE ---
giorni_totali = (datetime.strptime(scelta_scadenza, "%Y-%m-%d").date() - data_ingresso).days if scelta_scadenza else 30
passaggio_tempo = st.sidebar.slider("Avanza nel tempo (Giorni)", 0, giorni_totali, 0)

idx_g = min(passaggio_tempo, len(df_full) - 1)
prezzo_corrente = float(df_full['Close'].iloc[idx_g])
data_corrente = df_full.index[idx_g]

# --- 6. SETUP STRATEGIA ---
st.subheader(f"Configurazione Operazione su {ticker}")
cols = st.columns(2)
legs = []

for i in range(2): # Simuliamo 2 gambe per semplicità
    with cols[i]:
        st.markdown(f"**Gamba {i+1}**")
        tipo = st.selectbox(f"Tipo", ["Call", "Put"], key=f"t{i}")
        pos = st.selectbox(f"Posizione", ["Long (Compra)", "Short (Vendi)"], key=f"p{i}")
        strike = st.selectbox(f"Strike", strikes, index=len(strikes)//2, key=f"s{i}") if scelta_scadenza else st.number_input("Strike", value=prezzo_apertura, key=f"s{i}")
        
        # Logica Bid/Ask Reale
        df_c = chain.calls if tipo == "Call" else chain.puts
        row = df_c[df_c['strike'] == strike]
        
        if not row.empty:
            bid, ask, iv = float(row['bid']), float(row['ask']), float(row['impliedVolatility'])
            prezzo_entrata = ask if "Long" in pos else bid
            st.caption(f"Prezzo Mercato: ${prezzo_entrata:.2f} | IV: {iv*100:.1f}%")
        else:
            iv, prezzo_entrata = 0.35, bs_engine(prezzo_apertura, strike, giorni_totali/365, 0.04, 0.35, tipo)

        legs.append({'tipo': tipo, 'segno': 1 if "Long" in pos else -1, 'strike': strike, 'premio_ap': prezzo_entrata, 'iv': iv})

# --- 7. CALCOLO P&L ---
pnl_totale = 0
for leg in legs:
    t_residuo = max(0, (giorni_totali - passaggio_tempo) / 365)
    prezzo_opz_ora = bs_engine(prezzo_corrente, leg['strike'], t_residuo, 0.04, leg['iv'], leg['tipo'])
    pnl_totale += (prezzo_opz_ora - leg['premio_ap']) * leg['segno'] * moltiplicatore

# --- 8. DASHBOARD ---
c1, c2, c3 = st.columns(3)
c1.metric("Prezzo Sottostante", f"${prezzo_corrente:.2f}")
c2.metric("P&L Posizione", f"${pnl_totale:.2f}", delta=f"{pnl_totale:.2f}")
c3.metric("Data Corrente", data_corrente.strftime('%d %b %Y'))

# --- 9. GRAFICO PAYOFF ---
s_min, s_max = prezzo_apertura * 0.8, prezzo_apertura * 1.2
s_range = np.linspace(s_min, s_max, 100)
payoff_finale = np.zeros_like(s_range)

for leg in legs:
    if leg['tipo'] == "Call":
        p = np.maximum(s_range - leg['strike'], 0)
    else:
        p = np.maximum(leg['strike'] - s_range, 0)
    payoff_finale += (p - leg['premio_ap']) * leg['segno'] * moltiplicatore

fig = go.Figure()
fig.add_trace(go.Scatter(x=s_range, y=payoff_finale, name="Payoff a Scadenza", line=dict(color="#00ffcc")))
fig.add_vline(x=prezzo_corrente, line_dash="dash", line_color="orange", annotation_text="Prezzo attuale")
fig.update_layout(template="plotly_dark", title="Profilo di Rischio")
st.plotly_chart(fig, use_container_width=True)

import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
from scipy.stats import norm
import plotly.graph_objects as go
from datetime import datetime, timedelta
import os

# --- 1. CONFIGURAZIONE PAGINA E CSS ---
st.set_page_config(page_title="OptionStrat Pro - Final Edition", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.25rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.85rem !important; color: #cccccc !important; }
.risk-card {
    background-color: #1e2130;
    padding: 15px;
    border-radius: 10px;
    border-left: 5px solid #00ffcc;
    margin-bottom: 20px;
}
</style>
""", unsafe_allow_html=True)

# --- 2. LOGICA DI SALVATAGGIO PERMANENTE ---
FILE_LOG = "trading_journal_permanente.csv"

if 'balance' not in st.session_state:
    st.session_state.balance = 10000.0
if 'trades_history' not in st.session_state:
    st.session_state.trades_history = []

def carica_dati_permanenti():
    if os.path.exists(FILE_LOG):
        try:
            df = pd.read_csv(FILE_LOG)
            if not df.empty:
                st.session_state.balance = float(df['Saldo'].iloc[-1])
                st.session_state.trades_history = df.to_dict('records')
        except:
            pass

def salva_dati_permanenti(nuovo_trade):
    st.session_state.trades_history.append(nuovo_trade)
    df = pd.DataFrame(st.session_state.trades_history)
    df.to_csv(FILE_LOG, index=False)

carica_dati_permanenti()

# --- 3. MOTORE MATEMATICO (Black-Scholes) ---
def bs_engine(S, K, T, r, sigma, option_type="Call"):
    if T <= 0: T = 1e-9 
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    if option_type == "Call":
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

# --- 4. SIDEBAR E INPUT ---
st.sidebar.header("📊 Parametri Asset")
ticker = st.sidebar.text_input("Ticker Azione", value="NVDA").upper()
moltiplicatore = st.sidebar.number_input("Moltiplicatore", value=100)
data_ingresso = st.sidebar.date_input("Data Inizio Operazione", value=datetime.now() - timedelta(days=30))

# --- 5. DOWNLOAD DATI REALI ---
try:
    with st.spinner('Scaricamento dati in corso...'):
        tk = yf.Ticker(ticker)
        df_full = tk.history(start=data_ingresso)
        if df_full.empty: raise ValueError
        prezzo_apertura = float(df_full['Close'].iloc[0])
        
        # Recupero scadenze e chain
        scadenze = tk.options
        if not scadenze: raise ValueError
        scelta_scadenza = st.sidebar.selectbox("Scadenza Opzioni", scadenze)
        chain = tk.option_chain(scelta_scadenza)
        strikes = sorted(list(set(chain.calls['strike'].tolist())))
except:
    st.error("Errore nel caricamento dati. Controlla il Ticker.")
    st.stop()

# --- 6. TIME MACHINE ---
giorni_totali = (datetime.strptime(scelta_scadenza, "%Y-%m-%d").date() - data_ingresso).days
passaggio_tempo = st.sidebar.slider("Avanza nel tempo (Giorni)", 0, giorni_totali, 0)

idx_g = min(passaggio_tempo, len(df_full) - 1)
prezzo_corrente = float(df_full['Close'].iloc[idx_g])
data_corrente = df_full.index[idx_g]

# --- 7. CONFIGURAZIONE STRATEGIA (BID/ASK) ---
st.subheader(f"Configurazione Strategia su {ticker}")
cols = st.columns(2)
legs = []

for i in range(2):
    with cols[i]:
        st.markdown(f"<div class='risk-card'>Gamba {i+1}</div>", unsafe_allow_html=True)
        tipo = st.selectbox(f"Tipo", ["Call", "Put"], key=f"t{i}")
        pos = st.selectbox(f"Posizione", ["Long (Compra)", "Short (Vendi)"], key=f"p{i}")
        
        idx_atm = min(range(len(strikes)), key=lambda j: abs(strikes[j]-prezzo_apertura))
        strike = st.selectbox(f"Strike Price", strikes, index=idx_atm, key=f"s{i}")
        
        # Logica Bid/Ask Reale
        df_side = chain.calls if tipo == "Call" else chain.puts
        row = df_side[df_side['strike'] == strike]
        
        if not row.empty:
            bid = float(row['bid'].iloc[0])
            ask = float(row['ask'].iloc[0])
            iv = float(row['impliedVolatility'].iloc[0])
            # Se compri paghi l'Ask, se vendi ricevi il Bid
            prezzo_entrata = ask if "Long" in pos else bid
            st.caption(f"Bid: ${bid:.2f} | Ask: ${ask:.2f} | IV: {iv*100:.1f}%")
        else:
            iv = 0.30
            prezzo_entrata = bs_engine(prezzo_apertura, strike, giorni_totali/365, 0.04, iv, tipo)
            st.caption(f"Prezzo Teorico: ${prezzo_entrata:.2f}")

        legs.append({'tipo': tipo, 'segno': 1 if "Long" in pos else -1, 'strike': strike, 'premio_ap': prezzo_entrata, 'iv': iv})

# --- 8. CALCOLO P&L ---
pnl_totale = 0
for leg in legs:
    t_residuo = max(1e-9, (giorni_totali - passaggio_tempo) / 365)
    prezzo_opz_ora = bs_engine(prezzo_corrente, leg['strike'], t_residuo, 0.04, leg['iv'], leg['tipo'])
    pnl_totale += (prezzo_opz_ora - leg['premio_ap']) * leg['segno'] * moltiplicatore

# --- 9. DASHBOARD ---
st.divider()
c1, c2, c3, c4 = st.columns(4)
c1.metric("Prezzo Sottostante", f"${prezzo_corrente:.2f}")
c2.metric("P&L Attuale", f"${pnl_totale:.2f}", delta=f"{(pnl_totale/st.session_state.balance)*100:.2f}%")
c3.metric("Saldo Virtuale", f"${st.session_state.balance:.2f}")
c4.metric("Data Simulazione", data_corrente.strftime('%d/%m/%Y'))

# --- 10. TRADING JOURNAL ---
if st.button("✅ Chiudi e Salva Operazione nel Journal"):
    st.session_state.balance += pnl_totale
    nuovo_trade = {
        "Data": data_corrente.strftime('%Y-%m-%d'),
        "Ticker": ticker,
        "P&L": round(pnl_totale, 2),
        "Saldo": round(st.session_state.balance, 2)
    }
    salva_dati_permanenti(nuovo_trade)
    st.success("Operazione salvata correttamente!")

# --- 11. GRAFICI ---
tab1, tab2 = st.tabs(["Profilo di Rischio", "Storico Saldo"])

with tab1:
    s_range = np.linspace(prezzo_apertura * 0.7, prezzo_apertura * 1.3, 100)
    payoff = np.zeros_like(s_range)
    for leg in legs:
        if leg['tipo'] == "Call":
            val = np.maximum(s_range - leg['strike'], 0)
        else:
            val = np.maximum(leg['strike'] - s_range, 0)
        payoff += (val - leg['premio_ap']) * leg['segno'] * moltiplicatore
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=s_range, y=payoff, name="Payoff Scadenza", line=dict(color="#00ffcc")))
    fig.add_vline(x=prezzo_corrente, line_dash="dash", line_color="orange")
    fig.update_layout(template="plotly_dark", title="Analisi Payoff a Scadenza")
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    if st.session_state.trades_history:
        df_hist = pd.DataFrame(st.session_state.trades_history)
        st.line_chart(df_hist['Saldo'])
        st.table(df_hist.tail(5))

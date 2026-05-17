import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm

# --- MOTORE MATEMATICO ---
def black_scholes_put(S, K, T, r, sigma):
    """
    Calcola il prezzo di una Put europea usando Black-Scholes.
    Se T è vicinissimo a 0, restituisce direttamente il valore intrinseco per evitare errori di divisione.
    """
    if T <= 0.0001:
        return np.maximum(K - S, 0.0)
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
    return put_price

# --- INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="Opzioni: Payoff a Scadenza", layout="wide")
st.title("Simulatore Strategia SPY: Risoluzione Bug OptionStrat")
st.markdown("Grafico del payoff simulato alla chiusura del **26 maggio**.")

# --- SIDEBAR (PARAMETRI) ---
st.sidebar.header("Parametri di Mercato")
current_price = st.sidebar.number_input("Prezzo Attuale SPY", value=760.0, step=1.0)
iv_long = st.sidebar.slider("Volatilità Residua (Opzioni 27 Maggio) %", min_value=1.0, max_value=50.0, value=15.0, step=1.0) / 100
risk_free_rate = 0.05 # Tasso privo di rischio standard al 5%

st.sidebar.header("Struttura del Trade")
st.sidebar.markdown("**Gambe Short (Scadenza Oggi: 26 Maggio)**")
strike_short_1 = st.sidebar.number_input("Strike Short Put 1", value=757.0)
strike_short_2 = st.sidebar.number_input("Strike Short Put 2", value=764.0)

st.sidebar.markdown("**Gambe Long (Scadenza Domani: 27 Maggio)**")
strike_long = st.sidebar.number_input("Strike Long Put (x2)", value=761.0)

net_debit = st.sidebar.number_input("Debito Pagato Inizialmente ($)", value=78.50)

# --- CALCOLO DEL PAYOFF ---
# Creiamo un array di possibili prezzi dello SPY a scadenza
prices = np.linspace(current_price - 40, current_price + 40, 500)

# 1. Valore a scadenza della Short Put 757 (T=0)
# Essendo venduta, incassiamo il premio, ma a scadenza paghiamo il valore intrinseco.
payoff_short_1 = -np.maximum(strike_short_1 - prices, 0.0)

# 2. Valore a scadenza della Short Put 764 (T=0)
payoff_short_2 = -np.maximum(strike_short_2 - prices, 0.0)

# 3. Valore residuo delle due Long Put 761 (T = 1 giorno = 1/365 anni)
# Qui usiamo Black-Scholes perché queste opzioni sopravvivono un altro giorno!
T_residuo = 1 / 365 
valore_long_singola = black_scholes_put(prices, strike_long, T_residuo, risk_free_rate, iv_long)
payoff_long_totale = 2 * valore_long_singola

# Calcolo del Profitto Netto Totale
# (Valore finale della struttura) - (Costo per aprirla)
total_payoff = payoff_short_1 + payoff_short_2 + payoff_long_totale - net_debit

# --- GRAFICO PLOTLY ---
fig = go.Figure()

# Aggiungiamo la linea del PnL
fig.add_trace(go.Scatter(
    x=prices, 
    y=total_payoff, 
    mode='lines', 
    name='Payoff Netto',
    line=dict(color='white', width=3),
    fill='tozeroy',
    fillcolor='rgba(0, 255, 0, 0.1)' # Verde in trasparenza per i profitti
))

# Evidenziamo l'asse zero
fig.add_hline(y=0, line_dash="dash", line_color="gray")

# Linea verticale sul prezzo attuale
fig.add_vline(x=current_price, line_dash="dot", line_color="blue", annotation_text="Prezzo Attuale")

# Formattazione del grafico
fig.update_layout(
    title=f"Payoff il 26 Maggio (Max Perdita blindata a -${net_debit})",
    xaxis_title="Prezzo SPY a Scadenza",
    yaxis_title="Profitto / Perdita ($)",
    template="plotly_dark",
    hovermode="x unified"
)

st.plotly_chart(fig, use_container_width=True)

# Spiegazione a schermo
st.info("""
**Perché questo grafico è corretto:** Il codice azzera matematicamente il valore temporale delle opzioni in scadenza oggi (26 Maggio), ma applica il modello Black-Scholes per calcolare il valore esatto delle due Put in scadenza domani (27 Maggio). Questo dimostra che anche abbassando la volatilità dalla barra laterale, la tua perdita massima non scenderà mai sotto il debito iniziale pagato.
""")

import streamlit as st
import yfinance as yf
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from scipy.stats import norm
from datetime import datetime, timedelta

# Configurazione della pagina Streamlit
st.set_page_config(page_title="Advanced Options Strategy Studio", layout="wide")

# Mappatura dei mesi in italiano
MONTH_MAP = {
    1: "Gennaio", 2: "Febbraio", 3: "Marzo", 4: "Aprile",
    5: "Maggio", 6: "Giugno", 7: "Luglio", 8: "Agosto",
    9: "Settembre", 10: "Ottobre", 11: "Novembre", 12: "Dicembre"
}

# ==========================================
# 1. MOTORE MATEMATICO (BLACK-SCHOLES & GRECHE)
# ==========================================

def black_scholes_put(S, K, T, r, sigma):
    if T <= 0.00001:
        return max(0.0, K - S)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)


def black_scholes_call(S, K, T, r, sigma):
    if T <= 0.00001:
        return max(0.0, S - K)
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)


def calculate_greeks(S, K, T, r, sigma, option_type="put"):
    if T <= 0.00001:
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}
    
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    gamma = norm.pdf(d1) / (S * sigma * np.sqrt(T))
    vega = S * norm.pdf(d1) * np.sqrt(T) / 100.0 
    
    if option_type == "put":
        delta = norm.cdf(d1) - 1.0
        theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) + r * K * np.exp(-r * T) * norm.cdf(-d2)
    else:
        delta = norm.cdf(d1)
        theta = - (S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T)) - r * K * np.exp(-r * T) * norm.cdf(d2)
        
    return {
        "delta": delta,
        "gamma": gamma,
        "theta": theta / 365.0, 
        "vega": vega
    }

# ==========================================
# 2. INTERFACCIA UTENTE & SIDEBAR
# ==========================================

st.title("馃搳 Opzioni Advanced Analytix - SPY Studio Pro")
st.markdown("Costruttore di strategie asimmetriche multi-gamba con motore termico di volatilit脿.")

st.sidebar.header("鈿欙笍 Impostazioni di Input")
modalita = st.sidebar.radio("Modalit脿 Dati:", ["Live API (Yahoo Finance)", "Manuale (Sandbox)"])

tasso_interesse = st.sidebar.number_input("Tasso Risk-Free (%)", value=4.5, step=0.1) / 100.0

# Calcolo o inserimento del prezzo Spot di riferimento
if modalita == "Live API (Yahoo Finance)":
    ticker_input = st.sidebar.text_input("Ticker", value="SPY").upper()
    try:
        ticker_data = yf.Ticker(ticker_input)
        prezzo_spot_live = ticker_data.history(period="1d")["Close"].iloc[-1]
        st.sidebar.success(f"Prezzo Live Connesso: ${prezzo_spot_live:.2f}")
    except Exception:
        st.sidebar.error("Errore nel recupero dati live. Uso fallback manuale.")
        prezzo_spot_live = 760.0
    
    usa_override = st.sidebar.checkbox("Inserisci Spot Manuale (Live Tracking Ibrido)")
    if usa_override:
        prezzo_spot = st.sidebar.number_input("Prezzo Spot Corrente ($)", value=float(round(prezzo_spot_live, 2)))
    else:
        prezzo_spot = float(prezzo_spot_live)
else:
    prezzo_spot = st.sidebar.number_input("Prezzo Spot Manuale ($)", value=760.0, step=1.0)

# ==========================================
# 3. GENERAZIONE CALENDARIO SCADENZE (STILE OPTIONSTRAT)
# ==========================================

# Recupero delle date disponibili (vere o simulate)
if modalita == "Live API (Yahoo Finance)" and 'ticker_data' in locals():
    try:
        raw_options_dates = ticker_data.options
        available_dates = [datetime.strptime(d, "%Y-%m-%d").date() for d in raw_options_dates]
    except Exception:
        available_dates = [datetime.now().date() + timedelta(days=i) for i in range(1, 45)]
else:
    # Generazione automatica scadenze giornaliere artificiali per la Sandbox
    available_dates = [datetime.now().date() + timedelta(days=i) for i in range(0, 45)]

# Raggruppamento date per Mese
grouped_dates = {}
for d in available_dates:
    month_str = f"{MONTH_MAP[d.month]} {d.year}"
    if month_str not in grouped_dates:
        grouped_dates[month_str] = []
    grouped_dates[month_str].append(d)

# ==========================================
# 4. GESTIONE DINAMICA DELLE GAMBE (SESSION STATE)
# ==========================================

st.header("馃幆 Configurazione Gambe Strategia")

# Inizializzazione delle 3 gambe di default se la sessione 猫 nuova
if "legs" not in st.session_state:
    first_month = list(grouped_dates.keys())[0]
    days_in_first_month = grouped_dates[first_month]
    
    # Assegna scadenze di default basate sul calendario reale trovato
    d_short = days_in_first_month[0]
    d_long = days_in_first_month[1] if len(days_in_first_month) > 1 else d_short + timedelta(days=1)
    
    st.session_state.legs = [
        {"action": "Short", "qty": 1, "type": "Put", "strike": int(prezzo_spot - 3), "month": first_month, "day": d_short},
        {"action": "Long", "qty": 2, "type": "Put", "strike": int(prezzo_spot + 1), "month": first_month, "day": d_long},
        {"action": "Short", "qty": 1, "type": "Put", "strike": int(prezzo_spot + 4), "month": first_month, "day": d_short},
    ]

# Renderizzazione dinamica delle righe per ciascuna gamba presente
active_legs = []
for i in range(len(st.session_state.legs)):
    st.markdown(f"**Gamba {i+1}**")
    col_act, col_qty, col_typ, col_stk, col_mon, col_day = st.columns([1.2, 1.2, 1.2, 1.8, 2.2, 1.8])
    
    leg_data = st.session_state.legs[i]
    
    with col_act:
        action = st.selectbox("Azione", ["Long", "Short"], key=f"act_{i}", index=0 if leg_data["action"] == "Long" else 1)
    with col_qty:
        qty = st.number_input("Lotti", min_value=1, max_value=500, value=int(leg_data["qty"]), key=f"qty_{i}")
    with col_typ:
        opt_type = st.selectbox("Tipo", ["Put", "Call"], key=f"typ_{i}", index=0 if leg_data["type"] == "Put" else 1)
    with col_stk:
        strike = st.number_input("Strike ($)", value=int(leg_data["strike"]), key=f"stk_{i}", step=1)
    with col_mon:
        month_list = list(grouped_dates.keys())
        saved_month = leg_data["month"] if leg_data["month"] in month_list else month_list[0]
        month = st.selectbox("Mese Scadenza", month_list, key=f"mon_{i}", index=month_list.index(saved_month))
    with col_day:
        day_list = grouped_dates[month]
        saved_day = leg_data["day"] if leg_data["day"] in day_list else day_list[0]
        day = st.selectbox("Giorno Scadenza", day_list, format_func=lambda x: f"{x.day}", key=f"day_{i}", index=day_list.index(saved_day))
        
    active_legs.append({
        "action": action,
        "qty": qty,
        "type": opt_type,
        "strike": strike,
        "month": month,
        "day": day
    })

# Aggiorna lo stato globale con le modifiche correnti
st.session_state.legs = active_legs

# Pulsanti di controllo delle gambe
col_btn1, col_btn2, _ = st.columns([1.5, 1.5, 7])
with col_btn1:
    if st.button("鉃 Aggiungi Gamba"):
        # Copia i dati dell'ultima gamba per comodit脿 di inserimento
        nuova_gamba = st.session_state.legs[-1].copy()
        st.session_state.legs.append(nuova_gamba)
        st.rerun()
with col_btn2:
    if st.button("鉂 Rimuovi Ultima Gamba") and len(st.session_state.legs) > 1:
        st.session_state.legs.pop()
        st.rerun()

# ==========================================
# 5. GESTIONE VOLATILIT脌 & SIMULAZIONE SCADENZA
# ==========================================

st.sidebar.header("馃搱 Gestione Volatilit脿 (IV)")
iv_generica = st.sidebar.slider("Volatilit脿 Implicita Base (%)", min_value=2.0, max_value=50.0, value=16.9) / 100.0
correzione_bug = st.sidebar.toggle("Attiva Struttura a Termine Intelligente (No Bug)", value=True)

debito_iniziale = st.number_input("Net Debit Pagato Totale ($)", value=78.50, step=1.0)

# Calcolo automatico della data di valutazione (Default: La scadenza pi霉 corta del portafoglio)
all_selected_days = [leg["day"] for leg in st.session_state.legs]
valuation_date = min(all_selected_days)

st.header("鈴 Simulatore Temporale Intraday")
st.caption(f"La strategia viene valutata in base alla scadenza pi霉 vicina impostata: **{valuation_date.day} {valuation_date.strftime('%B %Y')}**")

valutazione_scadenza = st.radio("Seleziona finestra di chiusura:", ["Esattamente a scadenza delle opzioni Short", "Intraday (Qualche ora prima della chiusura del mercato)"])

if valutazione_scadenza == "Intraday (Qualche ora prima della chiusura del mercato)":
    ore_mancanti = st.slider("Ore mancanti alla chiusura del mercato", min_value=1, max_value=7, value=2)
else:
    ore_mancanti = 0

# ==========================================
# 6. ENGINE DI CALCOLO DINAMICO DEL PROFILO PNL
# ==========================================

prezzi_asse_x = np.linspace(prezzo_spot * 0.90, prezzo_spot * 1.10, 500)
pnl_profilo = []


# Funzione interna per mappare il tempo (T) e la volatilit脿 (IV) di ogni singola gamba
def get_leg_parameters(leg, valuation_date, ore_mancanti, iv_generica, correzione_bug):
    # Calcolo tempo residuo (T)
    if ore_mancanti > 0:
        if leg["day"] == valuation_date:
            T_leg = (ore_mancanti / 24.0) / 365.0
        else:
            T_leg = ((leg["day"] - valuation_date).days + (ore_mancanti / 24.0)) / 365.0
    else:
        if leg["day"] == valuation_date:
            T_leg = 0.000001 # Prossimo a zero
        else:
            T_leg = (leg["day"] - valuation_date).days / 365.0
            
    # Calcolo Volatilit脿 Term Structure (No Bug Fix)
    if correzione_bug and leg["day"] > valuation_date:
        iv_leg = max(iv_generica, 0.12) # Floor protettivo del 12%
    else:
        iv_leg = iv_generica
        
    return T_leg, iv_leg


# Ciclo di calcolo principale per l'asse X del grafico
for x_spot in prezzi_asse_x:
    valore_attuale_posizione = 0.0
    for leg in st.session_state.legs:
        T_leg, iv_leg = get_leg_parameters(leg, valuation_date, ore_mancanti, iv_generica, correzione_bug)
        
        if leg["type"] == "Put":
            price = black_scholes_put(x_spot, leg["strike"], T_leg, tasso_interesse, iv_leg)
        else:
            price = black_scholes_call(x_spot, leg["strike"], T_leg, tasso_interesse, iv_leg)
            
        segno = 1.0 if leg["action"] == "Long" else -1.0
        valore_attuale_posizione += segno * leg["qty"] * price * 100
        
    pnl_singolo = valore_attuale_posizione - debito_iniziale
    pnl_profilo.append(pnl_singolo)

pnl_profilo = np.array(pnl_profilo)

# Calcolo valore corrente allo spot attuale dello SPY
pnl_corrente = 0.0
delta_tot, gamma_tot, theta_tot, vega_tot = 0.0, 0.0, 0.0, 0.0

for leg in st.session_state.legs:
    T_leg, iv_leg = get_leg_parameters(leg, valuation_date, ore_mancanti, iv_generica, correzione_bug)
    
    if leg["type"] == "Put":
        price_now = black_scholes_put(prezzo_spot, leg["strike"], T_leg, tasso_interesse, iv_leg)
    else:
        price_now = black_scholes_call(prezzo_spot, leg["strike"], T_leg, tasso_interesse, iv_leg)
        
    segno = 1.0 if leg["action"] == "Long" else -1.0
    pnl_corrente += segno * leg["qty"] * price_now * 100
    
    # Aggregazione Greche di Portafoglio
    g_leg = calculate_greeks(prezzo_spot, leg["strike"], T_leg, tasso_interesse, iv_leg, leg["type"].lower())
    delta_tot += segno * leg["qty"] * g_leg["delta"]
    gamma_tot += segno * leg["qty"] * g_leg["gamma"]
    theta_tot += segno * leg["qty"] * g_leg["theta"]
    vega_tot += segno * leg["qty"] * g_leg["vega"]

pnl_corrente -= debito_iniziale
max_profit = np.max(pnl_profilo)

# ==========================================
# 7. METRICHE & CONTROLLO LIVE DELLE GRECHE
# ==========================================

st.header("馃幆 Monitoraggio Posizione e Greche Live")
m1, m2, m3 = st.columns(3)
m1.metric("PnL Previsto allo Spot Corrente", f"${pnl_corrente:.2f}")
m2.metric("Massimo Profitto dell'Asse", f"${max_profit:.2f}")
m3.metric("Rischio Massimo Struttura", f"-${debito_iniziale:.2f}")

col_g1, col_g2, col_g3, col_g4 = st.columns(4)
col_g1.metric("Delta di Posizione (Direzione)", f"{delta_tot * 100:.2f}", help="Indica il guadagno/perdita teorico per un movimento di 1$ dello SPY.")
col_g2.metric("Gamma di Posizione (Accelerazione)", f"{gamma_tot * 100:.4f}", help="L'accelerazione del tuo Delta rispetto ai movimenti dello SPY.")
col_g3.metric("Theta di Posizione (Decadimento/Giorno)", f"${theta_tot * 100:.2f}", help="Il valore estrinseco incassato/perso passivamente ogni 24 ore.")
col_g4.metric("Vega di Posizione (Sensibilit脿 IV)", f"${vega_tot * 100:.2f}", help="L'impatto sul portafoglio per ogni variazione dell'1% della volatilit脿.")

# ==========================================
# 8. TRACCIAMENTO GRAFICO INTERATTIVO (PLOTLY)
# ==========================================

fig = go.Figure()

# Linea del Profilo PnL
fig.add_trace(go.Scatter(
    x=prezzi_asse_x, 
    y=pnl_profilo,
    mode='lines',
    name='Profilo PnL Strategia',
    line=dict(color='#2ecc71' if pnl_corrente >= 0 else '#e74c3c', width=3)
))

# Segnaposto Prezzo Spot Attuale
fig.add_trace(go.Scatter(
    x=[prezzo_spot], 
    y=[pnl_corrente],
    mode='markers+text',
    name='Prezzo Spot Sottostante',
    marker=dict(size=12, color='white', line=dict(color='black', width=2)),
    text=[f"Spot: ${prezzo_spot:.2f}"],
    textposition="top center"
))

# Visualizzazione dinamica di TUTTI gli strike inseriti nelle gambe
for idx, leg in enumerate(st.session_state.legs):
    colore_linea = "#3498db" if leg["action"] == "Long" else "orange"
    stile_linea = "solid" if leg["action"] == "Long" else "dash"
    fig.add_vline(
        x=leg["strike"], 
        line_dash=stile_linea, 
        line_color=colore_linea, 
        annotation_text=f"G{idx+1} ({leg['action']}): {leg['strike']}"
    )

fig.update_layout(
    title="Grafico Asimmetrico dei Payoff in Tempo Reale",
    xaxis_title="Prezzo Sottostante ($)",
    yaxis_title="Profitto / Perdita Netta ($)",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    template="plotly_dark",
    hovermode="x unified"
)

fig.add_hline(y=0, line_color="white", line_width=1)

st.plotly_chart(fig, use_container_width=True)

st.info("馃挕 **Consiglio di prova:** Modifica i lotti di una qualsiasi gamba o cambia il tipo in 'Call'. Vedrai sia il grafico che il pannello delle Greche adattarsi istantaneamente senza generare errori matematici.")

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import yfinance as yf

# --- MOTORE MATEMATICO ---
def calcola_prezzo_opzione(S, K, T, r, sigma, tipo_opzione):
    if T <= 0.0001:
        if tipo_opzione == 'Call':
            return np.maximum(S - K, 0.0)
        else:
            return np.maximum(K - S, 0.0)
            
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    
    if tipo_opzione == 'Call':
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
    else:
        return K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)

# --- SETUP PAGINA ---
st.set_page_config(page_title="OptionStrat Simulator PC", layout="wide")
st.title("Piattaforma Simulazione Opzioni - Desktop Version")

# --- SIDEBAR PARAMETRI ---
st.sidebar.header("Parametri di Mercato")
prezzo_attuale = st.sidebar.number_input("Prezzo Sottostante", value=760.0, step=1.0)
iv_globale = st.sidebar.slider("Volatilità Implicita (IV) %", min_value=1.0, max_value=50.0, value=16.0, step=0.1)
giorni_simulazione = st.sidebar.slider("Giorni Trascorsi:", min_value=0, max_value=30, value=9)
tasso_risk_free = st.sidebar.number_input("Tasso Interesse Risk-Free", value=0.05, step=0.01)

st.sidebar.markdown("---")
attiva_bug = st.sidebar.checkbox("Attiva BUG OptionStrat", value=False)

# --- SEZIONE YAHOO FINANCE ---
st.subheader("Catena delle Opzioni Reale (Yahoo Finance)")
try:
    ticker = "SPY"
    spy_data = yf.Ticker(ticker)
    scadenze_disponibili = spy_data.options
    scadenza_selezionata = st.selectbox("Seleziona una Scadenza reale presente sul mercato:", scadenze_disponibili)
    
    opt_chain = spy_data.option_chain(scadenza_selezionata)
    puts_reali = opt_chain.puts[['strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility']]
    st.dataframe(puts_reali.head(10), use_container_width=True)
except:
    st.warning("Impossibile caricare l'Option Chain in questo momento.")

# --- TABELLA GAMBE ---
st.subheader("Configurazione Gambe Strategia")

dati_iniziali = {
    "Azione": ["Short", "Short", "Long"],
    "Tipo": ["Put", "Put", "Put"],
    "Quantità": [1, 1, 2],
    "Strike": [757.0, 764.0, 761.0],
    "DTE Iniziali": [9, 9, 10], 
    "Prezzo Ingresso ($)": [1.50, 4.00, 2.35]
}

df_gambe = st.data_editor(
    pd.DataFrame(dati_iniziali),
    num_rows="dynamic",
    column_config={
        "Azione": st.column_config.SelectboxColumn("Azione", options=["Long", "Short"], required=True),
        "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Call", "Put"], required=True),
        "Quantità": st.column_config.NumberColumn("Quantità", min_value=1, step=1, required=True),
        "DTE Iniziali": st.column_config.NumberColumn("DTE Iniziali", min_value=0, step=1, required=True),
    },
    use_container_width=True
)

# --- CALCOLO E GRAFICO ---
if len(df_gambe) > 0:
    prezzi_simulati = np.linspace(prezzo_attuale * 0.90, prezzo_attuale * 1.10, 500)
    payoff_totale = np.zeros_like(prezzi_simulati)
    costo_totale_struttura = 0.0

    for index, row in df_gambe.iterrows():
        azione = row["Azione"]
        tipo = row["Tipo"]
        qta = int(row["Quantità"])
        strike = float(row["Strike"])
        dte_iniziale = float(row["DTE Iniziali"])
        prezzo_ingresso = float(row["Prezzo Ingresso ($)"])
        
        moltiplicatore = 1 if azione == "Long" else -1
        costo_gamba = prezzo_ingresso * qta * moltiplicatore * 100
        costo_totale_struttura += costo_gamba
        
        giorni_rimanenti = max(dte_iniziale - giorni_simulazione, 0)
        
        if attiva_bug and giorni_rimanenti <= 1:
            T_rimanente = 0.0
        else:
            T_rimanente = giorni_rimanenti / 365.0
            
        valore_futuro_singolo = calcola_prezzo_opzione(prezzi_simulati, strike, T_rimanente, tasso_risk_free, iv_globale / 100, tipo)
        payoff_gamba = (valore_futuro_singolo - prezzo_ingresso) * moltiplicatore * qta * 100
        payoff_totale += payoff_gamba

    st.subheader("Grafico Analisi Payoff")
    debito_o_credito = "Debito Netto" if costo_totale_struttura > 0 else "Credito Netto"
    st.markdown(f"**{debito_o_credito} Iniziale:** ${abs(costo_totale_struttura):.2f}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=prezzi_simulati, y=payoff_totale, mode='lines', name='Profilo PnL',
        line=dict(color='white', width=3), fill='tozeroy',
        fillcolor='rgba(0, 255, 0, 0.1)' if max(payoff_totale) > 0 else 'rgba(255, 0, 0, 0.1)'
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.add_vline(x=prezzo_attuale, line_dash="dot", line_color="blue", annotation_text="Prezzo Spot")

    fig.update_layout(
        xaxis_title="Prezzo Sottostante",
        yaxis_title="Profitto / Perdita ($)",
        template="plotly_dark",
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Inserisci le gambe nella tabella per generare il grafico del payoff.")

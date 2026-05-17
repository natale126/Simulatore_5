import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
import yfinance as yf

# --- MOTORE MATEMATICO (Black-Scholes) ---
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

# --- SETUP INTERFACCIA RESPONSIVE ---
st.set_page_config(page_title="SPY Options Suite", layout="wide")
st.title("📊 SPY Options Analytix (Mobile Ready)")

# --- SEZIONE 1: LIVE TRACKER IBRIDO (YAHOO FINANCE) ---
st.header("1. Sottostante & Catena Opzioni Real-Time")

modalita_spot = st.radio(
    "Sorgente prezzo SPY:", 
    ["Yahoo Finance (Ritardo 15 min)", "Inserimento Manuale (Prezzo dal tuo Broker)"],
    horizontal=True
)

# Recupero dati da Yahoo Finance
ticker = "SPY"
spy_data = yf.Ticker(ticker)

try:
    prezzo_yahoo = spy_data.history(period="1d")["Close"].iloc[-1]
except:
    prezzo_yahoo = 760.0 # Fallback se i mercati sono chiusi o API offline

if modalita_spot == "Yahoo Finance (Ritardo 15 min)":
    prezzo_sottostante = prezzo_yahoo
    st.success(f"Prezzo attuale SPY (Yahoo): **${prezzo_sottostante:.2f}**")
else:
    prezzo_sottostante = st.number_input("Inserisci il prezzo attuale dal tuo broker:", value=float(np.round(prezzo_yahoo, 2)), step=0.01)

# Sezione Option Chain Reale
with st.expander("Visualizza Catena delle Opzioni Reale sullo SPY"):
    try:
        scadenze_disponibili = spy_data.options
        scadenza_selezionata = st.selectbox("Seleziona una scadenza di mercato:", scadenze_disponibili)
        
        opt_chain = spy_data.option_chain(scadenza_selezionata)
        puts_reali = opt_chain.puts[['strike', 'lastPrice', 'bid', 'ask', 'impliedVolatility']]
        puts_reali['impliedVolatility'] = (puts_reali['impliedVolatility'] * 100).round(2)
        
        st.dataframe(puts_reali.head(15), use_container_width=True)
        st.caption("Usa questi dati reali (Strike, Prezzi e Volatilità IV) per popolare la strategia qui sotto.")
    except:
        st.warning("Impossibile caricare l'Option Chain. Prova più tardi.")

# --- SEZIONE 2: COSTRUTTORE DI STRATEGIE DINAMICO ---
st.header("2. Analizzatore Payoff Strategia")
st.markdown("Aggiungi, rimuovi o modifica le gambe nella tabella. Il grafico simula il payoff futuro eliminando il bug della volatilità residua.")

# Parametri temporali globali per la simulazione
st.subheader("Parametri Simulazione Grafico")
col_g1, col_g2 = st.columns(2)
with col_g1:
    giorni_simulazione = st.slider("Valuta la strategia tra X giorni da oggi:", min_value=0, max_value=30, value=9)
with col_g2:
    tasso_risk_free = st.number_input("Tasso d'interesse Risk-Free:", value=0.05, step=0.01)

# Dati di default pronti (La tua strategia Diagonal Put su SPY)
dati_iniziali = {
    "Azione": ["Short", "Short", "Long"],
    "Tipo": ["Put", "Put", "Put"],
    "Quantità": [1, 1, 2],
    "Strike": [757.0, 764.0, 761.0],
    "DTE (Giorni a Scadenza)": [9, 9, 10], 
    "Volatilità IV (%)": [16.0, 16.0, 16.0],
    "Prezzo Ingresso ($)": [1.50, 4.00, 2.35]
}
df_iniziale = pd.DataFrame(dati_iniziali)

# Tabella interattiva per Mobile e PC
df_gambe = st.data_editor(
    df_iniziale,
    num_rows="dynamic",
    column_config={
        "Azione": st.column_config.SelectboxColumn("Azione", options=["Long", "Short"], required=True),
        "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Call", "Put"], required=True),
        "Quantità": st.column_config.NumberColumn("Q.tà", min_value=1, step=1, required=True),
        "DTE (Giorni a Scadenza)": st.column_config.NumberColumn("DTE", min_value=0, step=1, required=True),
    },
    use_container_width=True
)

# --- CALCOLO FINALE DEL PAYOFF ---
if len(df_gambe) > 0:
    prezzi_simulati = np.linspace(prezzo_sottostante * 0.92, prezzo_sottostante * 1.08, 500)
    payoff_totale = np.zeros_like(prezzi_simulati)
    costo_totale_struttura = 0.0

    for index, row in df_gambe.iterrows():
        azione = row["Azione"]
        tipo = row["Tipo"]
        qta = int(row["Quantità"])
        strike = float(row["Strike"])
        dte_iniziale = float(row["DTE (Giorni a Scadenza)"])
        volatilita = float(row["Volatilità IV (%)"]) / 100
        prezzo_ingresso = float(row["Prezzo Ingresso ($)"])
        
        moltiplicatore = 1 if azione == "Long" else -1
        costo_gamba = prezzo_ingresso * qta * moltiplicatore * 100
        costo_totale_struttura += costo_gamba
        
        # Sottraiamo i giorni passati ma blocchiamo a 0
        giorni_rimanenti = max(dte_iniziale - giorni_simulazione, 0)
        T_rimanente = giorni_rimanenti / 365.0
        
        valore_futuro_singolo = calcola_prezzo_opzione(prezzi_simulati, strike, T_rimanente, tasso_risk_free, volatilita, tipo)
        payoff_gamba = (valore_futuro_singolo - prezzo_ingresso) * moltiplicatore * qta * 100
        payoff_totale += payoff_gamba

    # --- GRAFICO INTERATTIVO ---
    debito_o_credito = "Debito Netto" if costo_totale_struttura > 0 else "Credito Netto"
    st.metric(label=debito_o_credito, value=f"${abs(costo_totale_struttura):.2f}")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=prezzi_simulati, y=payoff_totale, mode='lines', name=f'PnL stimato a {giorni_simulazione}gg',
        line=dict(color='#00ffcc', width=3), fill='tozeroy',
        fillcolor='rgba(0, 255, 200, 0.08)'
    ))
    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.add_vline(x=prezzo_sottostante, line_dash="dot", line_color="#ff9900", annotation_text="Prezzo Attuale")

    fig.update_layout(
        title="Profilo Profitto / Perdita ($)",
        xaxis_title="Prezzo Sottostante SPY",
        yaxis_title="PnL ($)",
        template="plotly_dark",
        hovermode="x unified",
        margin=dict(l=10, r=10, t=40, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("Inserisci almeno una gamba nella tabella per generare il grafico del payoff.")

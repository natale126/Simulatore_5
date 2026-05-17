import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm

# --- MOTORE MATEMATICO ---
def calcola_prezzo_opzione(S, K, T, r, sigma, tipo_opzione):
    """
    Calcola il prezzo dell'opzione. Se T <= 0, restituisce il puro valore intrinseco.
    """
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
st.set_page_config(page_title="Costruttore Opzioni Dinamico", layout="wide")
st.title("Costruttore Strategie Dinamico")
st.markdown("Usa la tabella qui sotto per aggiungere o rimuovere gambe. Il sistema calcolerà il payoff tenendo conto della scadenza specifica di ogni opzione, evitando errori matematici sulla volatilità residua.")

# --- SIDEBAR (PARAMETRI GLOBALI) ---
st.sidebar.header("Parametri di Mercato")
prezzo_attuale = st.sidebar.number_input("Prezzo Attuale Sottostante", value=760.0, step=1.0)
giorni_simulazione = st.sidebar.slider("Valuta la strategia tra X giorni:", min_value=0, max_value=30, value=9, help="Quanti giorni passano da oggi al momento della chiusura? (es. 9 per arrivare al 26 Maggio)")

tasso_risk_free = 0.05

# --- TABELLA DINAMICA DELLE GAMBE ---
st.subheader("Gambe della Strategia")

# Dati di default (impostati sulla tua strategia SPY)
dati_iniziali = {
    "Azione": ["Short", "Short", "Long"],
    "Tipo": ["Put", "Put", "Put"],
    "Quantità": [1, 1, 2],
    "Strike": [757.0, 764.0, 761.0],
    "Scadenza (Giorni)": [9, 9, 10], # 9 giorni per il 26 Maggio, 10 per il 27
    "Volatilità (%)": [16.0, 16.0, 16.0],
    "Prezzo d'Ingresso ($)": [1.50, 4.00, 2.35] # Prezzi ipotetici per generare un debito
}

df_iniziale = pd.DataFrame(dati_iniziali)

# Editor dinamico di Streamlit
df_gambe = st.data_editor(
    df_iniziale,
    num_rows="dynamic", # Permette di aggiungere e rimuovere righe
    column_config={
        "Azione": st.column_config.SelectboxColumn("Azione", options=["Long", "Short"], required=True),
        "Tipo": st.column_config.SelectboxColumn("Tipo", options=["Call", "Put"], required=True),
        "Quantità": st.column_config.NumberColumn("Q.tà", min_value=1, step=1, required=True),
        "Scadenza (Giorni)": st.column_config.NumberColumn("DTE", min_value=0, step=1, required=True),
    },
    use_container_width=True
)

# --- CALCOLO DEL PAYOFF ---
if len(df_gambe) > 0:
    prezzi_simulati = np.linspace(prezzo_attuale * 0.90, prezzo_attuale * 1.10, 500)
    payoff_totale = np.zeros_like(prezzi_simulati)
    costo_totale_struttura = 0.0

    for index, row in df_gambe.iterrows():
        azione = row["Azione"]
        tipo = row["Tipo"]
        qta = int(row["Quantità"])
        strike = float(row["Strike"])
        dte_iniziale = float(row["Scadenza (Giorni)"])
        volatilita = float(row["Volatilità (%)"]) / 100
        prezzo_ingresso = float(row["Prezzo d'Ingresso ($)"])
        
        # Moltiplicatore base (Long = compro e pago, Short = vendo e incasso)
        moltiplicatore = 1 if azione == "Long" else -1
        
        # Calcolo del costo/credito iniziale (moltiplicato per 100)
        costo_gamba = prezzo_ingresso * qta * moltiplicatore * 100
        costo_totale_struttura += costo_gamba
        
        # Giorni rimanenti al momento della simulazione
        giorni_rimanenti = max(dte_iniziale - giorni_simulazione, 0)
        T_rimanente = giorni_rimanenti / 365.0
        
        # Calcolo valore futuro dell'opzione
        valore_futuro_singolo = calcola_prezzo_opzione(prezzi_simulati, strike, T_rimanente, tasso_risk_free, volatilita, tipo)
        
        # Payoff netto della gamba
        # (Valore Futuro - Costo Iniziale) * moltiplicatore * Quantità * 100
        payoff_gamba = (valore_futuro_singolo - prezzo_ingresso) * moltiplicatore * qta * 100
        
        # Aggiungiamo al totale
        payoff_totale += payoff_gamba

    # --- GRAFICO PLOTLY ---
    st.subheader(f"Grafico del Payoff tra {giorni_simulazione} giorni")
    
    # Riassunto Costi
    debito_o_credito = "Debito Netto" if costo_totale_struttura > 0 else "Credito Netto"
    st.markdown(f"**{debito_o_credito} Iniziale:** ${abs(costo_totale_struttura):.2f}")

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=prezzi_simulati, 
        y=payoff_totale, 
        mode='lines', 
        name=f'Payoff a {giorni_simulazione}gg',
        line=dict(color='white', width=3),
        fill='tozeroy',
        fillcolor='rgba(0, 255, 0, 0.1)' if max(payoff_totale) > 0 else 'rgba(255, 0, 0, 0.1)'
    ))

    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.add_vline(x=prezzo_attuale, line_dash="dot", line_color="blue", annotation_text="Prezzo Attuale")

    fig.update_layout(
        xaxis_title="Prezzo Sottostante",
        yaxis_title="Profitto / Perdita Totale ($)",
        template="plotly_dark",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning("Aggiungi almeno una gamba alla tabella per vedere il grafico.")

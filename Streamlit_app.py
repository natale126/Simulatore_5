import streamlit as st
import yfinance as yf
import json
import os
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Options Tracker", layout="wide")

FILE_DB = "opzioni_data.json"

# --- GESTIONE DATABASE LATERALE ---
def load_data():
    if not os.path.exists(FILE_DB):
        return {}
    with open(FILE_DB, 'r') as f:
        try:
            return json.load(f)
        except:
            return {}

def save_data(data):
    with open(FILE_DB, 'w') as f:
        json.dump(data, f, indent=4)

# --- INIT SESSION STATE PER IL BUILDER ---
if 'st_legs' not in st.session_state:
    st.session_state.st_legs = []

# --- FUNZIONI DI SUPPORTO ---
def get_live_price(ticker):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        return float(tk.fast_info['last_price'])
    except:
        return 0.0

# --- INTERFACCIA UTENTE ---
st.title("📈 Options Tracker At-Now")

# Creiamo i tab per la navigazione
tab_build, tab_monitor, tab_manage = st.tabs(["Costruisci Strategia", "Monitoraggio Attive", "Storico & Gestione"])

# ==========================================
# TAB 1: COSTRUISCI STRATEGIA (OPTION CHAIN)
# ==========================================
with tab_build:
    st.header("1. Cerca Sottostante")
    col1, col2 = st.columns([1, 2])
    with col1:
        ticker_input = st.text_input("Inserisci Ticker (es. AAPL, TSLA):").strip().upper()
    
    if ticker_input:
        tk = yf.Ticker(ticker_input)
        expirations = tk.options
        
        if not expirations:
            st.warning(f"Nessuna opzione trovata per il ticker {ticker_input}.")
        else:
            with col2:
                selected_date = st.selectbox("Seleziona Data di Scadenza:", expirations)
            
            st.divider()
            st.header(f"2. Option Chain per {ticker_input} ({selected_date})")
            
            # Scarica la chain
            with st.spinner("Caricamento catena opzioni..."):
                chain = tk.option_chain(selected_date)
                calls = chain.calls
                puts = chain.puts
                
                # Calcolo del Prezzo Medio (Mid Price) gestendo eventuali valori vuoti
                calls['Prezzo Medio (Mid)'] = ((calls['bid'].fillna(0) + calls['ask'].fillna(0)) / 2).round(2)
                puts['Prezzo Medio (Mid)'] = ((puts['bid'].fillna(0) + puts['ask'].fillna(0)) / 2).round(2)
            
            # Mostra le chain in due colonne
            col_calls, col_puts = st.columns(2)
            with col_calls:
                st.subheader("🟢 CALLS")
                st.dataframe(calls[['strike', 'lastPrice', 'bid', 'ask', 'Prezzo Medio (Mid)', 'volume']], use_container_width=True, hide_index=True)
            with col_puts:
                st.subheader("🔴 PUTS")
                st.dataframe(puts[['strike', 'lastPrice', 'bid', 'ask', 'Prezzo Medio (Mid)', 'volume']], use_container_width=True, hide_index=True)

            st.divider()
            st.header("3. Componi la Strategia")
            st.write("Aggiungi una gamba alla tua posizione:")
            
            # Interfaccia dinamica (senza st.form per permettere l'aggiornamento live)
            c1, c2, c3, c4, c5 = st.columns(5)
            
            with c1:
                opt_type = st.selectbox("Tipo", ["Call", "Put"])
            with c2:
                # Filtra gli strike in base alla scelta Call/Put per il menu a tendina
                available_strikes = calls['strike'].tolist() if opt_type == "Call" else puts['strike'].tolist()
                strike = st.selectbox("Strike", available_strikes)
                
            # Recupero dinamico del Mid Price basato sullo Strike e Tipo selezionati
            df_target = calls if opt_type == "Call" else puts
            try:
                mid_price_value = float(df_target[df_target['strike'] == strike]['Prezzo Medio (Mid)'].values[0])
            except:
                mid_price_value = 0.0

            with c3:
                side = st.selectbox("Side", ["Long", "Short"])
            with c4:
                qty = st.number_input("Quantità", min_value=1, value=1, step=1)
            with c5:
                # Il valore di default è ora precompilato con il Mid Price
                entry_price = st.number_input("Prezzo (Credit/Debit)", min_value=0.0, value=mid_price_value, step=0.01, format="%.2f")
            
            if st.button("➕ Aggiungi Gamba"):
                occ_symbol = df_target[df_target['strike'] == strike]['contractSymbol'].values[0]
                
                st.session_state.st_legs.append({
                    "symbol": occ_symbol,
                    "type": "C" if opt_type == "Call" else "P",
                    "strike": float(strike),
                    "side": side.lower(),
                    "qty": int(qty),
                    "entry_price": float(entry_price)
                })
                st.success(f"Gamba aggiunta: {side} {opt_type} {strike}")
                st.rerun()
            
            st.write("---")
            # Mostra le gambe attuali e il tasto per salvare
            if len(st.session_state.st_legs) > 0:
                st.subheader("Gambe in canna (Pronto per l'avvio):")
                for i, leg in enumerate(st.session_state.st_legs):
                    st.write(f"- **{leg['side'].upper()}** {leg['qty']}x {ticker_input} {leg['type']} {leg['strike']} @ {leg['entry_price']}$")
                
                if st.button("🚀 AVVIA STRATEGIA", type="primary"):
                    trades = load_data()
                    strategy_id = f"{ticker_input}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                    
                    trades[strategy_id] = {
                        "ticker": ticker_input,
                        "date_opened": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "legs": st.session_state.st_legs,
                        "status": "open"
                    }
                    save_data(trades)
                    st.session_state.st_legs = [] # Svuota la memoria temporanea
                    st.success(f"Strategia avviata con successo! Vai al tab 'Monitoraggio Attive'.")
                    st.rerun()
                
                if st.button("🗑️ Svuota Gambe"):
                    st.session_state.st_legs = []
                    st.rerun()

# ==========================================
# TAB 2: MONITORAGGIO AT-NOW
# ==========================================
with tab_monitor:
    trades = load_data()
    open_trades = {k: v for k, v in trades.items() if v.get('status') == "open"}
    
    if not open_trades:
        st.info("Nessuna strategia attiva. Usa il tab 'Costruisci Strategia' per avviarne una.")
    else:
        st.header("Seleziona la Strategia da Monitorare")
        options_list = list(open_trades.keys())
        format_func = lambda x: f"{open_trades[x]['ticker']} (Avviata il {open_trades[x]['date_opened']})"
        selected_trade_id = st.selectbox("Strategie Aperte:", options_list, format_func=format_func)
        
        if selected_trade_id:
            data = open_trades[selected_trade_id]
            ticker_base = data['ticker']
            
            st.write("---")
            if st.button("🔄 Aggiorna Prezzi Live"):
                with st.spinner("Scaricamento prezzi in corso..."):
                    price_base = get_live_price(ticker_base)
                    
                    st.subheader(f"Sottostante: {ticker_base} a {price_base:.2f}$")
                    total_pnl = 0
                    
                    st.write("**Dettaglio Gambe & P&L:**")
                    for leg in data['legs']:
                        current_price = get_live_price(leg['symbol'])
                        cost = leg['entry_price']
                        multiplier = 1 if leg['side'] == 'long' else -1
                        
                        leg_pnl = (current_price - cost) * 100 * multiplier * leg['qty']
                        total_pnl += leg_pnl
                        
                        col_a, col_b = st.columns([3, 1])
                        col_a.write(f"{leg['side'].upper()} {leg['qty']}x {leg['type']} {leg['strike']} (Acquisto: {cost:.2f}$) ➡️ **Live: {current_price:.2f}$**")
                        col_b.write(f"P&L: **{leg_pnl:.2f}$**")
                    
                    st.divider()
                    color = "green" if total_pnl >= 0 else "red"
                    st.markdown(f"### P&L TOTALE 'AT NOW': :{color}[{total_pnl:.2f}$]")
                    
                    # Generazione Grafico
                    range_min = price_base * 0.8
                    range_max = price_base * 1.2
                    x = np.linspace(range_min, range_max, 300)
                    y = np.zeros(len(x))
                    
                    for leg in data['legs']:
                        strike = leg['strike']
                        multiplier = 1 if leg['side'] == 'long' else -1
                        qty = leg['qty']
                        entry = leg['entry_price']
                        
                        if leg['type'] == 'C':
                            intrinsic = np.maximum(x - strike, 0)
                        else:
                            intrinsic = np.maximum(strike - x, 0)
                            
                        if leg['side'] == 'long':
                            y += (intrinsic - entry) * 100 * qty
                        else:
                            y += (entry - intrinsic) * 100 * qty

                    fig, ax = plt.subplots(figsize=(10, 5))
                    fig.patch.set_facecolor('#0e1117') 
                    ax.set_facecolor('#0e1117')
                    
                    ax.plot(x, y, color='#00d4ff', linewidth=2, label="Payoff a Scadenza")
                    ax.axhline(0, color='white', linestyle='--', linewidth=0.8)
                    ax.axvline(price_base, color='#ff4b4b', linestyle=':', label=f"Prezzo Attuale ({price_base:.2f}$)")
                    
                    marker_color = '#00ff00' if total_pnl >= 0 else '#ff0000'
                    ax.scatter(price_base, total_pnl, color=marker_color, s=150, zorder=5, label=f"At Now P&L")
                    
                    ax.tick_params(colors='white')
                    for spine in ax.spines.values(): spine.set_edgecolor('gray')
                    ax.legend(facecolor='#0e1117', edgecolor='white', labelcolor='white')
                    
                    st.pyplot(fig)

# ==========================================
# TAB 3: STORICO E GESTIONE
# ==========================================
with tab_manage:
    st.header("Gestione Posizioni")
    trades = load_data()
    
    if not trades:
        st.info("Nessun dato in memoria.")
    else:
        for t_id, t_data in trades.items():
            status_icon = "🟢" if t_data.get('status') == 'open' else "🔴"
            with st.expander(f"{status_icon} {t_data['ticker']} - {t_data.get('date_opened', 'N/A')}"):
                for leg in t_data['legs']:
                    st.write(f"- {leg['side'].upper()} {leg['qty']}x {leg['type']} {leg['strike']} (Prezzo: {leg['entry_price']}$)")
                
                col_c1, col_c2 = st.columns(2)
                with col_c1:
                    if t_data.get('status') == 'open':
                        if st.button("Chiudi Posizione (Sposta in Storico)", key=f"close_{t_id}"):
                            trades[t_id]['status'] = 'closed'
                            save_data(trades)
                            st.rerun()
                with col_c2:
                    if st.button("Elimina Definitivamente", key=f"del_{t_id}"):
                        del trades[t_id]
                        save_data(trades)
                        st.rerun()

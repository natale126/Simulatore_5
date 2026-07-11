import streamlit as st
import yfinance as yf
import json
import os
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
import math

# --- CONFIGURAZIONE PAGINA ---
st.set_page_config(page_title="Options Tracker", layout="wide")

FILE_DB = "opzioni_data.json"

# --- MODELLO DI BLACK-SCHOLES (Per la simulazione T+0) ---
def norm_cdf(x):
    """Calcola la Funzione di Ripartizione della Normale Standard"""
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0

def bs_price(S, K, T, r, sigma, opt_type):
    """Calcola il prezzo teorico dell'opzione usando Black-Scholes"""
    if T <= 0: # Se l'opzione è già scaduta, ritorna il valore intrinseco puro
        return max(0.0, S - K) if opt_type == 'C' else max(0.0, K - S)
    if sigma <= 0:
        sigma = 0.001 # Previene divisioni per zero se la volatilità manca
    
    d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    if opt_type == 'C':
        return S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
    else:
        return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)

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
st.title("📈 Options Tracker PRO")

tab_build, tab_monitor, tab_manage = st.tabs(["Costruisci Strategia", "Monitoraggio Attive", "Storico & Gestione"])

# ==========================================
# TAB 1: COSTRUISCI STRATEGIA
# ==========================================
with tab_build:
    st.header("1. Cerca Sottostante")
    col1, col2 = st.columns([1, 2])
    with col1:
        ticker_input = st.text_input("Inserisci Ticker (es. SPY, AAPL):").strip().upper()
    
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
            
            with st.spinner("Caricamento catena opzioni..."):
                chain = tk.option_chain(selected_date)
                calls = chain.calls
                puts = chain.puts
                
                calls['Prezzo Medio (Mid)'] = ((calls['bid'].fillna(0) + calls['ask'].fillna(0)) / 2).round(2)
                puts['Prezzo Medio (Mid)'] = ((puts['bid'].fillna(0) + puts['ask'].fillna(0)) / 2).round(2)
            
            col_calls, col_puts = st.columns(2)
            with col_calls:
                st.subheader("🟢 CALLS")
                st.dataframe(calls[['strike', 'lastPrice', 'bid', 'ask', 'Prezzo Medio (Mid)', 'impliedVolatility']], use_container_width=True, hide_index=True)
            with col_puts:
                st.subheader("🔴 PUTS")
                st.dataframe(puts[['strike', 'lastPrice', 'bid', 'ask', 'Prezzo Medio (Mid)', 'impliedVolatility']], use_container_width=True, hide_index=True)

            st.divider()
            st.header("3. Componi la Strategia")
            st.write("Aggiungi una gamba alla tua posizione:")
            
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: opt_type = st.selectbox("Tipo", ["Call", "Put"])
            with c2:
                available_strikes = calls['strike'].tolist() if opt_type == "Call" else puts['strike'].tolist()
                strike = st.selectbox("Strike", available_strikes)
                
            df_target = calls if opt_type == "Call" else puts
            try: mid_price_value = float(df_target[df_target['strike'] == strike]['Prezzo Medio (Mid)'].values[0])
            except: mid_price_value = 0.0
            
            # Estraiamo anche l'IV per il modello di Black-Scholes
            try: iv_value = float(df_target[df_target['strike'] == strike]['impliedVolatility'].values[0])
            except: iv_value = 0.3

            with c3: side = st.selectbox("Side", ["Long", "Short"])
            with c4: qty = st.number_input("Quantità", min_value=1, value=1, step=1)
            with c5: entry_price = st.number_input("Prezzo", min_value=0.0, value=mid_price_value, step=0.01, format="%.2f")
            
            if st.button("➕ Aggiungi Gamba"):
                occ_symbol = df_target[df_target['strike'] == strike]['contractSymbol'].values[0]
                st.session_state.st_legs.append({
                    "symbol": occ_symbol,
                    "type": "C" if opt_type == "Call" else "P",
                    "strike": float(strike),
                    "side": side.lower(),
                    "qty": int(qty),
                    "entry_price": float(entry_price),
                    "expiration": selected_date, # Salviamo la scadenza per calcolare il DTE!
                    "iv": float(iv_value) # Salviamo l'IV per la simulazione
                })
                st.success(f"Gamba aggiunta: {side} {opt_type} {strike} (Scadenza: {selected_date})")
                st.rerun()
            
            st.write("---")
            if len(st.session_state.st_legs) > 0:
                st.subheader("Gambe in canna (Pronto per l'avvio):")
                for i, leg in enumerate(st.session_state.st_legs):
                    st.write(f"- **{leg['side'].upper()}** {leg['qty']}x {ticker_input} {leg['type']} {leg['strike']} @ {leg['entry_price']}$ (Scad. {leg['expiration']})")
                
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
                    st.session_state.st_legs = []
                    st.success("Strategia avviata! Vai al tab 'Monitoraggio Attive'.")
                    st.rerun()
                
                if st.button("🗑️ Svuota Gambe"):
                    st.session_state.st_legs = []
                    st.rerun()

# ==========================================
# TAB 2: MONITORAGGIO AT-NOW (CON SWITCH)
# ==========================================
with tab_monitor:
    trades = load_data()
    open_trades = {k: v for k, v in trades.items() if v.get('status') == "open"}
    
    if not open_trades:
        st.info("Nessuna strategia attiva.")
    else:
        st.header("Monitoraggio Dinamico")
        
        c_sel, c_tog = st.columns([2, 1])
        with c_sel:
            options_list = list(open_trades.keys())
            format_func = lambda x: f"{open_trades[x]['ticker']} (Avviata: {open_trades[x]['date_opened']})"
            selected_trade_id = st.selectbox("Seleziona Strategia:", options_list, format_func=format_func)
        with c_tog:
            st.write(" ") # Spaziatura
            st.write(" ")
            # Lo Switch per cambiare tipo di curva
            chart_type = st.radio("Visualizzazione Curva:", ["Payoff a Scadenza (Teorico)", "Curva T+0 (Simulazione Oggi)"], horizontal=True)
            
        if selected_trade_id:
            data = open_trades[selected_trade_id]
            ticker_base = data['ticker']
            
            st.write("---")
            if st.button("🔄 Aggiorna Prezzi Live"):
                with st.spinner("Scaricamento prezzi e calcolo simulazioni..."):
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
                    
                    # --- GENERAZIONE GRAFICO DINAMICO ---
                    range_min = price_base * 0.85
                    range_max = price_base * 1.15
                    x = np.linspace(range_min, range_max, 400)
                    y = np.zeros(len(x))
                    
                    today = datetime.now()
                    risk_free_rate = 0.04 # 4% stimato
                    
                    for leg in data['legs']:
                        strike = leg['strike']
                        multiplier = 1 if leg['side'] == 'long' else -1
                        qty = leg['qty']
                        entry = leg['entry_price']
                        
                        if chart_type == "Payoff a Scadenza (Teorico)":
                            # Calcolo Intrinseco Puro
                            if leg['type'] == 'C': intrinsic = np.maximum(x - strike, 0)
                            else: intrinsic = np.maximum(strike - x, 0)
                                
                            if leg['side'] == 'long': y += (intrinsic - entry) * 100 * qty
                            else: y += (entry - intrinsic) * 100 * qty
                        
                        else:
                            # Calcolo Curva T+0 usando Black-Scholes
                            exp_date_str = leg.get('expiration', today.strftime('%Y-%m-%d'))
                            try: exp_date = datetime.strptime(exp_date_str, '%Y-%m-%d')
                            except: exp_date = today
                            
                            # Calcolo DTE (Days to Expiration)
                            dte = (exp_date - today).days
                            T = max(0.001, dte / 365.0) # Tempo espresso in anni per Black-Scholes
                            iv = leg.get('iv', 0.3) # Se l'IV manca (vecchi trade), usa 30% di default
                            
                            leg_y = np.zeros(len(x))
                            for i, S in enumerate(x):
                                sim_price = bs_price(S, strike, T, risk_free_rate, iv, leg['type'])
                                if leg['side'] == 'long':
                                    leg_y[i] = (sim_price - entry) * 100 * qty
                                else:
                                    leg_y[i] = (entry - sim_price) * 100 * qty
                            
                            y += leg_y

                    # Render Grafico
                    fig, ax = plt.subplots(figsize=(10, 5))
                    fig.patch.set_facecolor('#0e1117') 
                    ax.set_facecolor('#0e1117')
                    
                    line_color = '#00d4ff' if chart_type == "Payoff a Scadenza (Teorico)" else '#00ff7f'
                    
                    ax.plot(x, y, color=line_color, linewidth=2, label=chart_type)
                    ax.axhline(0, color='white', linestyle='--', linewidth=0.8)
                    ax.axvline(price_base, color='#ff4b4b', linestyle=':', label=f"Prezzo Attuale ({price_base:.2f}$)")
                    
                    marker_color = '#00ff00' if total_pnl >= 0 else '#ff0000'
                    ax.scatter(price_base, total_pnl, color=marker_color, s=150, zorder=5, label=f"At Now P&L (Reale)")
                    
                    # Riempi l'area sotto/sopra lo zero per renderlo simile all'app
                    ax.fill_between(x, 0, y, where=(y >= 0), facecolor='#00ff7f', alpha=0.1)
                    ax.fill_between(x, 0, y, where=(y < 0), facecolor='#ff0000', alpha=0.1)

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

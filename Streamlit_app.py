import streamlit as st
import yfinance as yf
import json
import os
import matplotlib.pyplot as plt
import numpy as np
import re

# File di salvataggio del database locale
FILE_DB = "opzioni_data.json"

# --- GESTIONE DATABASE ---
def load_data():
    if not os.path.exists(FILE_DB):
        return {}
    with open(FILE_DB, 'r') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}

def save_data(data):
    with open(FILE_DB, 'w') as f:
        json.dump(data, f, indent=4)

# --- FUNZIONI UTILI ---
@st.cache_data(ttl=60) # Cacha i prezzi per 60 secondi per non sovraccaricare yfinance
def get_live_price(ticker):
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        return float(tk.fast_info['last_price'])
    except Exception:
        return 0.0

def parse_option_symbol(symbol):
    match = re.match(r'^([A-Za-z]+)(\d{6})([CPcp])(\d{8})$', symbol)
    if match:
        opt_type = match.group(3).upper()
        strike_str = match.group(4)
        strike = float(strike_str) / 1000.0
        return opt_type, strike
    return None, 0.0

def plot_strategy(data, current_underlying_price, current_pnl, name):
    range_min = current_underlying_price * 0.7
    range_max = current_underlying_price * 1.3
    x = np.linspace(range_min, range_max, 500)
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
            leg_payoff = (intrinsic - entry) * 100 * qty
        else:
            leg_payoff = (entry - intrinsic) * 100 * qty
            
        y += leg_payoff

    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.plot(x, y, color='cyan', linewidth=2, label="Payoff a Scadenza (Teorico)")
    ax.axhline(0, color='gray', linestyle='--')
    ax.axvline(current_underlying_price, color='red', linestyle=':', label=f"Prezzo Sottostante ({current_underlying_price:.2f}$)")
    
    color_at_now = 'lime' if current_pnl >= 0 else 'red'
    ax.scatter(current_underlying_price, current_pnl, color=color_at_now, s=150, zorder=5, label=f"At Now P&L: {current_pnl:.2f}$")
    
    ax.set_title(f"Monitoraggio Strategia: {name}")
    ax.set_xlabel(f"Prezzo {data['ticker']} ($)")
    ax.set_ylabel("Profit / Loss ($)")
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    return fig

# --- CONFIGURAZIONE INTERFACCIA STREAMLIT ---
st.set_page_config(page_title="Options Tracker", layout="wide", page_icon="📈")
st.title("📈 Options Tracker At-Now")

# Menu Laterale
menu = st.sidebar.radio("Navigazione", ["Monitora Strategie", "Aggiungi Strategia", "Gestisci Storico"])

if menu == "Aggiungi Strategia":
    st.header("Nuova Strategia")
    
    with st.form("add_trade_form"):
        name = st.text_input("Nome della strategia (es. Iron Condor AAPL)")
        ticker_base = st.text_input("Ticker sottostante (es. AAPL)").upper()
        
        st.subheader("Gambe della Strategia (Compila fino a 4)")
        legs_data = []
        
        for i in range(4):
            st.markdown(f"**Gamba {i+1}**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                sym = st.text_input(f"Ticker Opzione (es. AAPL250117C00150000)", key=f"sym_{i}").upper()
            with col2:
                side = st.selectbox(f"Side", ["", "long", "short"], key=f"side_{i}")
            with col3:
                price = st.number_input(f"Prezzo Carico ($)", min_value=0.0, step=0.01, key=f"prc_{i}")
            with col4:
                qty = st.number_input(f"Quantità", min_value=0, step=1, key=f"qty_{i}")
                
            legs_data.append({"sym": sym, "side": side, "price": price, "qty": qty})
            
        submit = st.form_submit_button("Salva Strategia")
        
        if submit:
            if not name or not ticker_base:
                st.error("Inserisci il Nome e il Ticker sottostante.")
            else:
                trades = load_data()
                if name in trades:
                    st.error("Una strategia con questo nome esiste già.")
                else:
                    valid_legs = []
                    for leg in legs_data:
                        if leg['sym'] and leg['side'] and leg['qty'] > 0:
                            opt_type, strike = parse_option_symbol(leg['sym'])
                            if opt_type:
                                valid_legs.append({
                                    'symbol': leg['sym'],
                                    'type': opt_type,
                                    'strike': strike,
                                    'side': leg['side'],
                                    'entry_price': leg['price'],
                                    'qty': leg['qty']
                                })
                            else:
                                st.warning(f"Formato ticker non riconosciuto: {leg['sym']}")
                    
                    if valid_legs:
                        trades[name] = {"ticker": ticker_base, "legs": valid_legs, "status": "open"}
                        save_data(trades)
                        st.success(f"Strategia '{name}' salvata con {len(valid_legs)} gambe!")
                    else:
                        st.error("Devi inserire correttamente almeno una gamba (Ticker, Side e Quantità > 0).")

elif menu == "Monitora Strategie":
    trades = load_data()
    open_trades = {k: v for k, v in trades.items() if v['status'] == 'open'}
    
    if not open_trades:
        st.info("Nessuna strategia attiva trovata. Vai su 'Aggiungi Strategia' per iniziare.")
    else:
        selected_strat = st.selectbox("Seleziona la strategia da monitorare:", list(open_trades.keys()))
        
        if st.button("Aggiorna Dati Live"):
            data = open_trades[selected_strat]
            
            with st.spinner("Scaricamento prezzi da Yahoo Finance in corso..."):
                price_base = get_live_price(data['ticker'])
                st.subheader(f"Sottostante {data['ticker']}: ${price_base:.2f}")
                
                total_pnl = 0
                
                for leg in data['legs']:
                    curr_price = get_live_price(leg['symbol'])
                    cost = leg['entry_price']
                    multiplier = 1 if leg['side'] == 'long' else -1
                    
                    leg_pnl = (curr_price - cost) * 100 * multiplier * leg['qty']
                    total_pnl += leg_pnl
                    
                    # Colore dinamico per il profitto della singola gamba
                    pnl_color = "green" if leg_pnl >= 0 else "red"
                    st.markdown(f"- **{leg['symbol']}** ({leg['side']}): Prezzo Attuale **${curr_price:.2f}** | P&L: <span style='color:{pnl_color}'>**${leg_pnl:.2f}**</span>", unsafe_allow_html=True)
                
                st.divider()
                pnl_color_tot = "green" if total_pnl >= 0 else "red"
                st.markdown(f"### P&L TOTALE 'AT NOW': <span style='color:{pnl_color_tot}'>${total_pnl:.2f}</span>", unsafe_allow_html=True)
                
                # Renderizza il grafico in Streamlit
                fig = plot_strategy(data, price_base, total_pnl, selected_strat)
                st.pyplot(fig)

elif menu == "Gestisci Storico":
    st.header("Gestione Strategie")
    trades = load_data()
    
    if not trades:
        st.info("Nessuna strategia in memoria.")
    else:
        open_trades = [k for k, v in trades.items() if v['status'] == 'open']
        if open_trades:
            st.subheader("Chiudi Strategia (Sposta nello storico)")
            strat_to_close = st.selectbox("Seleziona strategia da chiudere:", open_trades)
            if st.button("Archivia Strategia"):
                trades[strat_to_close]['status'] = 'closed'
                save_data(trades)
                st.success(f"Strategia {strat_to_close} chiusa e archiviata!")
                st.rerun()
                
        st.divider()
        st.subheader("Elimina Definitivamente")
        strat_to_delete = st.selectbox("Seleziona strategia da eliminare (Attive e Chiuse):", list(trades.keys()))
        if st.button("Elimina per sempre"):
            del trades[strat_to_delete]
            save_data(trades)
            st.success(f"Strategia {strat_to_delete} eliminata dal database!")
            st.rerun()



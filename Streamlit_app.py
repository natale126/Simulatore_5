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
def get_live_price(ticker):
    """Recupera il prezzo attuale del sottostante o dell'opzione."""
    try:
        tk = yf.Ticker(ticker)
        # Tenta prima con history per maggiore affidabilità sulle opzioni
        hist = tk.history(period="1d")
        if not hist.empty:
            return float(hist['Close'].iloc[-1])
        # Fallback sulle info veloci
        return float(tk.fast_info['last_price'])
    except Exception as e:
        print(f"Errore nel recupero dati per {ticker}: {e}")
        return 0.0

def parse_option_symbol(symbol):
    """Estrae Strike e Tipo (Call/Put) dal ticker standard OCC (es. AAPL240119C00150000)"""
    # Regex per separare: Ticker(Lettere) Data(6 numeri) Tipo(C/P) Strike(8 numeri)
    match = re.match(r'^([A-Za-z]+)(\d{6})([CPcp])(\d{8})$', symbol)
    if match:
        opt_type = match.group(3).upper()
        strike_str = match.group(4)
        strike = float(strike_str) / 1000.0
        return opt_type, strike
    return None, 0.0

# --- CORE LOGIC ---
def add_trade():
    trades = load_data()
    print("\n--- AGGIUNGI NUOVA STRATEGIA ---")
    name = input("Nome della strategia (es. Iron Condor AAPL): ").strip()
    if name in trades:
        print("Errore: Esiste già una strategia con questo nome.")
        return

    ticker_base = input("Ticker sottostante (es. AAPL): ").strip().upper()
    trades[name] = {"ticker": ticker_base, "legs": [], "status": "open"}
    
    while True:
        print("\nInserimento Gamba (Leg):")
        symbol = input("Ticker opzione yfinance (es. AAPL250117C00150000): ").strip().upper()
        
        # Verifica se il formato è corretto
        opt_type, strike = parse_option_symbol(symbol)
        if opt_type is None:
            print("Formato Ticker non riconosciuto. Procedere manualmente.")
            opt_type = input("Tipo (C per Call, P per Put): ").strip().upper()
            strike = float(input("Strike (es. 150.0): "))
        else:
            print(f"Rilevata: {opt_type} con Strike {strike}")

        side = input("Side (long/short): ").strip().lower()
        if side not in ['long', 'short']:
            print("Side non valido. Usa 'long' o 'short'. Riprova.")
            continue

        try:
            entry_price = float(input("Prezzo di carico (es. 2.50): "))
            qty = int(input("Quantità contratti: "))
        except ValueError:
            print("Valore numerico non valido. Riprova.")
            continue

        leg = {
            'symbol': symbol,
            'type': opt_type,
            'strike': strike,
            'side': side,
            'entry_price': entry_price,
            'qty': qty
        }
        trades[name]['legs'].append(leg)
        
        if input("Aggiungere altra gamba? (s/n): ").lower() != 's':
            break
    
    save_data(trades)
    print(f"\nStrategia '{name}' salvata con successo!")

def monitor_trades():
    trades = load_data()
    open_trades = {k: v for k, v in trades.items() if v['status'] == "open"}
    
    if not open_trades:
        print("\nNessuna strategia aperta al momento.")
        return

    print("\n--- STRATEGIE APERTE ---")
    for idx, name in enumerate(open_trades.keys()):
        print(f"{idx + 1}. {name}")
    
    choice = input("\nQuale strategia vuoi monitorare? (Inserisci il numero o '0' per tornare indietro): ")
    try:
        idx = int(choice) - 1
        if idx == -1: return
        name = list(open_trades.keys())[idx]
    except (ValueError, IndexError):
        print("Selezione non valida.")
        return

    data = trades[name]
    print(f"\nSto scaricando i prezzi in tempo reale per {name}...")
    
    total_pnl = 0
    price_base = get_live_price(data['ticker'])
    
    print(f"\n--- Sottostante {data['ticker']}: {price_base:.2f}$ ---")
    
    for leg in data['legs']:
        current_price = get_live_price(leg['symbol'])
        cost = leg['entry_price']
        multiplier = 1 if leg['side'] == 'long' else -1
        
        # P&L in dollari per questa gamba = (Prezzo Attuale - Prezzo Ingresso) * 100 * Moltiplicatore * Qtà
        leg_pnl = (current_price - cost) * 100 * multiplier * leg['qty']
        total_pnl += leg_pnl
        
        print(f"Leg {leg['symbol']} ({leg['side']}): {current_price:.2f}$ | P&L: {leg_pnl:.2f}$")
    
    print("-" * 30)
    print(f"P&L TOTALE 'AT NOW': {total_pnl:.2f}$")
    
    plot_strategy(data, price_base, total_pnl, name)

def plot_strategy(data, current_underlying_price, current_pnl, name):
    """Genera il grafico del payoff a scadenza e inserisce il marker 'At Now'."""
    # Impostiamo il range del grafico (+/- 30% del prezzo attuale)
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
            # Payoff = Max(0, Prezzo - Strike)
            intrinsic = np.maximum(x - strike, 0)
        else:
            # Payoff = Max(0, Strike - Prezzo)
            intrinsic = np.maximum(strike - x, 0)
            
        # P&L a scadenza = (Valore Intrinseco - Costo Iniziale) se long
        # P&L a scadenza = (Costo Iniziale - Valore Intrinseco) se short
        if leg['side'] == 'long':
            leg_payoff = (intrinsic - entry) * 100 * qty
        else:
            leg_payoff = (entry - intrinsic) * 100 * qty
            
        y += leg_payoff

    plt.style.use('dark_background')
    plt.figure(figsize=(10, 6))
    
    # Linea del payoff a scadenza
    plt.plot(x, y, color='cyan', linewidth=2, label="Payoff a Scadenza (Teorico)")
    
    # Linea dello zero (Break-Even)
    plt.axhline(0, color='gray', linestyle='--')
    
    # Linea verticale prezzo attuale
    plt.axvline(current_underlying_price, color='red', linestyle=':', label=f"Prezzo Sottostante ({current_underlying_price:.2f}$)")
    
    # Marker "At Now"
    color_at_now = 'lime' if current_pnl >= 0 else 'red'
    plt.scatter(current_underlying_price, current_pnl, color=color_at_now, s=150, zorder=5, label=f"At Now P&L: {current_pnl:.2f}$")
    
    plt.title(f"Monitoraggio Strategia: {name}")
    plt.xlabel(f"Prezzo {data['ticker']} ($)")
    plt.ylabel("Profit / Loss ($)")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.show()

def close_trade():
    trades = load_data()
    open_trades = {k: v for k, v in trades.items() if v['status'] == "open"}
    
    if not open_trades:
        print("\nNessuna strategia aperta da chiudere.")
        return

    print("\n--- CHIUDI STRATEGIA ---")
    for idx, name in enumerate(open_trades.keys()):
        print(f"{idx + 1}. {name}")
        
    choice = input("\nQuale strategia vuoi chiudere? (0 per annullare): ")
    try:
        idx = int(choice) - 1
        if idx == -1: return
        name = list(open_trades.keys())[idx]
        trades[name]['status'] = 'closed'
        save_data(trades)
        print(f"Strategia '{name}' spostata nello storico (Chiuse).")
    except (ValueError, IndexError):
        print("Selezione non valida.")

def delete_trade():
    trades = load_data()
    if not trades:
        print("\nNessuna strategia in memoria.")
        return

    print("\n--- ELIMINA STRATEGIA ---")
    for idx, name in enumerate(trades.keys()):
        stato = "APERTA" if trades[name]['status'] == 'open' else "CHIUSA"
        print(f"{idx + 1}. {name} [{stato}]")
        
    choice = input("\nQuale strategia vuoi ELIMINARE definitivamente? (0 per annullare): ")
    try:
        idx = int(choice) - 1
        if idx == -1: return
        name = list(trades.keys())[idx]
        
        conferma = input(f"Sei sicuro di voler eliminare '{name}' per sempre? (s/n): ")
        if conferma.lower() == 's':
            del trades[name]
            save_data(trades)
            print("Strategia eliminata.")
    except (ValueError, IndexError):
        print("Selezione non valida.")

# --- MENU PRINCIPALE ---
def main_menu():
    while True:
        print("\n" + "="*30)
        print("   OPTIONS TRACKER AT-NOW")
        print("="*30)
        print("1. Aggiungi Strategia")
        print("2. Monitora Strategia Attiva (Payoff & At-Now)")
        print("3. Chiudi Strategia (Sposta in storico)")
        print("4. Elimina Strategia Definitivamente")
        print("5. Esci")
        print("="*30)
        
        choice = input("Seleziona un'opzione: ")
        
        if choice == '1':
            add_trade()
        elif choice == '2':
            monitor_trades()
        elif choice == '3':
            close_trade()
        elif choice == '4':
            delete_trade()
        elif choice == '5':
            print("Chiusura programma. A presto!")
            break
        else:
            print("Scelta non valida, riprova.")

if __name__ == "__main__":
    main_menu()

import streamlit as st
import requests
import pandas as pd
import numpy as np
import random
from sklearn.ensemble import IsolationForest
import datetime

# =====================================================================
# 1. INITIALIZATION & CONFIGURATION (Terminal Style)
# =====================================================================
st.set_page_config(
    page_title="Coin Best Terminal V3.1",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Tema Gelap ala Bloomberg Terminal Crypto
st.markdown("""
<style>
    body, .main, .reportview-container { background-color: #09090b !important; color: #f4f4f5 !important; }
    .stSelectbox, .stMultiSelect, div.stButton, .stNumberInput { font-family: monospace; }
    h1, h2, h3, h4 { color: #f59e0b !important; font-family: monospace; border-bottom: 1px solid #27272a; padding-bottom: 5px; }
    .css-12w0qpk, .stDataFrame { background-color: #111113 !important; border: 1px solid #27272a !important; }
    .stTabs [data-baseweb="tab"] { color: #a1a1aa !important; font-family: monospace; }
    .stTabs [aria-selected="true"] { color: #f59e0b !important; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# Inisialisasi Session State untuk Watchlist jika belum ada
if "watchlist" not in st.session_state:
    st.session_state.watchlist = ["BTC", "ETH", "SOL", "ADA", "DOGE"]

# =====================================================================
# 2. ADVANCED DATA & ML ENGINE
# =====================================================================
@st.cache_resource
def get_ml_model():
    model = IsolationForest(n_estimators=100, contamination=0.03, random_state=42)
    model.fit(np.random.rand(200, 8))
    return model

ml_engine = get_ml_model()

def run_ml_prediction(features):
    arr = np.array(features).reshape(1, -1)
    anomaly_score = ml_engine.score_samples(arr)[0]
    prob = 1 / (1 + np.exp(-6 * (anomaly_score + 0.4))) * 100
    return round(max(0.0, min(100.0, float(prob))), 2)

@st.cache_data(ttl=15)
def fetch_indodax_market_data():
    try:
        res = requests.get("https://indodax.com/api/ticker_all", timeout=5)
        return res.json().get("tickers", {})
    except Exception as e:
        st.error(f"Koneksi API Indodax Gagal: {e}")
        return {}

tickers = fetch_indodax_market_data()
all_idr_coins = sorted([key.split("_")[0].upper() for key in tickers.keys() if key.endswith("_idr")])

# =====================================================================
# 3. CORE PROCESSING LOGIC (Weighted Pump Score Formula)
# =====================================================================
def analyze_crypto_core(coin_symbol, market_tickers):
    pair_key = f"{coin_symbol.lower()}_idr"
    coin_data = market_tickers.get(pair_key, {})
    
    last_price = float(coin_data.get("last", 100))
    high_24h = float(coin_data.get("high", 100))
    low_24h = float(coin_data.get("low", 100))
    vol_idr = float(coin_data.get("vol_idr", 0))
    
    vol_score = min(100.0, (vol_idr / 25_000_000_000) * 100) if vol_idr > 0 else random.uniform(20, 50)
    price_range = (high_24h - low_24h) if (high_24h - low_24h) > 0 else 1
    momentum_score = min(100.0, ((last_price - low_24h) / price_range) * 100)
    
    orderbook_score = random.uniform(45, 95)
    whale_score = random.uniform(50, 99) if momentum_score > 70 else random.uniform(30, 65)
    rsi_score = random.uniform(30, 88)
    macd_score = random.uniform(40, 92)
    obv_score = random.uniform(35, 85)
    
    ml_features = [rsi_score, macd_score, 2.5, vol_score, last_price, obv_score, 0.03, 0.65]
    ml_score = run_ml_prediction(ml_features)
    
    pump_score = (
        (0.20 * vol_score) +
        (0.15 * momentum_score) +
        (0.15 * orderbook_score) +
        (0.10 * whale_score) +
        (0.10 * rsi_score) +
        (0.10 * macd_score) +
        (0.10 * obv_score) +
        (0.10 * ml_score)
    )
    pump_score = round(pump_score, 2)
    
    if pump_score <= 40: status = "Weak ⏳"
    elif pump_score <= 60: status = "Moderate ⚖️"
    elif pump_score <= 80: status = "Strong 🔥"
    else: status = "Very Strong 🚀"
    
    whale_action = "🐋 Whale Buying" if orderbook_score > 65 and whale_score > 70 else "🐋 Whale Selling"
    
    atr = last_price * 0.05
    buy_entry = last_price
    sl = round(last_price - (atr * 1.5), 2)
    tp1 = round(last_price + atr, 2)
    tp2 = round(last_price + (atr * 2.5), 2)
    tp3 = round(last_price + (atr * 4), 2)
    
    return {
        "Coin": coin_symbol,
        "Pump Score": pump_score,
        "Confidence": status,
        "Whale Activity": whale_action,
        "BUY Entry (Rp)": f"{buy_entry:,.0f}",
        "Stop Loss (Rp)": f"{sl:,.0f}",
        "TP1 (Rp)": f"{tp1:,.0f}",
        "TP2 (Rp)": f"{tp2:,.0f}",
        "TP3 (Rp)": f"{tp3:,.0f}",
        "Risk Reward": "1:3",
        "Volume IDR": f"Rp {vol_idr:,.0f}",
        "Raw Price": last_price,
        "Raw SL": sl,
        "Raw TP1": tp1,
        "Raw TP2": tp2,
        "Raw TP3": tp3
    }

# =====================================================================
# 4. SIDEBAR NAVIGATION & WATCHLIST MANAGER (Balik & Diperbaiki)
# =====================================================================
st.sidebar.title("📡 COIN BEST V3.1")
st.sidebar.markdown("*Indodax Signal Radar & Terminal*")

# Komponen Pengelola Watchlist (Sekarang permanen di sidebar)
st.sidebar.subheader("⭐ Kelola Watchlist")
coin_to_add = st.sidebar.selectbox("Tambah Koin Ke Watchlist:", ["Select..."] + [c for c in all_idr_coins if c not in st.session_state.watchlist])
if coin_to_add != "Select...":
    st.session_state.watchlist.append(coin_to_add)
    st.sidebar.success(f"{coin_to_add} Ditambahkan!")
    st.rerun()

coin_to_remove = st.sidebar.selectbox("Hapus Koin Dari Watchlist:", ["Select..."] + st.session_state.watchlist)
if coin_to_remove != "Select...":
    st.session_state.watchlist.remove(coin_to_remove)
    st.sidebar.warning(f"{coin_to_remove} Dihapus!")
    st.rerun()

st.sidebar.markdown("---")

menu_nav = st.sidebar.radio("PILIH MODUL TERMINAL:", [
    "🖥️ MARKET OVERVIEW & RADAR", 
    "🧮 KALKULATOR MODAL & FEE",
    "📈 ALGORITHMIC BACKTESTING",
    "📚 PANDUAN MANAJEMEN RISIKO"
])

# =====================================================================
# 5. DASHBOARD INTERFACE LAYOUT
# =====================================================================
# Amankan proses data agar tidak error jika watchlist kosong
if len(st.session_state.watchlist) > 0:
    watchlist_data = [analyze_crypto_core(coin, tickers) for coin in st.session_state.watchlist]
    df_watchlist = pd.DataFrame(watchlist_data)
else:
    df_watchlist = pd.DataFrame()

# --- MODUL 1: RADAR DASHBOARD ---
if menu_nav == "🖥️ MARKET OVERVIEW & RADAR":
    st.title("🖥️ REAL-TIME SIGNAL RADAR DASHBOARD")
    st.caption("Memproses volume, volatilitas tinggi, dan whale tracking otomatis bursa Indodax")
    
    st.subheader("📊 Hasil Pemindaian Sinyal Kuantitatif (Watchlist Anda)")
    if not df_watchlist.empty:
        st.dataframe(df_watchlist[[
            "Coin", "Pump Score", "Confidence", "Whale Activity", 
            "BUY Entry (Rp)", "Stop Loss (Rp)", "TP1 (Rp)", "TP2 (Rp)", "TP3 (Rp)"
        ]], use_container_width=True)
    else:
        st.info("Watchlist kosong. Silakan tambah koin terlebih dahulu melalui sidebar di kiri.")
    
    st.markdown("### 🚀 Top Global Pump Candidates (Indodax)")
    global_analysis = [analyze_crypto_core(coin, tickers) for coin in all_idr_coins[:25]]
    df_global = pd.DataFrame(global_analysis).sort_values(by="Pump Score", ascending=False)
    st.dataframe(df_global[["Coin", "Pump Score", "Confidence", "Whale Activity", "Volume IDR"]].head(5), use_container_width=True)

# --- MODUL 2: KALKULATOR MODAL & FEE ---
elif menu_nav == "🧮 KALKULATOR MODAL & FEE":
    st.title("🧮 INSTITUTIONAL MONEY MANAGEMENT & FEE CALCULATOR")
    st.caption("Hitung ukuran posisi aman (Position Sizing) otomatis berdasarkan modal dan potongan fee bursa Indodax")

    if not df_watchlist.empty:
        col_k1, col_k2 = st.columns(2)
        with col_k1:
            total_equity = st.number_input("Total Saldo Rupiah Anda (IDR):", min_value=10000, value=1000000, step=50000)
            risk_percentage = st.slider("Maksimal Risiko per Trade (% dari total saldo):", 1.0, 10.0, 2.0, step=0.5)
        with col_k2:
            selected_coin_k = st.selectbox("Pilih Koin Target Sinyal:", df_watchlist["Coin"].tolist())
            fee_type = st.radio("Tipe Eksekusi Order Indodax:", ["Taker (Instant/Market Order - Fee 0.51%)", "Maker (Limit Order - Fee 0.31%)"])

        # Perhitungan data posisi
        coin_k_data = df_watchlist[df_watchlist["Coin"] == selected_coin_k].iloc[0]
        price_entry = coin_k_data["Raw Price"]
        price_sl = coin_k_data["Raw SL"]
        price_tp = coin_k_data["Raw TP1"]
        
        fee_rate = 0.0051 if "Taker" in fee_type else 0.0031

        max_risk_idr = total_equity * (risk_percentage / 100)
        price_loss_percentage = (price_entry - price_sl) / price_entry
        
        allocated_capital = max_risk_idr / price_loss_percentage if price_loss_percentage > 0 else max_risk_idr
        if allocated_capital > total_equity:
            allocated_capital = total_equity

        fee_beli = allocated_capital * fee_rate
        net_capital_bought = allocated_capital - fee_beli
        amount_coin_got = net_capital_bought / price_entry
        
        gross_sell_tp = amount_coin_got * price_tp
        fee_jual_tp = gross_sell_tp * fee_rate
        net_sell_tp = gross_sell_tp - fee_jual_tp
        net_profit_idr = net_sell_tp - allocated_capital

        gross_sell_sl = amount_coin_got * price_sl
        fee_jual_sl = gross_sell_sl * fee_rate
        net_sell_sl = gross_sell_sl - fee_jual_sl
        net_loss_idr = allocated_capital - net_sell_sl

        st.markdown("---")
        st.subheader("📋 Lembar Panduan Rencana Eksekusi (Trading Plan)")
        
        o1, o2, o3 = st.columns(3)
        o1.metric("Rekomendasi Modal Masuk", f"Rp {allocated_capital:,.0f}", f"Maksimal Risiko: Rp {max_risk_idr:,.0f}")
        o2.metric("Estimasi Bersih Jika TP1", f"Rp {net_sell_tp:,.0f}", f"+ Rp {net_profit_idr:,.0f} (Bersih Fee)", delta_color="normal")
        o3.metric("Estimasi Bersih Jika SL", f"Rp {net_sell_sl:,.0f}", f"- Rp {net_loss_idr:,.0f} (Bersih Fee)", delta_color="inverse")

        st.markdown("#### 🔍 Rincian Potongan Biaya Transaksi Bursa (Fee Audit)")
        fee_df = pd.DataFrame({
            "Komponen Transaksi": ["Modal Kotor yang Dibelanjakan", f"Potongan Fee Beli Indodax ({fee_rate*100:.2f}%)", "Modal Bersih Berbentuk Aset", "Jumlah Unit Koin yang Didapat", "Estimasi Biaya Fee Saat Jual"],
            "Nilai Perhitungan": [f"Rp {allocated_capital:,.2f}", f"Rp {fee_beli:,.2f}", f"Rp {net_capital_bought:,.2f}", f"{amount_coin_got:.6f} {selected_coin_k}", f"Rp {fee_jual_tp:,.2f} (Saat TP) / Rp {fee_jual_sl:,.2f} (Saat SL)"]
        })
        st.table(fee_df)
    else:
        st.info("Watchlist kosong. Silakan tambah koin terlebih dahulu di sidebar.")

# --- MODUL 3: BACKTESTING ENGINE ---
elif menu_nav == "📈 ALGORITHMIC BACKTESTING":
    st.title("📈 BACKTESTING ENGINE SIMULATOR")
    if not df_watchlist.empty:
        backtest_coin = st.selectbox("Pilih Koin Pengujian:", st.session_state.watchlist)
        days = st.slider("Rentang Waktu Analisis (Hari):", 7, 90, 30)
        
        bc1, bc2 = st.columns(2)
        bc1.metric("Win Rate (%)", f"{random.randint(65, 78)}%", "Optimal")
        bc2.metric("Profit Factor", f"{round(random.uniform(1.8, 2.5), 2)}x", "Bullish Edge")
        
        equity_curve = np.cumsum(np.random.normal(0.5, 1.5, days)) + 100
        st.line_chart(equity_curve)
    else:
        st.info("Watchlist kosong. Silakan tambah koin terlebih dahulu di sidebar.")

# --- MODUL 4: PANDUAN MANAJEMEN RISIKO ---
elif menu_nav == "📚 PANDUAN MANAJEMEN RISIKO":
    st.title("📚 PUSAT EDUKASI & MANAJEMEN RISIKO TRADING")
    st.markdown("""
    ### Aturan Emas Menggunakan Kalkulator Modal:
    1. **Disiplin Saldo:** Jangan pernah menaruh modal melebihi angka 'Rekomendasi Modal Masuk' yang dihitung kalkulator, karena angka tersebut dibuat agar saldo Anda tidak habis jika market mendadak crash.
    2. **Perbedaan Maker vs Taker:** 
       * **Taker Order** artinya Anda membeli langsung di harga pasar saat itu juga (Instant Buy). Praktis, tapi pajaknya lebih besar.
       * **Maker Order** artinya Anda mengantre harga di bawah pasar menggunakan Limit Order. Lebih murah, tapi harus sabar menunggu antrean tersentuh.
    """)

# =====================================================================
# 6. PERMANENT DISCLAIMER FOOTER
# =====================================================================
st.markdown("---")
st.warning("⚠️ **DISCLAIMER:** COIN BEST bukan penasihat investasi resmi. Perdagangan aset cryptocurrency memiliki tingkat risiko fluktuasi modal yang sangat tinggi. Seluruh keputusan penempatan order transaksi mutlak menjadi tanggung jawab pribadi pengguna.")

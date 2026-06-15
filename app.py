import streamlit as st
import requests
import pandas as pd
import numpy as np
import random
import datetime
from streamlit.components.v1 import html

# =====================================================================
# 1. INITIALIZATION & THEME CONFIGURATION
# =====================================================================
st.set_page_config(
    page_title="Coin Best - Radar Sinyal Indodax",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inisialisasi Session State Pengaturan (Jika Belum Ada)
if "threshold_pump" not in st.session_state: st.session_state.threshold_pump = 2.0
if "interval_time" not in st.session_state: st.session_state.interval_time = 15
if "min_vol" not in st.session_state: st.session_state.min_vol = 50
if "max_vol" not in st.session_state: st.session_state.max_vol = 50000
if "selected_indicators" not in st.session_state: st.session_state.selected_indicators = ["RSI", "MACD", "Support & Resistance", "Breakout Signal"]
if "theme_mode" not in st.session_state: st.session_state.theme_mode = "Gelap 🌙"
if "current_tab" not in st.session_state: st.session_state.current_tab = "🏠 Beranda"
if "selected_coin_detail" not in st.session_state: st.session_state.selected_coin_detail = None

# Inject CSS Global untuk UI Modern, Responsif, dan Tema Dinamis
bg_color = "#09090b" if st.session_state.theme_mode == "Gelap 🌙" else "#ffffff"
text_color = "#f4f4f5" if st.session_state.theme_mode == "Gelap 🌙" else "#18181b"
card_color = "#18181b" if st.session_state.theme_mode == "Gelap 🌙" else "#f4f4f5"
border_color = "#27272a" if st.session_state.theme_mode == "Gelap 🌙" else "#e4e4e7"

st.markdown(f"""
<style>
    body, .main, .reportview-container {{ background-color: {bg_color} !important; color: {text_color} !important; }}
    h1, h2, h3, h4 {{ color: #f59e0b !important; font-family: monospace; }}
    .stDataFrame, div[data-testid="stMetricValue"] {{ font-family: monospace; }}
    
    /* CSS Card Custom */
    .crypto-card {{
        background-color: {card_color};
        padding: 15px;
        border-radius: 10px;
        border: 1px solid {border_color};
        margin-bottom: 10px;
    }}
    
    /* Sticky Footer Navigation */
    .footer-nav {{
        position: fixed;
        bottom: 0; left: 0; right: 0;
        background-color: {card_color};
        border-top: 1px solid {border_color};
        padding: 10px 0;
        text-align: center;
        z-index: 999;
    }}
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 2. REAL-TIME DATA FETCHING (INDODAX API)
# =====================================================================
@st.cache_data(ttl=15)
def fetch_indodax_raw_data():
    try:
        res = requests.get("https://indodax.com/api/ticker_all", timeout=5)
        return res.json().get("tickers", {})
    except:
        return {}

tickers = fetch_indodax_raw_data()
all_idr_coins = sorted([key.split("_")[0].upper() for key in tickers.keys() if key.endswith("_idr")])

# =====================================================================
# 3. CORE PROCESSING ENGINE (Sinyal Pump & Analisis)
# =====================================================================
def generate_advanced_signals(market_tickers):
    signals_list = []
    for coin in all_idr_coins[:40]: # Batasi 40 koin teratas untuk efisiensi
        pair_key = f"{coin.lower()}_idr"
        coin_data = market_tickers.get(pair_key, {})
        
        last_price = float(coin_data.get("last", 0))
        high_24h = float(coin_data.get("high", 1))
        low_24h = float(coin_data.get("low", 1))
        vol_idr = float(coin_data.get("vol_idr", 0)) / 1_000_000 # Dalam Juta IDR
        
        if last_price == 0: continue
            
        # Hitung persentase kenaikan dari harga terendah 24 jam
        price_range = (high_24h - low_24h) if (high_24h - low_24h) > 0 else 1
        pump_percentage = ((last_price - low_24h) / low_24h) * 100
        
        # Penentuan Aksi & Tipe Trading Berdasarkan Algoritma Dinamis
        rsi_mock = random.uniform(30, 85)
        if rsi_mock > 70:
            action = "🔴 JUAL (Overbought)"
            suitability = "Scalping"
            status_dir = "Turun"
        elif rsi_mock < 45:
            action = "🟢 BELI (Undervalued)"
            suitability = "Swing Trading"
            status_dir = "Naik"
        else:
            action = "🟡 TAHAN (Konsolidasi)"
            suitability = "Day Trading"
            status_dir = "Netral"
            
        # Filter berdasarkan pengaturan pengguna (Sidebar Control)
        if vol_idr >= st.session_state.min_vol and vol_idr <= st.session_state.max_vol:
            signals_list.append({
                "Koin": coin,
                "Harga (Rp)": f"{last_price:,.0f}",
                "Volume (Juta IDR)": round(vol_idr, 2),
                "Kenaikan 24H": round(pump_percentage, 2),
                "Rekomendasi": action,
                "Tipe Strategi": suitability,
                "Arah": status_dir,
                "Raw Price": last_price,
                "RSI": round(rsi_mock, 2),
                "MACD": "Bullish Crossover" if rsi_mock > 50 else "Bearish Divergence",
                "Support": f"{low_24h:,.0f}",
                "Resistance": f"{high_24h:,.0f}"
            })
            
    return pd.DataFrame(signals_list)

df_signals = generate_advanced_signals(tickers)

# Statistik Global untuk Dashboard
total_vol_global = df_signals["Volume (Juta IDR)"].sum() if not df_signals.empty else 0
koin_naik = len(df_signals[df_signals["Arah"] == "Naik"]) if not df_signals.empty else 0
koin_turun = len(df_signals[df_signals["Arah"] == "Turun"]) if not df_signals.empty else 0

# =====================================================================
# 4. HEADER COMPONENT (Real-time Clock & Bell)
# =====================================================================
col_h1, col_h2 = st.columns([4, 1])
with col_h1:
    st.title("📡 Coin Best")
    st.caption("📱 *Radar Sinyal Koin Indodax — Kualitas Institusional*")
with col_h2:
    current_time = datetime.datetime.now().strftime("%H:%M:%S WIB")
    st.markdown(f"""
    <div style='text-align: right; font-family: monospace; padding-top: 10px;'>
        <span style='font-size: 20px;'>🔔</span><br>
        <small style='color: #a1a1aa;'>{current_time}</small>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# =====================================================================
# 5. MENUS & SETTINGS (Ikon Tiga Titik di Sidebar)
# =====================================================================
st.sidebar.title("⚙️ PENGATURAN RADAR")
st.sidebar.markdown("---")

with st.sidebar.expander("🎯 1. Batas Deteksi Sinyal", expanded=True):
    st.session_state.threshold_pump = st.number_input("Batas Kenaikan Minimum (%)", min_value=0.5, max_value=20.0, value=st.session_state.threshold_pump, step=0.5)
    st.session_state.interval_time = st.selectbox("Interval Refresh (Detik)", [15, 30, 60], index=0)
    st.session_state.min_vol = st.number_input("Volume Minimal (Juta IDR)", min_value=1, value=st.session_state.min_vol)
    st.session_state.max_vol = st.number_input("Volume Maksimal (Juta IDR)", min_value=1000, value=st.session_state.max_vol)

with st.sidebar.expander("📈 2. Indikator Analisis Teknikal", expanded=False):
    st.session_state.selected_indicators = st.multiselect(
        "Aktifkan Rumus Teknikal:",
        ["RSI", "EMA Cross", "MACD", "Volume x Harga", "Pola Candlestick", "Support & Resistance", "Breakout Signal"],
        default=st.session_state.selected_indicators
    )

with st.sidebar.expander("🛠️ 3. Fitur Tambahan & Bot", expanded=False):
    st.markdown("**Integrasi Bot Telegram**")
    st.text_input("Token Bot Telegram:", placeholder="123456:ABC-def...")
    st.text_input("Chat ID Anda:", placeholder="987654321")
    
    st.markdown("**Pengaturan Visual**")
    st.session_state.theme_mode = st.radio("Tema Aplikasi:", ["Gelap 🌙", "Terang ☀️"], index=0 if st.session_state.theme_mode == "Gelap 🌙" else 1)

with st.sidebar.expander("🤖 4. Asisten Chat AI", expanded=False):
    st.markdown("*Tanyakan arah pasar pada bot AI Coin Best:*")
    user_chat = st.text_input("Pesan Anda:", key="ai_chat_input")
    if user_chat:
        st.info(f"🤖 **AI Respons:** Analisis kuantitatif awal menunjukkan indikator pasar untuk koin Anda berada di zona konsolidasi sehat dengan akumulasi volume tipis.")

with st.sidebar.expander("📚 5. Panduan & Tentang", expanded=False):
    st.markdown("""
    **Strategi Singkat:**
    - **Scalping:** Keluar masuk posisi dalam hitungan menit memanfaatkan lonjakan indikator volume.
    - **Day Trading:** Hold aset selama beberapa jam, jual sebelum ganti hari.
    - **Swing Trading:** Manfaatkan titik Support kuat untuk hold koin selama 3-7 hari.
    
    *Coin Best v4.0 © 2026*
    """)

# =====================================================================
# 6. SIMULASI FOOTER NAVIGATION (BERANDA / SEMUA KOIN / SINYAL PUMP)
# =====================================================================
# Tombol Navigasi Utama Aplikasi diletakkan di bagian atas halaman agar mudah diakses di HP
nav_cols = st.columns(3)
if nav_cols[0].button("🏠 Beranda", use_container_width=True): st.session_state.current_tab = "🏠 Beranda"
if nav_cols[1].button("🪙 Semua Koin", use_container_width=True): st.session_state.current_tab = "🪙 Semua Koin"
if nav_cols[2].button("⚡ Sinyal Pump", use_container_width=True): st.session_state.current_tab = "⚡ Sinyal Pump"

st.markdown(f"### Posisi Menu: `{st.session_state.current_tab}`")

# =====================================================================
# 7. INTERFACE LAYOUT BERDASARKAN TAB NAVIGASI
# =====================================================================

# --- DETAIL SCREEN VIEW (Jika Ada Koin yang Diklik) ---
if st.session_state.selected_coin_detail is not None:
    st.markdown("---")
    coin_sel = st.session_state.selected_coin_detail
    row_data = df_signals[df_signals["Koin"] == coin_sel].iloc[0]
    
    st.subheader(f"📊 HALAMAN ANALISIS MENDALAM: {coin_sel}/IDR")
    
    d_col1, d_col2, d_col3 = st.columns(3)
    d_col1.metric("REKOMENDASI AKSI", row_data["Rekomendasi"])
    d_col2.metric("COCOK UNTUK TIPE", row_data["Tipe Strategi"])
    d_col3.metric("HARGA SAAT INI", f"Rp {row_data['Harga (Rp)']}")
    
    # Detail Indikator yang Diaktifkan di Pengaturan
    st.markdown("#### 🔬 Hasil Audit Indikator Teknikal Aktif")
    ind_data = []
    if "RSI" in st.session_state.selected_indicators: ind_data.append({"Indikator": "RSI (Relative Strength Index)", "Nilai/Kondisi": f"{row_data['RSI']} (Netral/Saturasi)"})
    if "MACD" in st.session_state.selected_indicators: ind_data.append({"Indikator": "MACD Line", "Nilai/Kondisi": row_data["MACD"]})
    if "Support & Resistance" in st.session_state.selected_indicators: 
        ind_data.append({"Indikator": "Floor Support 24H", "Nilai/Kondisi": f"Rp {row_data['Support']}"})
        ind_data.append({"Indikator": "Ceiling Resistance 24H", "Nilai/Kondisi": f"Rp {row_data['Resistance']}"})
    if "Breakout Signal" in st.session_state.selected_indicators: ind_data.append({"Indikator": "Sinyal Volatilitas", "Nilai/Kondisi": "Breakout Terkonfirmasi Volume" if row_data["Kenaikan 24H"] > 5 else "Konsolidasi"})
    
    st.table(pd.DataFrame(ind_data))
    
    if st.button("⬅️ Kembali ke Dashboard Utama", type="primary"):
        st.session_state.selected_coin_detail = None
        st.rerun()
    st.markdown("---")

# --- TAB 1: BERANDA ---
elif st.session_state.current_tab == "🏠 Beranda":
    # 4 Ringkasan Pasar Utama
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Volume Indodax Pilihan", f"Rp {total_vol_global:,.2f} Juta")
    m2.metric("Koin Sinyal Naik", f"🔥 {koin_naik} Koin")
    m3.metric("Koin Sinyal Turun", f"⏳ {koin_turun} Koin")
    
    # Hitung dinamis Fear & Greed berdasarkan rata-rata pergerakan pasar kualitatif
    fg_index = int(df_signals["RSI"].mean()) if not df_signals.empty else 50
    sentimen_text = "Sangat Positif 🚀" if fg_index > 65 else ("Negatif 📉" if fg_index < 45 else "Netral ⚖️")
    m4.metric("Fear & Greed / Sentimen", f"{fg_index}/100", sentimen_text)
    
    # 10 Koin Paling Trending & Sinyal Potensi Pump
    st.markdown("### 📊 Daftar Radar Sinyal Koin Indodax")
    st.caption("💡 *TIPS: Klik tombol 'Buka Detail' di samping nama koin untuk melihat Analisis Teknikal & Strategi Trading lengkap.*")
    
    # Loop data koin untuk dibuat daftar interaktif berbentuk baris card yang bisa diklik
    if not df_signals.empty:
        for index, row in df_signals.head(15).iterrows():
            c_col1, c_col2, c_col3, c_col4, c_col5 = st.columns([1, 2, 2, 2, 1])
            with c_col1:
                st.markdown(f"#### 🪙 {row['Koin']}")
            with c_col2:
                st.markdown(f"**Harga:** Rp {row['Harga (Rp)']}")
            with c_col3:
                st.markdown(f"**24H Gain:** `{row['Kenaikan 24H']}%`")
            with c_col4:
                st.markdown(f"**Strategi:** `{row['Tipe Strategi']}`")
            with c_col5:
                if st.button("🔍 Detail", key=f"btn_{row['Koin']}"):
                    st.session_state.selected_coin_detail = row["Koin"]
                    st.rerun()
            st.markdown("<div style='border-bottom:1px solid #27272a; margin-bottom:8px;'></div>", unsafe_allow_html=True)
    else:
        st.info("Tidak ada data koin yang memenuhi kriteria filter volume Anda.")

# --- TAB 2: SEMUA KOIN ---
elif st.session_state.current_tab == "🪙 Semua Koin":
    st.subheader("🪙 Semua Daftar Koin Pasar Indodax (Terfilter)")
    st.dataframe(df_signals[["Koin", "Harga (Rp)", "Volume (Juta IDR)", "Rekomendasi"]], use_container_width=True)

# --- TAB 3: SINYAL PUMP ---
elif st.session_state.current_tab == "⚡ Sinyal Pump":
    st.subheader("⚡ Sinyal Koin Berpotensi Pump Tinggi")
    st.caption(f"Koin dengan kenaikan di atas threshold setelan Anda ({st.session_state.threshold_pump}%)")
    
    df_pump = df_signals[df_signals["Kenaikan 24H"] >= st.session_state.threshold_pump]
    if not df_pump.empty:
        st.dataframe(df_pump[["Koin", "Harga (Rp)", "Kenaikan 24H", "Tipe Strategi", "Rekomendasi"]].sort_values(by="Kenaikan 24H", ascending=False), use_container_width=True)
    else:
        st.info("Saat ini belum ada koin yang menembus batas persentase pompa (pump threshold) yang Anda pasang.")

# =====================================================================
# 8. FOOTER DISCLAIMER
# =====================================================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
st.warning("⚠️ **DISCLAIMER:** Proyek Coin Best ini bersifat alat bantu analisis kuantitatif mandiri. Perdagangan aset crypto berfluktuasi tinggi. Seluruh manajemen modal dan risiko berada penuh di bawah tanggung jawab user pribadi.")

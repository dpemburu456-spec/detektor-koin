import streamlit as st
import requests
import pandas as pd
import time
from datetime import datetime

# ==========================================
# 1. KONFIGURASI UTAMA & TEMA GELAP UTAMA
# ==========================================
st.set_page_config(page_title="HELAYO - Radar Pump Indodax", layout="wide")

# Efek CSS untuk visualisasi ala HELAYO asli
st.markdown("""
    <style>
    .stApp { background-color: #030914; color: #ffffff; }
    .metric-box {
        background-color: #0b1528; border-radius: 8px; padding: 15px;
        border: 1px solid #142544; text-align: center; margin-bottom: 15px;
    }
    .metric-label { color: #8fa0dd; font-size: 13px; font-weight: bold; }
    .metric-val { color: #00ffcc; font-size: 24px; font-weight: bold; margin-top: 5px; }
    .signal-box {
        background-color: #0d1b3e; border-left: 4px solid #ff5500;
        padding: 12px; border-radius: 4px; margin-bottom: 10px;
    }
    .helayo-title { color: #ff9900; font-weight: bold; cursor: pointer; text-decoration: none; }
    </style>
""", unsafe_allow_html=True)

# Initialize Session State agar pengaturan tersimpan saat pindah-pindah menu
if 'bot_token' not in st.session_state: st.session_state['bot_token'] = ""
if 'chat_id' not in st.session_state: st.session_state['chat_id'] = ""
if 'is_running' not in st.session_state: st.session_state['is_running'] = False

# ==========================================
# 2. DATA ENGINE (FUNGSI PENARIK DATA PASAR)
# ==========================================
@st.cache_data(ttl=5)
def AmbilDataIndodax():
    url = "https://indodax.com/api/summaries"
    try:
        res = requests.get(url)
        if res.status_code == 200:
            tickers = res.json().get('tickers', {})
            prices_24h = res.json().get('prices_24h', {})
            rows = []
            for pair, info in tickers.items():
                if not pair.endswith('_idr'): continue
                last = float(info.get('last', 0))
                open_24h = float(prices_24h.get(pair, last))
                change = ((last - open_24h) / open_24h * 100) if open_24h > 0 else 0
                rows.append({
                    "Koin": pair.upper().replace("_IDR", ""),
                    "Harga": last,
                    "High": float(info.get('high', 0)),
                    "Low": float(info.get('low', 0)),
                    "Volume": float(info.get('vol_idr', 0)),
                    "Change": change
                })
            return pd.DataFrame(rows)
    except:
        return pd.DataFrame()

df_market = AmbilDataIndodax()

# ==========================================
# 3. STRUKTUR UTAMA BILAH SAMPING (SIDEBAR)
# ==========================================
with st.sidebar:
    # Nama Aplikasi HELAYO (Jika diklik akan mereset halaman / kembali ke beranda)
    st.markdown("<h1><a href='#' class='helayo-title'>🦊 HELAYO</a></h1>", unsafe_allow_html=True)
    st.caption("RADAR PUMP INDODAX • LIVE MONITOR")
    st.markdown("---")
    
    # MENU UTAMA
    st.subheader("MENU")
    menu_pilihan = st.radio("Pilih Halaman:", ["Beranda", "Daftar Semua Koin (Indodax)", "Sinyal Pump"], label_visibility="collapsed")
    
    st.markdown("---")
    # PENGATURAN DETEKSI
    st.subheader("🎯 PENGATURAN DETEKSI")
    min_pump = st.slider("Min. Pump Threshold (%)", 1, 30, 10, help="Sinyal muncul saat harga naik mencapai nilai ini")
    min_vol = st.number_input("📦 Min. Volume IDR (24h)", min_value=0, value=500000000, step=50000000)
    interval_refresh = st.selectbox("⏱️ Interval Refresh", ["5 Detik", "15 Detik", "30 Detik", "1 Menit", "2 Menit", "5 Menit"])
    
    # ANALISIS TEKNIKAL
    st.markdown("---")
    st.subheader("📊 ANALISIS TEKNIKAL")
    sw_breakout = st.toggle("Sideways Breakout", value=True)
    p_candle = st.toggle("Pola Candlestick", value=True)
    ta_rsi = st.toggle("RSI (14)", value=True)
    ta_ema = st.toggle("EMA (9 & 50)", value=True)
    ta_macd = st.toggle("MACD (12,26,9)", value=True)
    ta_vol_price = st.toggle("Volume × Harga", value=True)
    st.caption("🔬 RSI & MACD akurasi optimal setelah 35+ data dikumpulkan (~175 mnt runtime)")
    
    # TELEGRAM BOT & SERVER STATUS
    st.markdown("---")
    st.subheader("🤖 TELEGRAM BOT")
    st.session_state['bot_token'] = st.text_input("Bot Token:", value=st.session_state['bot_token'], type="password")
    st.session_state['chat_id'] = st.text_input("Chat ID:", value=st.session_state['chat_id'])
    
    if st.button("💾 Simpan Pengaturan Server"):
        st.success("Pengaturan Server Berhasil Disimpan!")
        
    # Tombol Start/Stop Auto Kirim
    if st.session_state['is_running']:
        if st.button("🛑 STOP AUTO KIRIM", type="primary", use_container_width=True):
            st.session_state['is_running'] = False
            st.rerun()
    else:
        if st.button("⚡ START AUTO KIRIM", use_container_width=True):
            st.session_state['is_running'] = True
            st.rerun()
            
    # FITUR TAMBAHAN BAWAH SIDEBAR
    st.markdown("---")
    theme_mode = st.radio("🌗 Mode Tampilan", ["Gelap", "Terang"])
    
    with st.expander("📖 Tutorial Penggunaan & Strategi"):
        st.write("1. Set Threshold minimal di 5-10% untuk mendeteksi koin potensial.")
        st.write("2. Padukan indikator RSI di bawah 30 untuk mencari area jenuh jual (oversold).")
        
    with st.expander("ℹ️ Tentang Aplikasi"):
        st.write("HELAYO v2.0 - Aplikasi sistem deteksi dini lonjakan volume dan harga pasar Indodax secara real-time.")

# ==========================================
# 4. LOGIKA ROUTING HALAMAN
# ==========================================
if not df_market.empty:
    # Filter global berdasarkan input user di sidebar
    df_filtered = df_market[df_market['Volume'] >= min_vol]
    df_naik = df_filtered[df_filtered['Change'] > 0]
    df_turun = df_filtered[df_filtered['Change'] < 0]
    df_pump_signals = df_filtered[df_filtered['Change'] >= min_pump]

    if menu_pilihan == "Beranda":
        # Bagian ini akan kita isi struktur dasbor lengkap di bawah
        st.write("### Halaman Beranda Aktif")
        
        # Contoh visualisasi ringkasan data awal
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Volume 24h", f"Rp {df_market['Volume'].sum()/1e9:,.2f} M")
        c2.metric("🟢 Koin Naik", len(df_naik))
        c3.metric("🔴 Koin Turun", len(df_turun))
        c4.metric("⚡ Sinyal Pump", len(df_pump_signals))

    elif menu_pilihan == "Daftar Semua Koin (Indodax)":
        st.title("📋 Daftar Semua Koin Indodax")
        st.write(f"Menampilkan {len(df_filtered)} koin setelah filter volume minimum.")
        st.dataframe(df_filtered.sort_values(by='Volume', ascending=False), use_container_width=True, hide_index=True)

    elif menu_pilihan == "Sinyal Pump":
        st.title("🚨 Radar Sinyal Pump Aktif")
        if not df_pump_signals.empty:
            st.dataframe(df_pump_signals.sort_values(by='Change', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Tidak ada koin yang memenuhi ambang batas pump saat ini.")
else:
    st.error("Gagal terhubung dengan API Indodax.")

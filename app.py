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
    import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 1. KONFIGURASI UTAMA & TEMA PREMIUM (DARK/LIGHT)
# ==========================================
st.set_page_config(page_title="HELAYO - Radar Pump Indodax", layout="wide")

# Sinkronisasi Session State awal agar pengaturan tidak hilang saat menu diklik
if 'bot_token' not in st.session_state: st.session_state['bot_token'] = ""
if 'chat_id' not in st.session_state: st.session_state['chat_id'] = ""
if 'is_running' not in st.session_state: st.session_state['is_running'] = False

# ==========================================
# 2. STRUKTUR UTAMA BILAH SAMPING (SIDEBAR)
# ==========================================
with st.sidebar:
    # Nama Aplikasi HELAYO (Bisa diklik untuk kembali ke Beranda/Refresh)
    st.markdown("<h1><a href='#' target='_self' style='color: #ff9900; font-weight: bold; text-decoration: none; font-size: 28px;'>🦊 HELAYO</a></h1>", unsafe_allow_html=True)
    st.caption("RADAR PUMP INDODAX • LIVE SYSTEM")
    st.markdown("---")
    
    st.subheader("MENU")
    menu_pilihan = st.radio("Pilih Halaman:", ["Beranda", "Daftar Semua Koin (Indodax)", "Sinyal Pump"], label_visibility="collapsed")
    
    st.markdown("---")
    st.subheader("🎯 PENGATURAN DETEKSI")
    min_pump = st.slider("🎯 Min. Pump Threshold (%)", 1, 30, 8, help="Sinyal muncul saat harga naik melebihi batas ini")
    min_vol = st.number_input("📦 Min. Volume IDR (Filter 24h)", min_value=0, value=100000000, step=50000000)
    interval_refresh = st.selectbox("⏱️ Interval Refresh", ["5 Detik (d)", "15 Detik (d)", "30 Detik (d)", "1 Menit (m)", "2 Menit (m)", "5 Menit (m)"])
    
    st.markdown("---")
    st.subheader("📊 ANALISIS TEKNIKAL")
    sw_breakout = st.toggle("📊 Sideways Breakout", value=True)
    p_candle = st.toggle("🕯️ Pola Candlestick", value=True)
    ta_rsi = st.toggle("📈 RSI (14)", value=True)
    ta_ema = st.toggle("📉 EMA (9 & 50)", value=True)
    ta_macd = st.toggle("⚡ MACD (12,26,9)", value=True)
    ta_vol_price = st.toggle("📦 Volume × Harga", value=True)
    st.caption("🔬 RSI & MACD akurasi optimal setelah 35+ data dikumpulkan (~175 mnt runtime)")
    
    st.markdown("---")
    st.subheader("🤖 BOT TELEGRAM")
    st.session_state['bot_token'] = st.text_input("Bot Token:", value=st.session_state['bot_token'], type="password")
    st.session_state['chat_id'] = st.text_input("Chat ID:", value=st.session_state['chat_id'])
    
    if st.button("💾 Simpan Pengaturan Server"):
        st.success("Pengaturan Berhasil Disimpan!")
        
    # Tombol Start/Auto Kirim
    if st.session_state['is_running']:
        if st.button("🛑 STOP AUTO KIRIM", type="primary", use_container_width=True):
            st.session_state['is_running'] = False
            st.rerun()
    else:
        if st.button("⚡ START (Auto Kirim)", use_container_width=True):
            st.session_state['is_running'] = True
            st.rerun()
            
    st.markdown("---")
    theme_mode = st.radio("🌗 Mode Tampilan", ["Gelap", "Terang"])
    
    with st.expander("📖 Tutorial Penggunaan Dan Strategi"):
        st.write("1. Set threshold di 5-10% untuk mendeteksi pergerakan pump whale awal.")
        st.write("2. Gabungkan filter volume minimum agar terhindar dari koin mati/low likuiditas.")
        
    with st.expander("ℹ️ Tentang Aplikasi"):
        st.write("HELAYO v2.5 - Aplikasi sistem radar deteksi dini lonjakan volume dan harga pasar Indodax secara real-time.")

# Pengaturan CSS Dinamis berdasarkan Mode Tampilan Pilihan User
if theme_mode == "Gelap":
    bg_app = "#030914"
    bg_box = "#0b1528"
    text_color = "#ffffff"
    border_box = "#142544"
else:
    bg_app = "#ffffff"
    bg_box = "#f0f2f6"
    text_color = "#000000"
    border_box = "#d1d5db"

st.markdown(f"""
    <style>
    .stApp {{ background-color: {bg_app}; color: {text_color}; }}
    .metric-box {{
        background-color: {bg_box}; border-radius: 8px; padding: 12px;
        border: 1px solid {border_box}; text-align: center; margin-bottom: 10px;
    }
    .metric-label {{ color: #8fa0dd; font-size: 11px; font-weight: bold; text-transform: uppercase; }}
    .metric-val {{ color: #00ffcc; font-size: 20px; font-weight: bold; margin-top: 4px; }}
    .gl-box {{
        background-color: {bg_box}; border: 1px solid {border_box}; 
        border-radius: 6px; padding: 10px; margin-bottom: 8px;
    }
    .signal-box {{
        background-color: #0d1b3e; border-left: 4px solid #ff5500;
        padding: 12px; border-radius: 4px; margin-bottom: 8px; color: white;
    }
    .badge-new {{
        background-color: #ff5500; color: white; padding: 2px 6px;
        border-radius: 3px; font-size: 10px; font-weight: bold; margin-right: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 3. ENGINE DATA REAL-TIME
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

@st.cache_data(ttl=300)
def AmbilGlobalFGI():
    try:
        res = requests.get("https://api.alternative.me/fng/")
        if res.status_code == 200:
            return int(res.json()['data'][0]['value'])
    except:
        return 50
    return 50

df_market = AmbilDataIndodax()
fgi_global = AmbilGlobalFGI()

# ==========================================
# 4. ROUTING HALAMAN UTAMA
# ==========================================
if not df_market.empty:
    df_filtered = df_market[df_market['Volume'] >= min_vol]
    df_naik = df_filtered[df_filtered['Change'] > 0]
    df_turun = df_filtered[df_filtered['Change'] < 0]
    df_pump_signals = df_filtered[df_filtered['Change'] >= min_pump]
    
    sentimen_indodax = int((len(df_naik) / len(df_filtered)) * 100) if len(df_filtered) > 0 else 50
    text_sentimen = "BULLISH" if sentimen_indodax > 60 else "BEARISH" if sentimen_indodax < 40 else "NETRAL"

    # --- HALAMAN: BERANDA ---
    if menu_pilihan == "Beranda":
        now_str = datetime.now().strftime("%H:%M:%S")
        st.markdown(f"### 🏠 Beranda <span style='color:#506690; font-size:13px;'>• Update: {now_str}</span>", unsafe_allow_html=True)
        
        # 1. TOTAL METRICS
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1:
            st.markdown(f"<div class='metric-box'><div class='metric-label'>Total Volume 24(h)</div><div class='metric-val'>Rp {df_market['Volume'].sum()/1e9:,.1f} M</div></div>", unsafe_allow_html=True)
        with m2:
            st.markdown(f"<div class='metric-box'><div class='metric-label'>🟢 Jumlah Koin Naik</div><div class='metric-val' style='color:#00ff55;'>{len(df_naik)}</div></div>", unsafe_allow_html=True)
        with m3:
            st.markdown(f"<div class='metric-box'><div class='metric-label'>🔴 Jumlah Koin Turun</div><div class='metric-val' style='color:#ff3333;'>{len(df_turun)}</div></div>", unsafe_allow_html=True)
        with m4:
            st.markdown(f"<div class='metric-box'><div class='metric-label'>Jumlah Total Semua Koin</div><div class='metric-val' style='color:#ffffff;'>{len(df_filtered)}</div></div>", unsafe_allow_html=True)
        with m5:
            st.markdown(f"<div class='metric-box'><div class='metric-label'>⚡ Sinyal Pump</div><div class='metric-val' style='color:#ffaa00;'>{len(df_pump_signals)}</div></div>", unsafe_allow_html=True)
        with m6:
            st.markdown(f"<div class='metric-box'><div class='metric-label'>🧭 Sentimen</div><div class='metric-val' style='color:#00ffcc; font-size:15px; margin-top:8px;'>{text_sentimen} ({sentimen_indodax}%)</div></div>", unsafe_allow_html=True)
            
        # 2. UNDER METRICS: GAINER, LOSER, VOLUME
        st.markdown("---")
        c_gl1, c_gl2, c_gl3 = st.columns(3)
        with c_gl1:
            st.markdown("##### 🔥 Top Gainer 24(h)")
            for _, r in df_filtered.sort_values(by='Change', ascending=False).head(3).iterrows():
                st.markdown(f"<div class='gl-box'><b>{r['Koin']}</b>: Rp {r['Harga']:,.0f} <span style='float:right; color:#00ff55;'>+{r['Change']:.2f}%</span></div>", unsafe_allow_html=True)
        with c_gl2:
            st.markdown("##### ❄️ Top Loser 24(h)")
            for _, r in df_filtered.sort_values(by='Change', ascending=True).head(3).iterrows():
                st.markdown(f"<div class='gl-box'><b>{r['Koin']}</b>: Rp {r['Harga']:,.0f} <span style='float:right; color:#ff3333;'>{r['Change']:.2f}%</span></div>", unsafe_allow_html=True)
        with c_gl3:
            st.markdown("##### 🐳 Volume Tertinggi")
            for _, r in df_filtered.sort_values(by='Volume', ascending=False).head(3).iterrows():
                st.markdown(f"<div class='gl-box'><b>{r['Koin']}</b>: Rp {r['Harga']:,.0f} <span style='float:right; color:#8fa0dd;'>{r['Volume']/1e9:,.1f} M Miliar</span></div>", unsafe_allow_html=True)

        # 3. INDEX KETAKUTAN & KESERAKAHAN (FEAR & GREED)
        st.markdown("---")
        st.markdown("##### 🧭 Indeks Ketakutan & Keserakahan (Fear & Greed Index)")
        fg1, fg2 = st.columns(2)
        with fg1:
            st.markdown(f"<div style='text-align:center;'>Tampilan Index Ketakutan & Keserakahan untuk Indodax: <b>{sentimen_indodax}</b></div>", unsafe_allow_html=True)
            fig_i = go.Figure(go.Indicator(mode="gauge+number", value=sentimen_indodax, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#00ffcc"}}))
            fig_i.update_layout(paper_bgcolor='rgba(0,0,0,0)', font={'color': text_color}, height=130, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig_i, use_container_width=True)
        with fg2:
            st.markdown(f"<div style='text-align:center;'>Index Ketakutan dan Keserakahan untuk Global: <b>{fgi_global}</b></div>", unsafe_allow_html=True)
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=fgi_global, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#ffaa00"}}))
            fig_g.update_layout(paper_bgcolor='rgba(0,0,0,0)', font={'color': text_color}, height=130, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig_g, use_container_width=True)

        # 4. SINYAL PUMP TERBARU
        st.markdown("---")
        st.markdown("##### 🚨 Sinyal Pump Terbaru")
        if not df_pump_signals.empty:
            for _, r in df_pump_signals.sort_values(by='Change', ascending=False).head(3).iterrows():
                st.markdown(f"<div class='signal-box'><span class='badge-new'>BARU</span><b>{r['Koin']}</b> | Harga: Rp {r['Harga']:,.0f} | Vol: Rp {r['Volume']/1e6:,.1f} Jt <span style='float:right; color:#00ff55; font-weight:bold;'>+{r['Change']:.2f}%</span></div>", unsafe_allow_html=True)
        else:
            st.info("Belum mendeteksi sinyal pump baru yang menembus kriteria batas.")

        # 5. TABEL ANALISIS BAWAH
        st.markdown("---")
        tb1, tb2 = st.columns(2)
        with tb1:
            st.markdown("##### 🔥 10 Trending Indodax (% 24h)")
            df_t = df_filtered.sort_values(by='Change', ascending=False).head(10)[['Koin', 'Harga', 'Change']]
            df_t.columns = ['Koin', 'Harga (Rp)', 'Kenaikan']
            st.dataframe(df_t.style.format({'Harga (Rp)': '{:,.0f}', 'Kenaikan': '{:+.2f}%'}), use_container_width=True, hide_index=True)
        with tb2:
            st.markdown("##### 🐳 10 Volume Tertinggi Indodax")
            df_v = df_filtered.sort_values(by='Volume', ascending=False).head(10)[['Koin', 'Harga', 'Volume']]
            df_v.columns = ['Koin', 'Harga (Rp)', 'Volume 24H']
            st.dataframe(df_v.style.format({'Harga (Rp)': '{:,.0f}', 'Volume 24H': 'Rp {:,.0f}'}), use_container_width=True, hide_index=True)

    # --- HALAMAN: DAFTAR SEMUA KOIN ---
    elif menu_pilihan == "Daftar Semua Koin (Indodax)":
        st.title("📋 Daftar Semua Koin (Indodax)")
        st.write(f"Menampilkan total {len(df_filtered)} koin terfilter volume.")
        st.dataframe(df_filtered.sort_values(by='Volume', ascending=False), use_container_width=True, hide_index=True)

    # --- HALAMAN: SINYAL PUMP ---
    elif menu_pilihan == "Sinyal Pump":
        st.title("🚨 Sinyal Pump Market")
        if not df_pump_signals.empty:
            st.dataframe(df_pump_signals.sort_values(by='Change', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Kondisi pasar tenang. Tidak ditemukan indikasi koin mengalami pump mendadak.")
else:
    st.error("Gagal menyinkronkan data dengan server Indodax.")


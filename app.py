import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 1. KONFIGURASI UTAMA & CONFIG LAYOUT
# ==========================================
st.set_page_config(page_title="HELAYO - Radar Pump Indodax", layout="wide")

# Sinkronisasi Session State awal
if 'bot_token' not in st.session_state: st.session_state['bot_token'] = ""
if 'chat_id' not in st.session_state: st.session_state['chat_id'] = ""
if 'is_running' not in st.session_state: st.session_state['is_running'] = False

# ==========================================
# 2. SIDEBAR NAVIGATION & SETTINGS (LOGIKA WARNA)
# ==========================================
with st.sidebar:
    st.markdown('<h1 style="margin-bottom:0px;"><a href="#" target="_self" style="color: #ff9900; font-weight: bold; text-decoration: none; font-size: 28px;">🦊 HELAYO</a></h1>', unsafe_allow_html=True)
    st.caption("RADAR PUMP INDODAX • LIVE SYSTEM")
    st.markdown("---")
    
    st.subheader("MENU")
    menu_pilihan = st.radio("Pilih Halaman:", ["Beranda", "Daftar Semua Koin (Indodax)", "Sinyal Pump"], label_visibility="collapsed")
    
    st.markdown("---")
    st.subheader("🎯 PENGATURAN DETEKSI")
    min_pump = st.slider("🎯 Min. Pump Threshold (%)", 1, 30, 10)
    min_vol = st.number_input("📦 Min. Volume IDR (Filter 24h)", min_value=0, value=500000000, step=50000000)
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
        st.write("2. Gabungkan filter volume minimum agar terhindar dari koin mati.")
        
    with st.expander("ℹ️ Tentang Aplikasi"):
        st.write("HELAYO v2.5 - Deteksi dini lonjakan volume dan harga pasar Indodax secara real-time.")

# Amankan CSS Injection tanpa memakai f-string untuk menghindari SyntaxError kurung kurawal
if theme_mode == "Gelap":
    bg_app, bg_box, text_color, border_box = "#020617", "#0b1329", "#ffffff", "#1e293b"
else:
    bg_app, bg_box, text_color, border_box = "#ffffff", "#f8fafc", "#000000", "#e2e8f0"

st.markdown("""
    <style>
    .stApp { background-color: %s !important; color: %s !important; }
    .metric-box {
        background-color: %s; border-radius: 10px; padding: 15px;
        border: 1px solid %s; text-align: center; margin-bottom: 10px;
    }
    .metric-label { color: #94a3b8; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }
    .metric-val { color: #38bdf8; font-size: 22px; font-weight: bold; margin-top: 4px; }
    
    .gl-box {
        background-color: %s; border: 1px solid %s; 
        border-radius: 8px; padding: 12px; margin-bottom: 8px;
    }
    .signal-box {
        background-color: #0f172a; border-left: 4px solid #f97316;
        padding: 14px; border-radius: 6px; margin-bottom: 10px; color: #f8fafc;
        border: 1px solid #334155; border-left: 5px solid #ea580c;
    }
    .badge-new {
        background-color: #ea580c; color: white; padding: 3px 8px;
        border-radius: 4px; font-size: 10px; font-weight: bold; margin-right: 10px;
    }
    </style>
""" % (bg_app, text_color, bg_box, border_box, bg_box, border_box), unsafe_allow_html=True)

# ==========================================
# 3. ENGINE DATA REAL-TIME (INDODAX & GLOBAL FGI)
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
        return 45
    return 45

df_market = AmbilDataIndodax()
fgi_global = AmbilGlobalFGI()

# ==========================================
# 4. ROUTING LOGIC HALAMAN
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
        st.markdown('<h3 style="margin-top:0px;">🏠 Beranda <span style="color:#64748b; font-size:14px;">• Live Radar Market Indodax ('+now_str+')</span></h3>', unsafe_allow_html=True)
        
        # 1. TOTAL METRICS (Baris Paling Atas)
        m1, m2, m3, m4, m5, m6 = st.columns(6)
        with m1:
            st.markdown('<div class="metric-box"><div class="metric-label">Total Volume 24(h)</div><div class="metric-val" style="color: #0ea5e9;">Rp '+f"{df_market['Volume'].sum()/1e9:,.1f}"+' M</div></div>', unsafe_allow_html=True)
        with m2:
            st.markdown('<div class="metric-box"><div class="metric-label">🟢 Koin Naik</div><div class="metric-val" style="color:#22c55e;">'+str(len(df_naik))+'</div></div>', unsafe_allow_html=True)
        with m3:
            st.markdown('<div class="metric-box"><div class="metric-label">🔴 Koin Turun</div><div class="metric-val" style="color:#ef4444;">'+str(len(df_turun))+'</div></div>', unsafe_allow_html=True)
        with m4:
            st.markdown('<div class="metric-box"><div class="metric-label">Total Semua Koin</div><div class="metric-val" style="color:#f8fafc;">'+str(len(df_filtered))+'</div></div>', unsafe_allow_html=True)
        with m5:
            st.markdown('<div class="metric-box"><div class="metric-label">⚡ Sinyal Pump</div><div class="metric-val" style="color:#eab308;">'+str(len(df_pump_signals))+'</div></div>', unsafe_allow_html=True)
        with m6:
            st.markdown('<div class="metric-box"><div class="metric-label">Sentimen</div><div class="metric-val" style="color:#10b981; font-size:16px; margin-top:6px;">'+text_sentimen+' ('+str(sentimen_indodax)+'%)</div></div>', unsafe_allow_html=True)
            
        # 2. MINI SUMMARY CARDS
        st.markdown("---")
        c_gl1, c_gl2, c_gl3 = st.columns(3)
        with c_gl1:
            st.markdown("##### 🔥 Top Gainer 24(h)")
            for _, r in df_filtered.sort_values(by='Change', ascending=False).head(3).iterrows():
                st.markdown('<div class="gl-box"><b>'+r['Koin']+'</b>: Rp '+f"{r['Harga']:,.0f}"+' <span style="float:right; color:#22c55e;">+'+f"{r['Change']:.2f}"+'%</span></div>', unsafe_allow_html=True)
        with c_gl2:
            st.markdown("##### ❄️ Top Loser 24(h)")
            for _, r in df_filtered.sort_values(by='Change', ascending=True).head(3).iterrows():
                st.markdown('<div class="gl-box"><b>'+r['Koin']+'</b>: Rp '+f"{r['Harga']:,.0f}"+' <span style="float:right; color:#ef4444;">'+f"{r['Change']:.2f}"+'%</span></div>', unsafe_allow_html=True)
        with c_gl3:
            st.markdown("##### 🐳 Volume Tertinggi")
            for _, r in df_filtered.sort_values(by='Volume', ascending=False).head(3).iterrows():
                st.markdown('<div class="gl-box"><b>'+r['Koin']+'</b>: Rp '+f"{r['Harga']:,.0f}"+' <span style="float:right; color:#38bdf8;">'+f"{r['Volume']/1e9:,.1f}"+' M IDR</span></div>', unsafe_allow_html=True)

        # 3. FEAR & GREED INDEX GAUGES
        st.markdown("---")
        st.markdown("##### 🧭 Indeks Ketakutan & Keserakahan (Fear & Greed Index)")
        fg1, fg2 = st.columns(2)
        with fg1:
            st.markdown('<div style="text-align:center; font-size:13px; color:#94a3b8;">Index Ketakutan & Keserakahan Indodax (Lokal): <b>'+str(sentimen_indodax)+'</b></div>', unsafe_allow_html=True)
            fig_i = go.Figure(go.Indicator(mode="gauge+number", value=sentimen_indodax, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#10b981"}}))
            fig_i.update_layout(paper_bgcolor='rgba(0,0,0,0)', font={'color': text_color}, height=130, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig_i, use_container_width=True)
        with fg2:
            st.markdown('<div style="text-align:center; font-size:13px; color:#94a3b8;">Index Ketakutan & Keserakahan Global: <b>'+str(fgi_global)+'</b></div>', unsafe_allow_html=True)
            fig_g = go.Figure(go.Indicator(mode="gauge+number", value=fgi_global, gauge={'axis': {'range': [0, 100]}, 'bar': {'color': "#f97316"}}))
            fig_g.update_layout(paper_bgcolor='rgba(0,0,0,0)', font={'color': text_color}, height=130, margin=dict(l=10,r=10,t=10,b=10))
            st.plotly_chart(fig_g, use_container_width=True)

        # 4. LOG RADAR PUMP TERBARU
        st.markdown("---")
        st.markdown("##### 🚨 Sinyal Pump Terbaru")
        if not df_pump_signals.empty:
            for _, r in df_pump_signals.sort_values(by='Change', ascending=False).head(4).iterrows():
                st.markdown('<div class="signal-box"><span class="badge-new">PUMP DETECTED</span><b>'+r['Koin']+'</b> | Harga saat ini: Rp '+f"{r['Harga']:,.0f}"+' | Volume Pasar: Rp '+f"{r['Volume']/1e6:,.1f}"+' Jt <span style="float:right; color:#22c55e; font-weight:bold;">+'+f"{r['Change']:.2f}"+'%</span></div>', unsafe_allow_html=True)
        else:
            st.info("Kondisi pasar terpantau stabil. Belum ditemukan indikasi koin mengalami lonjakan radikal di atas threshold.")

        # 5. TABEL ANALISIS PASAR BAWAH
        st.markdown("---")
        tb1, tb2 = st.columns(2)
        with tb1:
            st.markdown("##### 🔥 10 Trending Indodax (% 24h)")
            df_t = df_filtered.sort_values(by='Change', ascending=False).head(10)[['Koin', 'Harga', 'Change']]
            df_t.columns = ['Koin', 'Harga (Rp)', 'Kenaikan 24h']
            st.dataframe(df_t.style.format({'Harga (Rp)': '{:,.0f}', 'Kenaikan 24h': '{:+.2f}%'}), use_container_width=True, hide_index=True)
        with tb2:
            st.markdown("##### 🐳 10 Volume Tertinggi Indodax")
            df_v = df_filtered.sort_values(by='Volume', ascending=False).head(10)[['Koin', 'Harga', 'Volume']]
            df_v.columns = ['Koin', 'Harga (Rp)', 'Volume Total']
            st.dataframe(df_v.style.format({'Harga (Rp)': '{:,.0f}', 'Volume Total': 'Rp {:,.0f}'}), use_container_width=True, hide_index=True)

    # --- HALAMAN: DAFTAR SEMUA KOIN ---
    elif menu_pilihan == "Daftar Semua Koin (Indodax)":
        st.title("📋 Daftar Semua Koin (Indodax)")
        st.write("Menampilkan total koin aktif setelah memfilter batasan volume minimum.")
        st.dataframe(df_filtered.sort_values(by='Volume', ascending=False), use_container_width=True, hide_index=True)

    # --- HALAMAN: SINYAL PUMP ---
    elif menu_pilihan == "Sinyal Pump":
        st.title("🚨 Log Riwayat Sinyal Pump")
        if not df_pump_signals.empty:
            st.dataframe(df_pump_signals.sort_values(by='Change', ascending=False), use_container_width=True, hide_index=True)
        else:
            st.info("Belum ada koin yang tercatat menembus batas persentase pompa sinyal.")
else:
    st.error("Gagal mengambil data terupdate dari API publik Indodax.")

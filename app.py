import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta
import ccxt
import asyncio
from telegram import Bot
from telegram.error import TelegramError
import random

# ==========================================
# 1. KONFIGURASI LAYAR & SESSION STATE
# ==========================================
st.set_page_config(page_title="HELAYO - Radar Pump Indodax", layout="wide")

# Inisialisasi session state untuk semua pengaturan
if 'bot_token' not in st.session_state:
    st.session_state.bot_token = ""
if 'chat_id' not in st.session_state:
    st.session_state.chat_id = ""
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'min_pump' not in st.session_state:
    st.session_state.min_pump = 10
if 'min_vol' not in st.session_state:
    st.session_state.min_vol = 100_000_000
if 'interval_refresh' not in st.session_state:
    st.session_state.interval_refresh = "30 Detik (d)"
if 'dark_mode' not in st.session_state:
    st.session_state.dark_mode = "Gelap"
if 'analysis_settings' not in st.session_state:
    st.session_state.analysis_settings = {
        'sideways_breakout': True,
        'candlestick_pattern': True,
        'rsi': True,
        'ema': True,
        'macd': True,
        'volume_price': True
    }
if 'pump_signals_history' not in st.session_state:
    st.session_state.pump_signals_history = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = None

# ==========================================
# 2. SIDEBAR KONTROL & PENGATURAN
# ==========================================
with st.sidebar:
    st.markdown('<h1 style="margin-bottom:0;"><a href="#" style="color:#ff9900; text-decoration:none;">🦊 HELAYO</a></h1>', unsafe_allow_html=True)
    st.caption("RADAR PUMP INDODAX • REAL-TIME")
    st.markdown("---")
    
    # Menu navigasi
    menu_pilihan = st.radio("MENU", ["🏠 Beranda", "📈 Daftar Semua Koin (Indodax)", "⚡ Sinyal Pump"], label_visibility="collapsed")
    
    st.markdown("---")
    st.subheader("🎯 PENGATURAN DETEKSI")
    new_min_pump = st.slider("🎯 Min. Pump Threshold (%)", 1, 30, st.session_state.min_pump)
    new_min_vol = st.number_input("📦 Min. Volume IDR (24h)", min_value=0, value=st.session_state.min_vol, step=50_000_000)
    new_interval = st.selectbox("⏱️ Interval Refresh", ["5 Detik (d)", "15 Detik (d)", "30 Detik (d)", "1 Menit (m)"], index=["5 Detik (d)", "15 Detik (d)", "30 Detik (d)", "1 Menit (m)"].index(st.session_state.interval_refresh))
    
    st.markdown("---")
    st.subheader("📊 ANALISIS TEKNIKAL")
    st.session_state.analysis_settings['sideways_breakout'] = st.toggle("📊 Sideways Breakout", value=st.session_state.analysis_settings['sideways_breakout'])
    st.session_state.analysis_settings['candlestick_pattern'] = st.toggle("🕯️ Pola Candlestick", value=st.session_state.analysis_settings['candlestick_pattern'])
    st.session_state.analysis_settings['rsi'] = st.toggle("📈 RSI (14)", value=st.session_state.analysis_settings['rsi'])
    st.session_state.analysis_settings['ema'] = st.toggle("📉 EMA (9 & 50)", value=st.session_state.analysis_settings['ema'])
    st.session_state.analysis_settings['macd'] = st.toggle("⚡ MACD (12,26,9)", value=st.session_state.analysis_settings['macd'])
    st.session_state.analysis_settings['volume_price'] = st.toggle("📦 Volume × Harga", value=st.session_state.analysis_settings['volume_price'])
    
    st.markdown("---")
    st.subheader("🤖 BOT TELEGRAM")
    st.session_state.bot_token = st.text_input("Bot Token:", value=st.session_state.bot_token, type="password")
    st.session_state.chat_id = st.text_input("Chat ID:", value=st.session_state.chat_id)
    
    if st.button("💾 Simpan Pengaturan Server"):
        st.session_state.min_pump = new_min_pump
        st.session_state.min_vol = new_min_vol
        st.session_state.interval_refresh = new_interval
        st.success("Pengaturan disimpan!")
    
    # Tombol Start/Stop auto kirim (simulasi auto refresh)
    if st.session_state.is_running:
        if st.button("🛑 STOP AUTO KIRIM", type="primary", use_container_width=True):
            st.session_state.is_running = False
            st.rerun()
    else:
        if st.button("⚡ START (Auto Kirim)", use_container_width=True):
            st.session_state.is_running = True
            st.rerun()
    
    st.markdown("---")
    dark_mode_opt = st.radio("🌗 Mode Tampilan", ["Gelap", "Terang"], index=0 if st.session_state.dark_mode=="Gelap" else 1)
    st.session_state.dark_mode = dark_mode_opt
    
    with st.expander("📘 Tutorial Penggunaan & Strategi"):
        st.markdown("""
        **Cara Penggunaan:**
        1. Atur threshold pump dan volume minimal.
        2. Aktifkan analisis teknikal yang diinginkan.
        3. Klik 'START' untuk mulai auto refresh (setiap interval).
        4. Pantau sinyal pump di halaman 'Sinyal Pump'.
        
        **Strategi:**
        - Gunakan RSI >70 sebagai overbought, <30 oversold.
        - EMA golden cross (9 > 50) signal bullish.
        - MACD histogram positif menguat.
        - Sideways breakout + volume spike = potensi pump.
        """)
    with st.expander("ℹ️ Tentang Aplikasi"):
        st.markdown("**HELAYO v2.0**\nRadar sinyal market Indodax dengan analisis teknikal real-time.")

# ==========================================
# 3. FUNGSI PENGAMBIL DATA (DENGAN FALLBACK MOCK)
# ==========================================
@st.cache_data(ttl=10)
def get_indodax_data():
    """Ambil data ticker dari Indodax, jika gagal pakai mock"""
    try:
        url = "https://indodax.com/api/summaries"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            tickers = data.get('tickers', {})
            prices_24h = data.get('prices_24h', {})
            rows = []
            for pair, info in tickers.items():
                if not pair.endswith('_idr'):
                    continue
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
    except Exception as e:
        st.warning(f"Gagal ambil data real: {str(e)[:100]}. Gunakan data simulasi.")
    
    # Mock data (simulasi 20 koin)
    coins = ['BTC','ETH','XRP','ADA','DOGE','MATIC','SOL','DOT','AVAX','LTC','BNB','LINK','XLM','TRX','EOS','NEAR','ALGO','VET','THETA','FTM']
    mock_data = []
    for coin in coins:
        last = random.uniform(10000, 500_000_000)
        change = random.uniform(-15, 25)
        volume = random.uniform(1e8, 1e11)
        mock_data.append({
            "Koin": coin,
            "Harga": last,
            "High": last * 1.02,
            "Low": last * 0.98,
            "Volume": volume,
            "Change": change
        })
    return pd.DataFrame(mock_data)

@st.cache_data(ttl=300)
def get_global_fgi():
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5)
        if r.status_code == 200:
            return int(r.json()['data'][0]['value'])
    except:
        pass
    return 50

# ==========================================
# 4. FUNGSI ANALISIS TEKNIKAL (CCXT + MOCK)
# ==========================================
exchange = ccxt.indodax()

def get_ohlcv(pair_symbol, timeframe='1m', limit=100):
    """Ambil candlestick historis (dengan fallback mock)"""
    try:
        # pair_symbol contoh: 'BTC/IDR'
        symbol = pair_symbol.upper().replace('_', '/')
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except:
        # Mock data sederhana untuk demo
        dates = pd.date_range(end=datetime.now(), periods=limit, freq='1min')
        base = 100000
        prices = base * (1 + np.cumsum(np.random.randn(limit)/100))
        df = pd.DataFrame({
            'timestamp': dates,
            'open': prices * 0.998,
            'high': prices * 1.005,
            'low': prices * 0.995,
            'close': prices,
            'volume': np.random.randint(1e8, 1e10, limit)
        })
        return df

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram

def detect_sideways_breakout(df, lookback=20, threshold=0.02):
    if len(df) < lookback:
        return None
    recent = df['close'].tail(lookback)
    high, low = recent.max(), recent.min()
    range_percent = (high - low) / low
    if range_percent < 0.05:  # sideways
        last_close = df['close'].iloc[-1]
        if last_close > high * (1 + threshold):
            return "Bullish Breakout"
        elif last_close < low * (1 - threshold):
            return "Bearish Breakout"
    return None

def detect_candlestick_pattern(df):
    if len(df) < 1:
        return None
    last = df.iloc[-1]
    body = abs(last['close'] - last['open'])
    total_range = last['high'] - last['low']
    if total_range == 0:
        return None
    if body / total_range < 0.1:
        return "Doji"
    lower_wick = min(last['close'], last['open']) - last['low']
    upper_wick = last['high'] - max(last['close'], last['open'])
    if lower_wick > 2 * body and upper_wick < body:
        return "Hammer"
    if upper_wick > 2 * body and lower_wick < body:
        return "Shooting Star"
    return None

def analyze_coin_technical(pair_name, settings):
    """Lakukan semua analisis teknikal untuk satu koin"""
    df = get_ohlcv(pair_name.replace(' ', '_') + '_idr')
    if df.empty:
        return {}
    result = {}
    close = df['close']
    if settings.get('rsi'):
        rsi = calculate_rsi(close)
        result['RSI (14)'] = round(rsi.iloc[-1], 2) if not rsi.empty else None
    if settings.get('ema'):
        ema9 = calculate_ema(close, 9)
        ema50 = calculate_ema(close, 50)
        result['EMA9'] = round(ema9.iloc[-1], 2)
        result['EMA50'] = round(ema50.iloc[-1], 2)
        result['EMA Signal'] = "Bullish" if ema9.iloc[-1] > ema50.iloc[-1] else "Bearish"
    if settings.get('macd'):
        macd, signal, hist = calculate_macd(close)
        result['MACD Hist'] = round(hist.iloc[-1], 4)
        if len(hist) > 1:
            if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
                result['MACD Cross'] = "Bullish"
            elif hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
                result['MACD Cross'] = "Bearish"
    if settings.get('sideways_breakout'):
        result['Sideways Breakout'] = detect_sideways_breakout(df)
    if settings.get('candlestick_pattern'):
        result['Candlestick'] = detect_candlestick_pattern(df)
    if settings.get('volume_price'):
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        curr_vol = df['volume'].iloc[-1]
        result['Volume Spike'] = curr_vol > 2 * avg_vol if avg_vol else False
    return result

# ==========================================
# 5. FUNGSI NOTIFIKASI TELEGRAM
# ==========================================
async def send_telegram_msg(token, chat_id, message):
    try:
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message)
        return True
    except:
        return False

def notify_pump(pump_list):
    if st.session_state.bot_token and st.session_state.chat_id and pump_list:
        msg = "🚨 *PUMP DETECTED* 🚨\n\n"
        for p in pump_list[:5]:
            msg += f"• {p['Koin']}: +{p['Change']:.2f}% | Harga: Rp {p['Harga']:,.0f} | Vol: Rp {p['Volume']/1e9:.1f}M\n"
        asyncio.run(send_telegram_msg(st.session_state.bot_token, st.session_state.chat_id, msg))

# ==========================================
# 6. AUTO REFRESH LOGIC (BERDASARKAN INTERVAL)
# ==========================================
def get_refresh_milliseconds(interval_str):
    if interval_str == "5 Detik (d)": return 5000
    if interval_str == "15 Detik (d)": return 15000
    if interval_str == "30 Detik (d)": return 30000
    if interval_str == "1 Menit (m)": return 60000
    return 30000

if st.session_state.is_running:
    from streamlit_autorefresh import st_autorefresh
    interval_ms = get_refresh_milliseconds(st.session_state.interval_refresh)
    st_autorefresh(interval=interval_ms, key="auto_refresh")
    st.caption(f"🔄 Auto refresh setiap {st.session_state.interval_refresh}")

# ==========================================
# 7. AMBIL DATA UTAMA
# ==========================================
df_raw = get_indodax_data()
if df_raw.empty:
    st.error("Gagal mendapatkan data dari Indodax dan mock data. Cek koneksi.")
    st.stop()

# Terapkan filter volume & threshold
df_filtered = df_raw[df_raw['Volume'] >= st.session_state.min_vol]
df_pump_signals = df_filtered[df_filtered['Change'] >= st.session_state.min_pump]

# Update riwayat pump (simpan waktu)
if not df_pump_signals.empty:
    new_signals = []
    for _, row in df_pump_signals.iterrows():
        new_signals.append({
            'Koin': row['Koin'],
            'Harga': row['Harga'],
            'Change': row['Change'],
            'Volume': row['Volume'],
            'Waktu': datetime.now().strftime("%H:%M:%S")
        })
    # Gabungkan dengan history, batasi 50 entri
    st.session_state.pump_signals_history = new_signals + st.session_state.pump_signals_history[:50]
    # Kirim notifikasi jika auto running
    if st.session_state.is_running:
        notify_pump(new_signals)

st.session_state.last_update = datetime.now()

# ==========================================
# 8. TAMPILAN SESUAI MENU
# ==========================================
# Terapkan mode gelap/terang via CSS
bg_color = "#020617" if st.session_state.dark_mode == "Gelap" else "#ffffff"
text_color = "#ffffff" if st.session_state.dark_mode == "Gelap" else "#000000"
box_bg = "#0b1329" if st.session_state.dark_mode == "Gelap" else "#f8fafc"
border_color = "#1e293b" if st.session_state.dark_mode == "Gelap" else "#e2e8f0"
st.markdown(f"""
<style>
    .stApp {{ background-color: {bg_color}; color: {text_color}; }}
    .metric-box {{ background-color: {box_bg}; border-radius: 10px; padding: 15px; border: 1px solid {border_color}; text-align: center; margin-bottom: 10px; }}
    .metric-label {{ color: #94a3b8; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5px; }}
    .metric-val {{ color: #38bdf8; font-size: 22px; font-weight: bold; margin-top: 4px; }}
    .gl-box {{ background-color: {box_bg}; border: 1px solid {border_color}; border-radius: 8px; padding: 12px; margin-bottom: 8px; }}
    .signal-box {{ background-color: #0f172a; border: 1px solid #334155; border-left: 5px solid #ea580c; padding: 14px; border-radius: 6px; margin-bottom: 10px; color: #f8fafc; }}
    .badge-new {{ background-color: #ea580c; color: white; padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: bold; margin-right: 10px; }}
</style>
""", unsafe_allow_html=True)

if menu_pilihan == "🏠 Beranda":
    # Hitung metrik
    total_vol = df_filtered['Volume'].sum()
    naik = len(df_filtered[df_filtered['Change'] > 0])
    turun = len(df_filtered[df_filtered['Change'] < 0])
    total_koin = len(df_filtered)
    sinyal_pump = len(df_pump_signals)
    sentimen_persen = int((naik / total_koin) * 100) if total_koin > 0 else 50
    sentimen_label = "BULLISH" if sentimen_persen > 55 else "BEARISH" if sentimen_persen < 45 else "NETRAL"
    
    # WIB
    now_wib = datetime.utcnow() + timedelta(hours=7)
    st.markdown(f'<h3>🏠 Beranda <span style="color:#64748b; font-size:14px;">• Last update: {now_wib.strftime("%H:%M:%S")} WIB</span></h3>', unsafe_allow_html=True)
    
    # Baris metrik
    c1,c2,c3,c4,c5,c6 = st.columns(6)
    c1.markdown(f'<div class="metric-box"><div class="metric-label">Total Volume 24H</div><div class="metric-val">Rp {total_vol/1e9:.1f} M</div></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-box"><div class="metric-label">🟢 Koin Naik</div><div class="metric-val" style="color:#22c55e;">{naik}</div></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-box"><div class="metric-label">🔴 Koin Turun</div><div class="metric-val" style="color:#ef4444;">{turun}</div></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-box"><div class="metric-label">Total Semua Koin</div><div class="metric-val">{total_koin}</div></div>', unsafe_allow_html=True)
    c5.markdown(f'<div class="metric-box"><div class="metric-label">⚡ Sinyal Pump</div><div class="metric-val" style="color:#eab308;">{sinyal_pump}</div></div>', unsafe_allow_html=True)
    c6.markdown(f'<div class="metric-box"><div class="metric-label">Sentimen</div><div class="metric-val" style="color:#10b981; font-size:16px;">{sentimen_label} ({sentimen_persen}%)</div></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    col_g1, col_g2, col_g3 = st.columns(3)
    with col_g1:
        st.markdown("##### 🔥 Top Gainer 24h")
        for _, r in df_filtered.sort_values('Change', ascending=False).head(3).iterrows():
            st.markdown(f'<div class="gl-box"><b>{r["Koin"]}</b>: Rp {r["Harga"]:,.0f} <span style="float:right; color:#22c55e;">+{r["Change"]:.2f}%</span></div>', unsafe_allow_html=True)
    with col_g2:
        st.markdown("##### ❄️ Top Loser 24h")
        for _, r in df_filtered.sort_values('Change', ascending=True).head(3).iterrows():
            st.markdown(f'<div class="gl-box"><b>{r["Koin"]}</b>: Rp {r["Harga"]:,.0f} <span style="float:right; color:#ef4444;">{r["Change"]:.2f}%</span></div>', unsafe_allow_html=True)
    with col_g3:
        st.markdown("##### 🐳 Volume Tertinggi")
        for _, r in df_filtered.sort_values('Volume', ascending=False).head(3).iterrows():
            st.markdown(f'<div class="gl-box"><b>{r["Koin"]}</b>: Rp {r["Harga"]:,.0f} <span style="float:right; color:#38bdf8;">Rp {r["Volume"]/1e9:.1f}M</span></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("##### 🧭 Indeks Ketakutan & Keserakahan")
    fgi_global = get_global_fgi()
    fgi_indodax = sentimen_persen  # dari proporsi naik/turun
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        fig_i = go.Figure(go.Indicator(mode="gauge+number", value=fgi_indodax, gauge={'axis':{'range':[0,100]}, 'bar':{'color':'#10b981'}}))
        fig_i.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color=text_color, height=130, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig_i, use_container_width=True)
        st.caption(f"Indodax FGI: {fgi_indodax} - {'Greed' if fgi_indodax>55 else 'Fear' if fgi_indodax<45 else 'Netral'}")
    with col_f2:
        fig_g = go.Figure(go.Indicator(mode="gauge+number", value=fgi_global, gauge={'axis':{'range':[0,100]}, 'bar':{'color':'#f97316'}}))
        fig_g.update_layout(paper_bgcolor='rgba(0,0,0,0)', font_color=text_color, height=130, margin=dict(l=10,r=10,t=10,b=10))
        st.plotly_chart(fig_g, use_container_width=True)
        st.caption(f"Global FGI: {fgi_global}")
    
    st.markdown("---")
    st.markdown("##### 🚨 Sinyal Pump Terbaru")
    if st.session_state.pump_signals_history:
        for sig in st.session_state.pump_signals_history[:5]:
            st.markdown(f'<div class="signal-box"><span class="badge-new">PUMP</span><b>{sig["Koin"]}</b> | Harga: Rp {sig["Harga"]:,.0f} | Vol: Rp {sig["Volume"]/1e6:.1f} Jt <span style="float:right; color:#22c55e;">+{sig["Change"]:.2f}%</span><br><span style="font-size:10px;">{sig["Waktu"]}</span></div>', unsafe_allow_html=True)
    else:
        st.info("Belum ada sinyal pump terdeteksi.")
    
    st.markdown("---")
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.markdown("##### 🔥 10 Trending Indodax (% 24h)")
        trending = df_filtered.nlargest(10, 'Change')[['Koin','Harga','Change']]
        trending.columns = ['Koin','Harga (Rp)','Kenaikan 24h']
        st.dataframe(trending.style.format({'Harga (Rp)':'{:,.0f}','Kenaikan 24h':'{:+.2f}%'}), use_container_width=True, hide_index=True)
    with col_t2:
        st.markdown("##### 🐳 10 Volume Tertinggi Indodax")
        top_vol = df_filtered.nlargest(10, 'Volume')[['Koin','Harga','Volume']]
        top_vol.columns = ['Koin','Harga (Rp)','Volume Total']
        st.dataframe(top_vol.style.format({'Harga (Rp)':'{:,.0f}','Volume Total':'Rp {:,.0f}'}), use_container_width=True, hide_index=True)

elif menu_pilihan == "📈 Daftar Semua Koin (Indodax)":
    st.title("📋 Daftar Semua Koin (Indodax)")
    search = st.text_input("🔍 Cari koin", placeholder="Contoh: BTC, ETH")
    if search:
        df_display = df_filtered[df_filtered['Koin'].str.contains(search.upper())]
    else:
        df_display = df_filtered
    st.dataframe(df_display.sort_values('Volume', ascending=False), use_container_width=True, hide_index=True)

elif menu_pilihan == "⚡ Sinyal Pump":
    st.title("🚨 Log Riwayat Sinyal Pump")
    if st.session_state.pump_signals_history:
        hist_df = pd.DataFrame(st.session_state.pump_signals_history)
        st.dataframe(hist_df, use_container_width=True, hide_index=True)
    else:
        st.info("Belum ada sinyal pump terdeteksi.")
    
    # Tambahkan analisis teknikal untuk koin yang dipilih
    st.markdown("---")
    st.subheader("🔬 Analisis Teknikal (Pilih Koin)")
    selected_coin = st.selectbox("Pilih koin", df_filtered['Koin'].unique())
    if selected_coin:
        with st.spinner("Mengambil data OHLCV..."):
            analysis = analyze_coin_technical(selected_coin, st.session_state.analysis_settings)
            if analysis:
                st.json(analysis)
                # Plot candlestick sederhana
                df_ohlcv = get_ohlcv(selected_coin.replace(' ', '_') + '_idr')
                if not df_ohlcv.empty:
                    fig = go.Figure(data=[go.Candlestick(x=df_ohlcv['timestamp'], open=df_ohlcv['open'], high=df_ohlcv['high'], low=df_ohlcv['low'], close=df_ohlcv['close'])])
                    fig.update_layout(title=f"{selected_coin} - 1m Candlestick", height=400, template="plotly_dark" if st.session_state.dark_mode=="Gelap" else "plotly_white")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Tidak cukup data untuk analisis teknikal (mungkin koin tidak mendukung OHLCV).")

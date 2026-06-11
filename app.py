import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import json
import os
from datetime import datetime
import plotly.graph_objects as go
import ccxt
from streamlit_autorefresh import st_autorefresh
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# ==================== KONFIGURASI HALAMAN ====================
st.set_page_config(page_title="HELAYO - Radar Indodax", layout="wide", initial_sidebar_state="expanded")

# ==================== INISIALISASI SESSION STATE ====================
if 'settings' not in st.session_state:
    st.session_state.settings = {
        'min_pump_threshold': 5.0,      # persen
        'min_volume_idr': 100000000,    # 100 juta IDR
        'refresh_interval': 30,         # detik
        'telegram_token': '',
        'telegram_chat_id': '',
        'auto_start': False,
        'dark_mode': False,
        'analysis_enabled': {
            'sideways_breakout': True,
            'candlestick_pattern': True,
            'rsi': True,
            'ema': True,
            'macd': True,
            'volume_price': True
        }
    }

if 'last_update' not in st.session_state:
    st.session_state.last_update = None

if 'tickers_data' not in st.session_state:
    st.session_state.tickers_data = {}

if 'pump_signals' not in st.session_state:
    st.session_state.pump_signals = []

# ==================== FUNGSI API INDODAX ====================
@st.cache_data(ttl=60)
def get_indodax_tickers():
    """Ambil semua ticker dari Indodax"""
    try:
        response = requests.get('https://indodax.com/api/tickers', timeout=10)
        data = response.json()
        if data.get('success') == 1:
            return data['tickers']
        else:
            st.error("Gagal mengambil data dari Indodax")
            return {}
    except Exception as e:
        st.error(f"Error Indodax API: {e}")
        return {}

def process_ticker_data(tickers):
    """Proses raw ticker menjadi DataFrame dengan kolom yang diperlukan"""
    rows = []
    for pair, info in tickers.items():
        if pair == 'btc_idr':  # contoh, semua pair akan diproses
            pass
        # Konversi volume ke IDR (volume * harga terakhir)
        last = float(info.get('last', 0))
        volume = float(info.get('vol_idr', 0))  # Indodax menyediakan vol_idr untuk 24h
        if volume == 0:
            volume = float(info.get('volume', 0)) * last
        change = float(info.get('change', 0))
        rows.append({
            'pair': pair.upper(),
            'last_price': last,
            'volume_idr': volume,
            'change_percent': change,
            'high': float(info.get('high', 0)),
            'low': float(info.get('low', 0)),
            'buy': float(info.get('buy', 0)),
            'sell': float(info.get('sell', 0))
        })
    df = pd.DataFrame(rows)
    return df

def get_top_gainer_losser(df, top_n=10):
    """Top gainer dan loser berdasarkan persen change"""
    df_valid = df[df['change_percent'].notna()]
    gainers = df_valid.nlargest(top_n, 'change_percent')[['pair', 'change_percent', 'last_price', 'volume_idr']]
    losers = df_valid.nsmallest(top_n, 'change_percent')[['pair', 'change_percent', 'last_price', 'volume_idr']]
    return gainers, losers

def get_highest_volume(df, top_n=10):
    return df.nlargest(top_n, 'volume_idr')[['pair', 'volume_idr', 'last_price', 'change_percent']]

def get_total_volume_all(df):
    return df['volume_idr'].sum()

def get_coin_count_naik_turun(df):
    naik = len(df[df['change_percent'] > 0])
    turun = len(df[df['change_percent'] < 0])
    return naik, turun

# ==================== ANALISIS TEKNIKAL (menggunakan ccxt) ====================
exchange = ccxt.indodax()

def get_ohlcv(pair, timeframe='1m', limit=100):
    """Ambil data candlestick dari Indodax via ccxt"""
    try:
        # ccxt memerlukan pair format 'BTC/IDR'
        symbol = pair.upper().replace('_', '/')
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        st.warning(f"Gagal ambil OHLCV untuk {pair}: {e}")
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
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
    """Deteksi breakout dari fase sideways"""
    if len(df) < lookback:
        return False
    recent = df['close'].tail(lookback)
    high = recent.max()
    low = recent.min()
    range_percent = (high - low) / low
    if range_percent < 0.05:  # sideway jika range <5%
        last_close = df['close'].iloc[-1]
        if last_close > high * (1 + threshold):
            return "Bullish Breakout"
        elif last_close < low * (1 - threshold):
            return "Bearish Breakout"
    return None

def detect_candlestick_pattern(df):
    """Sederhana: detect doji, hammer, shooting star"""
    if len(df) < 2:
        return None
    last = df.iloc[-1]
    body = abs(last['close'] - last['open'])
    upper_wick = last['high'] - max(last['close'], last['open'])
    lower_wick = min(last['close'], last['open']) - last['low']
    total_range = last['high'] - last['low']
    if total_range == 0:
        return None
    if body / total_range < 0.1:
        return "Doji"
    if lower_wick > 2 * body and upper_wick < body:
        return "Hammer"
    if upper_wick > 2 * body and lower_wick < body:
        return "Shooting Star"
    return None

def analyze_coin(pair, settings):
    """Lakukan semua analisis teknikal untuk satu koin"""
    df = get_ohlcv(pair, limit=100)
    if df.empty:
        return {}
    result = {}
    close = df['close']
    if settings.get('rsi', True):
        rsi = calculate_rsi(close)
        result['RSI'] = round(rsi.iloc[-1], 2) if not rsi.empty else None
    if settings.get('ema', True):
        ema9 = calculate_ema(close, 9)
        ema50 = calculate_ema(close, 50)
        result['EMA9'] = round(ema9.iloc[-1], 2) if not ema9.empty else None
        result['EMA50'] = round(ema50.iloc[-1], 2) if not ema50.empty else None
        result['EMA_Signal'] = "Bullish" if ema9.iloc[-1] > ema50.iloc[-1] else "Bearish"
    if settings.get('macd', True):
        macd, signal, hist = calculate_macd(close)
        result['MACD'] = round(macd.iloc[-1], 4) if not macd.empty else None
        result['MACD_Signal'] = round(signal.iloc[-1], 4) if not signal.empty else None
        result['MACD_Hist'] = round(hist.iloc[-1], 4) if not hist.empty else None
        if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
            result['MACD_Cross'] = "Bullish"
        elif hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
            result['MACD_Cross'] = "Bearish"
    if settings.get('sideways_breakout', True):
        result['Sideways'] = detect_sideways_breakout(df)
    if settings.get('candlestick_pattern', True):
        result['Candlestick'] = detect_candlestick_pattern(df)
    if settings.get('volume_price', True):
        avg_volume = df['volume'].rolling(20).mean().iloc[-1]
        curr_volume = df['volume'].iloc[-1]
        result['Volume_Spike'] = curr_volume > 2 * avg_volume if avg_volume else False
    return result

# ==================== DETEKSI PUMP ====================
def detect_pumps(tickers_df, threshold_percent, min_volume):
    """Deteksi koin yang mengalami pump (kenaikan > threshold dalam 1 menit) - membutuhkan data real-time"""
    # Karena tidak ada streaming real-time, kita gunakan perubahan % dari ticker sebagai simulasi
    # Untuk demo, kita anggap pump jika change_percent > threshold
    pumps = []
    for _, row in tickers_df.iterrows():
        if row['change_percent'] >= threshold_percent and row['volume_idr'] >= min_volume:
            pumps.append({
                'pair': row['pair'],
                'gain_percent': row['change_percent'],
                'price': row['last_price'],
                'volume_idr': row['volume_idr'],
                'timestamp': datetime.now()
            })
    return pumps

# ==================== FEAR & GREED ====================
def get_global_fear_greed():
    try:
        r = requests.get('https://api.alternative.me/fng/?limit=1')
        data = r.json()
        value = int(data['data'][0]['value'])
        classification = data['data'][0]['value_classification']
        return value, classification
    except:
        return 50, "Netral"

def get_indodax_fear_greed(tickers_df):
    """Hitung fear greed berdasarkan perubahan harga dan volume"""
    if tickers_df.empty:
        return 50, "Netral"
    avg_change = tickers_df['change_percent'].mean()
    # mapping -10% s/d +10% ke 0-100
    fg = 50 + (avg_change * 2.5)
    fg = max(0, min(100, fg))
    if fg < 25:
        cls = "Extreme Fear"
    elif fg < 45:
        cls = "Fear"
    elif fg < 55:
        cls = "Netral"
    elif fg < 75:
        cls = "Greed"
    else:
        cls = "Extreme Greed"
    return int(fg), cls

# ==================== TELEGRAM BOT ====================
async def send_telegram_message(token, chat_id, message):
    try:
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=message)
        return True
    except TelegramError as e:
        st.error(f"Telegram error: {e}")
        return False

def notify_pump(pump_signals, settings):
    if settings['telegram_token'] and settings['telegram_chat_id']:
        if pump_signals:
            msg = "🚨 *PUMP DETECTED* 🚨\n\n"
            for p in pump_signals[:5]:
                msg += f"• {p['pair']}: +{p['gain_percent']:.2f}% | Vol: {p['volume_idr']:,.0f} IDR\n"
            asyncio.run(send_telegram_message(settings['telegram_token'], settings['telegram_chat_id'], msg))

# ==================== TAMPILAN UTAMA ====================
def main():
    # Sidebar Menu Utama
    with st.sidebar:
        st.image("https://indodax.com/logo.svg", width=150)  # placeholder
        st.title("HELAYO")
        menu = st.radio("Navigasi", ["🏠 Beranda", "📈 Daftar Semua Koin", "⚡ Sinyal Pump"])

        st.markdown("---")
        st.subheader("⚙️ Pengaturan Deteksi")
        new_threshold = st.slider("🎯 Min. Pump Threshold (%)", 0.0, 50.0, st.session_state.settings['min_pump_threshold'], 0.5)
        new_min_vol = st.number_input("📦 Min. Volume IDR", min_value=0, value=int(st.session_state.settings['min_volume_idr']), step=50000000, format="%d")
        new_interval = st.number_input("⏱️ Interval Refresh (detik)", min_value=5, max_value=300, value=st.session_state.settings['refresh_interval'], step=5)

        with st.expander("🔬 Analisis Teknikal"):
            st.session_state.settings['analysis_enabled']['sideways_breakout'] = st.checkbox("Sideways Breakout", st.session_state.settings['analysis_enabled']['sideways_breakout'])
            st.session_state.settings['analysis_enabled']['candlestick_pattern'] = st.checkbox("Pola Candlestick", st.session_state.settings['analysis_enabled']['candlestick_pattern'])
            st.session_state.settings['analysis_enabled']['rsi'] = st.checkbox("RSI (14)", st.session_state.settings['analysis_enabled']['rsi'])
            st.session_state.settings['analysis_enabled']['ema'] = st.checkbox("EMA (9 & 50)", st.session_state.settings['analysis_enabled']['ema'])
            st.session_state.settings['analysis_enabled']['macd'] = st.checkbox("MACD (12,26,9)", st.session_state.settings['analysis_enabled']['macd'])
            st.session_state.settings['analysis_enabled']['volume_price'] = st.checkbox("Volume × Harga", st.session_state.settings['analysis_enabled']['volume_price'])

        with st.expander("🤖 Bot Telegram"):
            token = st.text_input("Bot Token", value=st.session_state.settings['telegram_token'], type="password")
            chat_id = st.text_input("Chat ID", value=st.session_state.settings['telegram_chat_id'])
            if st.button("Tes Kirim Pesan"):
                asyncio.run(send_telegram_message(token, chat_id, "✅ Helayo bot connected!"))

        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Simpan Pengaturan Server"):
                st.session_state.settings['min_pump_threshold'] = new_threshold
                st.session_state.settings['min_volume_idr'] = new_min_vol
                st.session_state.settings['refresh_interval'] = new_interval
                st.session_state.settings['telegram_token'] = token
                st.session_state.settings['telegram_chat_id'] = chat_id
                st.success("Pengaturan disimpan!")
        with col2:
            if st.button("▶️ Auto Start"):
                st.session_state.settings['auto_start'] = True
                st.rerun()

        st.markdown("---")
        dark_mode = st.toggle("🌙 Mode Gelap", value=st.session_state.settings['dark_mode'])
        st.session_state.settings['dark_mode'] = dark_mode

        with st.expander("📘 Tutorial & Strategi"):
            st.markdown("""
            **Cara Penggunaan:**
            1. Atur threshold pump dan volume minimal.
            2. Aktifkan analisis teknikal yang diinginkan.
            3. Klik 'Auto Start' untuk refresh otomatis.
            4. Pantau sinyal pump di halaman Sinyal Pump.
            
            **Strategi:**
            - Gunakan RSI >70 sebagai overbought, <30 oversold.
            - EMA golden cross (9 di atas 50) signal bullish.
            - MACD histogram positif menguat.
            - Sideways breakout + volume spike = potensi pump.
            """)

        with st.expander("ℹ️ Tentang Aplikasi"):
            st.markdown("**HELAYO v1.0**\nRadar sinyal market Indodax. Dapatkan notifikasi pump real-time via Telegram.\n\nDibuat untuk trader kripto Indonesia.")

    # ==================== AUTO REFRESH ====================
    if st.session_state.settings['auto_start']:
        count = st_autorefresh(interval=st.session_state.settings['refresh_interval'] * 1000, key="auto_refresh")
        st.caption(f"🔄 Auto refresh setiap {st.session_state.settings['refresh_interval']} detik")

    # Ambil data ticker
    tickers_raw = get_indodax_tickers()
    if not tickers_raw:
        st.error("Tidak dapat mengambil data dari Indodax. Cek koneksi atau API.")
        return

    df_tickers = process_ticker_data(tickers_raw)
    st.session_state.tickers_data = df_tickers

    # Update pump signals
    pumps = detect_pumps(df_tickers, st.session_state.settings['min_pump_threshold'], st.session_state.settings['min_volume_idr'])
    if pumps:
        st.session_state.pump_signals = pumps + st.session_state.pump_signals[:20]  # keep last 20

    # Kirim notifikasi jika ada pump baru (sederhana)
    if st.session_state.pump_signals and st.session_state.settings['auto_start']:
        notify_pump(st.session_state.pump_signals[:3], st.session_state.settings)

    st.session_state.last_update = datetime.now()

    # ==================== HALAMAN BERANDA ====================
    if menu == "🏠 Beranda":
        st.title("📊 Radar Market Indodax")
        st.caption(f"Terakhir update: {st.session_state.last_update.strftime('%H:%M:%S')}")

        # Baris metrik
        total_vol = get_total_volume_all(df_tickers)
        naik, turun = get_coin_count_naik_turun(df_tickers)
        total_koin = len(df_tickers)
        sentimen = "🟢 Bullish" if naik > turun else "🔴 Bearish"
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Volume 24h (IDR)", f"{total_vol:,.0f}")
        col2.metric("Koin Naik", naik, delta=f"{naik - turun}")
        col3.metric("Koin Turun", turun)
        col4.metric("Total Koin", total_koin)
        col5.metric("Sentimen", sentimen)

        st.markdown("---")
        # Top Gainer/Loser/Volume
        gainers, losers = get_top_gainer_losser(df_tickers, 10)
        high_vol = get_highest_volume(df_tickers, 10)

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.subheader("🚀 Top Gainer 24h")
            st.dataframe(gainers.style.format({'change_percent': '{:.2f}%', 'volume_idr': '{:,.0f}'}))
        with col_b:
            st.subheader("📉 Top Losser 24h")
            st.dataframe(losers.style.format({'change_percent': '{:.2f}%', 'volume_idr': '{:,.0f}'}))
        with col_c:
            st.subheader("🔥 Volume Tertinggi")
            st.dataframe(high_vol.style.format({'volume_idr': '{:,.0f}', 'change_percent': '{:.2f}%'}))

        st.markdown("---")
        # Fear & Greed
        fg_global, fg_class_global = get_global_fear_greed()
        fg_indodax, fg_class_indodax = get_indodax_fear_greed(df_tickers)
        col_d, col_e = st.columns(2)
        with col_d:
            st.metric("🌍 Fear & Greed Global", f"{fg_global} - {fg_class_global}")
            st.progress(fg_global/100)
        with col_e:
            st.metric("🇮🇩 Fear & Greed Indodax", f"{fg_indodax} - {fg_class_indodax}")
            st.progress(fg_indodax/100)

        st.markdown("---")
        st.subheader("🔔 Sinyal Pump Terbaru")
        if st.session_state.pump_signals:
            pump_df = pd.DataFrame(st.session_state.pump_signals[:10])
            st.dataframe(pump_df[['pair', 'gain_percent', 'price', 'volume_idr', 'timestamp']].style.format({'gain_percent': '{:.2f}%', 'volume_idr': '{:,.0f}'}))
        else:
            st.info("Belum ada sinyal pump. Tunggu pergerakan harga.")

        st.markdown("---")
        st.subheader("📈 10 Trending Indodax (% 24h)")
        trending = df_tickers.nlargest(10, 'change_percent')[['pair', 'change_percent', 'last_price']]
        st.dataframe(trending.style.format({'change_percent': '{:.2f}%'}))

        st.subheader("💎 10 Volume Tertinggi Indodax")
        st.dataframe(high_vol.style.format({'volume_idr': '{:,.0f}'}))

    # ==================== HALAMAN DAFTAR SEMUA KOIN ====================
    elif menu == "📈 Daftar Semua Koin":
        st.title("📋 Daftar Semua Koin (Indodax)")
        search = st.text_input("Cari koin (misal: btc, eth)")
        if search:
            df_filtered = df_tickers[df_tickers['pair'].str.contains(search.upper())]
        else:
            df_filtered = df_tickers
        st.dataframe(df_filtered.style.format({
            'last_price': '{:,.2f}',
            'volume_idr': '{:,.0f}',
            'change_percent': '{:.2f}%',
            'high': '{:,.2f}',
            'low': '{:,.2f}'
        }))

    # ==================== HALAMAN SINYAL PUMP ====================
    elif menu == "⚡ Sinyal Pump":
        st.title("🚨 Daftar Sinyal Pump")
        if st.session_state.pump_signals:
            pump_df = pd.DataFrame(st.session_state.pump_signals)
            st.dataframe(pump_df[['pair', 'gain_percent', 'price', 'volume_idr', 'timestamp']].style.format({'gain_percent': '{:.2f}%', 'volume_idr': '{:,.0f}'}))
        else:
            st.info("Belum ada sinyal pump terdeteksi.")

        if st.button("Refresh Manual"):
            st.rerun()

        # Tampilkan detail analisis teknikal untuk koin yang dipilih
        st.subheader("🔬 Analisis Teknikal (Pilih Koin)")
        selected_pair = st.selectbox("Pilih koin untuk analisis mendalam", df_tickers['pair'].unique())
        if selected_pair:
            with st.spinner("Mengambil data OHLCV dan menghitung indikator..."):
                analysis = analyze_coin(selected_pair, st.session_state.settings['analysis_enabled'])
                if analysis:
                    col1, col2 = st.columns(2)
                    col1.write(analysis)
                    # Plot harga sederhana
                    df_ohlcv = get_ohlcv(selected_pair)
                    if not df_ohlcv.empty:
                        fig = go.Figure(data=[go.Candlestick(x=df_ohlcv['timestamp'],
                                                            open=df_ohlcv['open'],
                                                            high=df_ohlcv['high'],
                                                            low=df_ohlcv['low'],
                                                            close=df_ohlcv['close'])])
                        fig.update_layout(title=f"{selected_pair} - 1m Candlestick", height=400)
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("Tidak cukup data historis untuk analisis. Pastikan pair valid.")

    # Terapkan mode gelap/terang
    if st.session_state.settings['dark_mode']:
        st.markdown("""
        <style>
        .stApp {
            background-color: #0E1117;
            color: white;
        }
        </style>
        """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()

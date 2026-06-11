import streamlit as st
import pandas as pd
import numpy as np
import requests
import time
import json
import os
from datetime import datetime
import plotly.graph_objects as go
import ccxt  # perhatikan: ccxt, bukan cctx
from streamlit_autorefresh import st_autorefresh
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# ==================== KONFIGURASI HALAMAN ====================
st.set_page_config(page_title="HELAYO - Radar Indodax", layout="wide", initial_sidebar_state="expanded")

# ==================== INISIALISASI SESSION STATE ====================
if 'settings' not in st.session_state:
    st.session_state.settings = {
        'min_pump_threshold': 5.0,
        'min_volume_idr': 100000000,
        'refresh_interval': 30,
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

# ==================== FUNGSI API INDODAX (dengan fallback mock data) ====================
def get_indodax_tickers():
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get('https://indodax.com/api/tickers', headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') == 1:
                return data['tickers']
        return {}
    except Exception as e:
        st.warning(f"Gagal ambil data real, gunakan data simulasi: {str(e)[:50]}")
        # ----- MOCK DATA -----
        import random
        mock = {}
        coins = ['btc','eth','xrp','ada','doge','matic','sol','dot','avax','ltc','bnb','link']
        for c in coins:
            pair = f"{c}_idr"
            last = random.uniform(10000, 500_000_000)
            mock[pair] = {
                'last': str(last),
                'vol_idr': str(random.uniform(1e8, 1e11)),
                'change': str(random.uniform(-12, 18)),
                'high': str(last * 1.02),
                'low': str(last * 0.98),
                'buy': str(last * 0.99),
                'sell': str(last * 1.01)
            }
        return mock

def process_ticker_data(tickers):
    rows = []
    for pair, info in tickers.items():
        last = float(info.get('last', 0))
        volume = float(info.get('vol_idr', 0))
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
    return pd.DataFrame(rows)

def get_top_gainer_losser(df, top_n=10):
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

# ==================== ANALISIS TEKNIKAL ====================
exchange = ccxt.indodax()

def get_ohlcv(pair, timeframe='1m', limit=100):
    try:
        symbol = pair.upper().replace('_', '/')
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except:
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line, signal_line, macd_line - signal_line

def detect_sideways_breakout(df, lookback=20, threshold=0.02):
    if len(df) < lookback:
        return None
    recent = df['close'].tail(lookback)
    high, low = recent.max(), recent.min()
    if (high - low) / low < 0.05:
        last = df['close'].iloc[-1]
        if last > high * (1 + threshold):
            return "Bullish Breakout"
        elif last < low * (1 - threshold):
            return "Bearish Breakout"
    return None

def detect_candlestick_pattern(df):
    if len(df) < 1:
        return None
    last = df.iloc[-1]
    body = abs(last['close'] - last['open'])
    total = last['high'] - last['low']
    if total == 0:
        return None
    if body / total < 0.1:
        return "Doji"
    lower_wick = min(last['close'], last['open']) - last['low']
    upper_wick = last['high'] - max(last['close'], last['open'])
    if lower_wick > 2 * body and upper_wick < body:
        return "Hammer"
    if upper_wick > 2 * body and lower_wick < body:
        return "Shooting Star"
    return None

def analyze_coin(pair, settings):
    df = get_ohlcv(pair)
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
        macd, sig, hist = calculate_macd(close)
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
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        curr_vol = df['volume'].iloc[-1]
        result['Volume_Spike'] = curr_vol > 2 * avg_vol if avg_vol else False
    return result

def detect_pumps(df, threshold, min_vol):
    pumps = []
    for _, row in df.iterrows():
        if row['change_percent'] >= threshold and row['volume_idr'] >= min_vol:
            pumps.append({
                'pair': row['pair'],
                'gain_percent': row['change_percent'],
                'price': row['last_price'],
                'volume_idr': row['volume_idr'],
                'timestamp': datetime.now()
            })
    return pumps

def get_global_fear_greed():
    try:
        r = requests.get('https://api.alternative.me/fng/?limit=1')
        data = r.json()
        return int(data['data'][0]['value']), data['data'][0]['value_classification']
    except:
        return 50, "Netral"

def get_indodax_fear_greed(df):
    if df.empty:
        return 50, "Netral"
    avg = df['change_percent'].mean()
    fg = 50 + (avg * 2.5)
    fg = max(0, min(100, fg))
    if fg < 25:
        return int(fg), "Extreme Fear"
    elif fg < 45:
        return int(fg), "Fear"
    elif fg < 55:
        return int(fg), "Netral"
    elif fg < 75:
        return int(fg), "Greed"
    else:
        return int(fg), "Extreme Greed"

async def send_telegram(token, chat_id, msg):
    try:
        bot = Bot(token=token)
        await bot.send_message(chat_id=chat_id, text=msg)
        return True
    except:
        return False

def notify_pump(pumps, settings):
    if settings['telegram_token'] and settings['telegram_chat_id'] and pumps:
        msg = "🚨 *PUMP DETECTED* 🚨\n\n"
        for p in pumps[:5]:
            msg += f"• {p['pair']}: +{p['gain_percent']:.2f}% | Vol: {p['volume_idr']:,.0f} IDR\n"
        asyncio.run(send_telegram(settings['telegram_token'], settings['telegram_chat_id'], msg))

# ==================== TAMPILAN UTAMA ====================
def main():
    # Sidebar
    with st.sidebar:
        st.title("HELAYO")
        menu = st.radio("Navigasi", ["🏠 Beranda", "📈 Daftar Semua Koin", "⚡ Sinyal Pump"])
        st.markdown("---")
        st.subheader("⚙️ Pengaturan Deteksi")
        new_threshold = st.slider("🎯 Min. Pump Threshold (%)", 0.0, 50.0, st.session_state.settings['min_pump_threshold'], 0.5)
        new_min_vol = st.number_input("📦 Min. Volume IDR", min_value=0, value=int(st.session_state.settings['min_volume_idr']), step=50000000)
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
                asyncio.run(send_telegram(token, chat_id, "✅ Helayo bot connected!"))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Simpan Pengaturan"):
                st.session_state.settings['min_pump_threshold'] = new_threshold
                st.session_state.settings['min_volume_idr'] = new_min_vol
                st.session_state.settings['refresh_interval'] = new_interval
                st.session_state.settings['telegram_token'] = token
                st.session_state.settings['telegram_chat_id'] = chat_id
                st.success("Tersimpan!")
        with col2:
            if st.button("▶️ Auto Start"):
                st.session_state.settings['auto_start'] = True
                st.rerun()
        
        st.markdown("---")
        dark_mode = st.toggle("🌙 Mode Gelap", value=st.session_state.settings['dark_mode'])
        st.session_state.settings['dark_mode'] = dark_mode
        
        with st.expander("📘 Tutorial & Strategi"):
            st.markdown("Atur threshold, aktifkan analisis, klik Auto Start. Pantau sinyal pump.")
        with st.expander("ℹ️ Tentang Aplikasi"):
            st.markdown("HELAYO v1.0 - Radar Indodax")
    
    # Auto refresh
    if st.session_state.settings['auto_start']:
        st_autorefresh(interval=st.session_state.settings['refresh_interval']*1000, key="auto")
    
    # Ambil data
    tickers_raw = get_indodax_tickers()
    if not tickers_raw:
        st.error("Tidak ada data. Cek koneksi atau gunakan mock data (sudah fallback).")
        return
    df_tickers = process_ticker_data(tickers_raw)
    st.session_state.tickers_data = df_tickers
    
    pumps = detect_pumps(df_tickers, st.session_state.settings['min_pump_threshold'], st.session_state.settings['min_volume_idr'])
    if pumps:
        st.session_state.pump_signals = pumps + st.session_state.pump_signals[:20]
        notify_pump(pumps[:3], st.session_state.settings)
    
    st.session_state.last_update = datetime.now()
    
    # ========== BERANDA ==========
    if menu == "🏠 Beranda":
        st.title("📊 Radar Market Indodax")
        total_vol = get_total_volume_all(df_tickers)
        naik, turun = get_coin_count_naik_turun(df_tickers)
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Total Volume 24h", f"{total_vol:,.0f}")
        col2.metric("Koin Naik", naik)
        col3.metric("Koin Turun", turun)
        col4.metric("Total Koin", len(df_tickers))
        col5.metric("Sentimen", "🟢 Bullish" if naik > turun else "🔴 Bearish")
        
        gainers, losers = get_top_gainer_losser(df_tickers, 10)
        high_vol = get_highest_volume(df_tickers, 10)
        col_a, col_b, col_c = st.columns(3)
        with col_a: st.subheader("🚀 Top Gainer"); st.dataframe(gainers)
        with col_b: st.subheader("📉 Top Losser"); st.dataframe(losers)
        with col_c: st.subheader("🔥 Volume Tertinggi"); st.dataframe(high_vol)
        
        fg_glob, fg_glob_class = get_global_fear_greed()
        fg_id, fg_id_class = get_indodax_fear_greed(df_tickers)
        col_d, col_e = st.columns(2)
        with col_d: st.metric("🌍 Fear & Greed Global", f"{fg_glob} - {fg_glob_class}")
        with col_e: st.metric("🇮🇩 Fear & Greed Indodax", f"{fg_id} - {fg_id_class}")
        
        st.subheader("🔔 Sinyal Pump Terbaru")
        if st.session_state.pump_signals:
            st.dataframe(pd.DataFrame(st.session_state.pump_signals[:10])[['pair','gain_percent','price','volume_idr','timestamp']])
        else:
            st.info("Belum ada sinyal pump.")
        
        st.subheader("📈 10 Trending Indodax")
        trending = df_tickers.nlargest(10, 'change_percent')[['pair','change_percent','last_price']]
        st.dataframe(trending)
        st.subheader("💎 10 Volume Tertinggi")
        st.dataframe(high_vol)
    
    # ========== DAFTAR KOIN ==========
    elif menu == "📈 Daftar Semua Koin":
        st.title("📋 Daftar Semua Koin")
        search = st.text_input("Cari koin")
        df_filter = df_tickers[df_tickers['pair'].str.contains(search.upper())] if search else df_tickers
        st.dataframe(df_filter)
    
    # ========== SINYAL PUMP ==========
    elif menu == "⚡ Sinyal Pump":
        st.title("🚨 Daftar Sinyal Pump")
        if st.session_state.pump_signals:
            st.dataframe(pd.DataFrame(st.session_state.pump_signals))
        else:
            st.info("Belum ada sinyal.")
        if st.button("Refresh Manual"): st.rerun()
        st.subheader("🔬 Analisis Teknikal (Pilih Koin)")
        selected = st.selectbox("Pilih koin", df_tickers['pair'].unique())
        if selected:
            anal = analyze_coin(selected, st.session_state.settings['analysis_enabled'])
            if anal:
                st.write(anal)
            else:
                st.warning("Data OHLCV tidak cukup.")
    
    # Mode gelap
    if st.session_state.settings['dark_mode']:
        st.markdown("<style>.stApp { background-color: #0E1117; color: white; }</style>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

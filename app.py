import streamlit as st
import pandas as pd
import numpy as np
import requests
import random
from datetime import datetime
import plotly.graph_objects as go
import ccxt
from streamlit_autorefresh import st_autorefresh
import asyncio
from telegram import Bot
from telegram.error import TelegramError

# ==================== KONFIGURASI ====================
st.set_page_config(page_title="HELAYO - Radar Indodax", layout="wide", initial_sidebar_state="expanded")

# ==================== SESSION STATE ====================
if 'settings' not in st.session_state:
    st.session_state.settings = {
        'min_pump_threshold': 5.0,
        'min_volume_idr': 100_000_000,
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

# ==================== DATA INDODAX (MOCK / REAL) ====================
def get_indodax_tickers():
    """Coba ambil data real, jika gagal pakai mock data"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get('https://indodax.com/api/tickers', headers=headers, timeout=8)
        if resp.status_code == 200:
            data = resp.json()
            if data.get('success') == 1 and data.get('tickers'):
                return data['tickers']
    except Exception as e:
        st.warning(f"Tidak dapat akses API Indodax: {str(e)[:80]}. Menggunakan data simulasi.")
    
    # --- MOCK DATA (data simulasi) ---
    st.info("📡 Mode simulasi aktif (data tidak real-time).")
    coins = ['btc','eth','xrp','ada','doge','matic','sol','dot','avax','ltc','bnb','link','xlm','trx','eos','near','algo','vet','theta','ftm']
    mock = {}
    for c in coins:
        pair = f"{c}_idr"
        last = random.uniform(10_000, 500_000_000)
        mock[pair] = {
            'last': str(last),
            'vol_idr': str(random.uniform(1e8, 1e11)),
            'change': str(random.uniform(-15, 25)),
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
        })
    return pd.DataFrame(rows)

def get_top_gainer_losser(df, top_n=10):
    gainers = df.nlargest(top_n, 'change_percent')[['pair','change_percent','last_price','volume_idr']]
    losers = df.nsmallest(top_n, 'change_percent')[['pair','change_percent','last_price','volume_idr']]
    return gainers, losers

def get_highest_volume(df, top_n=10):
    return df.nlargest(top_n, 'volume_idr')[['pair','volume_idr','last_price','change_percent']]

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
        df = pd.DataFrame(ohlcv, columns=['timestamp','open','high','low','close','volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except:
        return pd.DataFrame()

def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_ema(series, period):
    return series.ewm(span=period, adjust=False).mean()

def calculate_macd(series, fast=12, slow=26, signal=9):
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

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
    close = df['close']
    res = {}
    if settings.get('rsi', True):
        rsi = calculate_rsi(close)
        res['RSI'] = round(rsi.iloc[-1], 2) if not rsi.empty else None
    if settings.get('ema', True):
        ema9 = calculate_ema(close, 9)
        ema50 = calculate_ema(close, 50)
        res['EMA9'] = round(ema9.iloc[-1], 2) if not ema9.empty else None
        res['EMA50'] = round(ema50.iloc[-1], 2) if not ema50.empty else None
        res['EMA_Signal'] = "Bullish" if ema9.iloc[-1] > ema50.iloc[-1] else "Bearish"
    if settings.get('macd', True):
        _, _, hist = calculate_macd(close)
        res['MACD_Hist'] = round(hist.iloc[-1], 4) if not hist.empty else None
        if len(hist) > 1:
            if hist.iloc[-1] > 0 and hist.iloc[-2] <= 0:
                res['MACD_Cross'] = "Bullish"
            elif hist.iloc[-1] < 0 and hist.iloc[-2] >= 0:
                res['MACD_Cross'] = "Bearish"
    if settings.get('sideways_breakout', True):
        res['Sideways'] = detect_sideways_breakout(df)
    if settings.get('candlestick_pattern', True):
        res['Candlestick'] = detect_candlestick_pattern(df)
    if settings.get('volume_price', True):
        avg_vol = df['volume'].rolling(20).mean().iloc[-1]
        curr_vol = df['volume'].iloc[-1]
        res['Volume_Spike'] = curr_vol > 2 * avg_vol if avg_vol else False
    return res

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
        r = requests.get('https://api.alternative.me/fng/?limit=1', timeout=5)
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
    if fg < 25: return int(fg), "Extreme Fear"
    if fg < 45: return int(fg), "Fear"
    if fg < 55: return int(fg), "Netral"
    if fg < 75: return int(fg), "Greed"
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
        msg = "🚨 *PUMP DETECTED* 🚨\n"
        for p in pumps[:5]:
            msg += f"• {p['pair']}: +{p['gain_percent']:.2f}% | Vol: {p['volume_idr']:,.0f} IDR\n"
        asyncio.run(send_telegram(settings['telegram_token'], settings['telegram_chat_id'], msg))

# ==================== TAMPILAN UTAMA ====================
def main():
    with st.sidebar:
        st.title("HELAYO")
        menu = st.radio("Navigasi", ["🏠 Beranda", "📈 Daftar Semua Koin", "⚡ Sinyal Pump"])
        st.markdown("---")
        st.subheader("⚙️ Pengaturan")
        new_threshold = st.slider("🎯 Min. Pump Threshold (%)", 0.0, 50.0, st.session_state.settings['min_pump_threshold'], 0.5)
        new_min_vol = st.number_input("📦 Min. Volume IDR", 0, int(st.session_state.settings['min_volume_idr']), step=50_000_000)
        new_interval = st.number_input("⏱️ Interval Refresh (detik)", 5, 300, st.session_state.settings['refresh_interval'], 5)
        with st.expander("🔬 Analisis Teknikal"):
            for key in st.session_state.settings['analysis_enabled']:
                st.session_state.settings['analysis_enabled'][key] = st.checkbox(key.replace('_',' ').title(), st.session_state.settings['analysis_enabled'][key])
        with st.expander("🤖 Bot Telegram"):
            token = st.text_input("Bot Token", value=st.session_state.settings['telegram_token'], type="password")
            chat_id = st.text_input("Chat ID", value=st.session_state.settings['telegram_chat_id'])
            if st.button("Tes Kirim"):
                asyncio.run(send_telegram(token, chat_id, "✅ Helayo bot connected!"))
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 Simpan"):
                st.session_state.settings.update({'min_pump_threshold': new_threshold, 'min_volume_idr': new_min_vol, 'refresh_interval': new_interval, 'telegram_token': token, 'telegram_chat_id': chat_id})
                st.success("Tersimpan")
        with col2:
            if st.button("▶️ Auto Start"):
                st.session_state.settings['auto_start'] = True
                st.rerun()
        st.markdown("---")
        dark_mode = st.toggle("🌙 Mode Gelap", st.session_state.settings['dark_mode'])
        st.session_state.settings['dark_mode'] = dark_mode
        with st.expander("📘 Tutorial"):
            st.markdown("Atur threshold dan volume, aktifkan Auto Start, pantau sinyal pump.")
        with st.expander("ℹ️ Tentang"):
            st.markdown("HELAYO v1.0 - Radar Indodax (mode simulasi jika API offline)")

    if st.session_state.settings['auto_start']:
        st_autorefresh(interval=st.session_state.settings['refresh_interval']*1000, key="auto")

    tickers_raw = get_indodax_tickers()
    if not tickers_raw:
        st.error("Gagal mendapatkan data (bahkan mock). Cek ulang.")
        return
    df = process_ticker_data(tickers_raw)
    st.session_state.tickers_data = df

    pumps = detect_pumps(df, st.session_state.settings['min_pump_threshold'], st.session_state.settings['min_volume_idr'])
    if pumps:
        st.session_state.pump_signals = pumps + st.session_state.pump_signals[:20]
        notify_pump(pumps[:3], st.session_state.settings)
    st.session_state.last_update = datetime.now()

    if menu == "🏠 Beranda":
        st.title("📊 Radar Market Indodax")
        total_vol = get_total_volume_all(df)
        naik, turun = get_coin_count_naik_turun(df)
        c1,c2,c3,c4,c5 = st.columns(5)
        c1.metric("Total Volume 24h", f"{total_vol:,.0f}")
        c2.metric("Koin Naik", naik)
        c3.metric("Koin Turun", turun)
        c4.metric("Total Koin", len(df))
        c5.metric("Sentimen", "🟢 Bullish" if naik > turun else "🔴 Bearish")
        gainers, losers = get_top_gainer_losser(df)
        high_vol = get_highest_volume(df)
        col_a, col_b, col_c = st.columns(3)
        with col_a: st.subheader("🚀 Top Gainer"); st.dataframe(gainers)
        with col_b: st.subheader("📉 Top Losser"); st.dataframe(losers)
        with col_c: st.subheader("🔥 Volume Tertinggi"); st.dataframe(high_vol)
        fg_glob, fg_glob_c = get_global_fear_greed()
        fg_id, fg_id_c = get_indodax_fear_greed(df)
        c_d, c_e = st.columns(2)
        with c_d: st.metric("🌍 Fear & Greed Global", f"{fg_glob} - {fg_glob_c}")
        with c_e: st.metric("🇮🇩 Fear & Greed Indodax", f"{fg_id} - {fg_id_c}")
        st.subheader("🔔 Sinyal Pump Terbaru")
        if st.session_state.pump_signals:
            st.dataframe(pd.DataFrame(st.session_state.pump_signals[:10])[['pair','gain_percent','price','volume_idr','timestamp']])
        else:
            st.info("Belum ada sinyal pump.")
        st.subheader("📈 10 Trending Indodax")
        trending = df.nlargest(10, 'change_percent')[['pair','change_percent','last_price']]
        st.dataframe(trending)
        st.subheader("💎 10 Volume Tertinggi")
        st.dataframe(high_vol)

    elif menu == "📈 Daftar Semua Koin":
        st.title("📋 Daftar Semua Koin")
        search = st.text_input("Cari koin")
        if search:
            df = df[df['pair'].str.contains(search.upper())]
        st.dataframe(df.style.format({'last_price':'{:,.2f}','volume_idr':'{:,.0f}','change_percent':'{:.2f}%'}))

    elif menu == "⚡ Sinyal Pump":
        st.title("🚨 Sinyal Pump")
        if st.session_state.pump_signals:
            st.dataframe(pd.DataFrame(st.session_state.pump_signals))
        else:
            st.info("Belum ada sinyal pump.")
        if st.button("Refresh Manual"):
            st.rerun()
        st.subheader("🔬 Analisis Teknikal")
        selected = st.selectbox("Pilih koin", df['pair'].unique())
        if selected:
            anal = analyze_coin(selected, st.session_state.settings['analysis_enabled'])
            if anal:
                st.json(anal)
            else:
                st.warning("Data OHLCV tidak tersedia untuk koin ini.")

    if st.session_state.settings['dark_mode']:
        st.markdown("<style>.stApp { background-color: #0E1117; color: white; }</style>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()

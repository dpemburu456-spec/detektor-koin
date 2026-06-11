import streamlit as st
import requests
import pandas as pd

# Konfigurasi Halaman
st.set_page_config(page_title="Crypto Dashboard", layout="wide")

# Judul dan CSS Kustom agar mirip Dashboard
st.markdown("""
    <style>
    .metric-card {background-color: #f0f2f6; padding: 20px; border-radius: 10px;}
    </style>
""", unsafe_allow_html=True)

st.title("📈 Crypto Market Dashboard")

# Fungsi ambil data
def get_data():
    url = "https://indodax.com/api/summaries"
    try:
        response = requests.get(url)
        return response.json()['tickers']
    except:
        return None

data = get_data()

if data:
    # Mengolah data ke DataFrame
    tickers = []
    for pair, info in data.items():
        tickers.append({
            "Koin": pair.upper(),
            "Harga": float(info['last']),
            "Volume": float(info.get('vol_idr', 0))
        })
    df = pd.DataFrame(tickers)

    # 1. Menampilkan Metric (Statistik Utama di atas)
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Koin Dipantau", len(df))
    col2.metric("Volume Tertinggi (IDR)", f"{df['Volume'].max():,.0f}")
    col3.metric("Harga BTC (IDR)", f"{df[df['Koin']=='BTC_IDR']['Harga'].values[0]:,.0f}")

    # 2. Fitur Pencarian dan Filter
    st.subheader("Market Overview")
    search = st.text_input("Cari Koin (contoh: BTC):").upper()
    if search:
        df = df[df['Koin'].str.contains(search)]

    # 3. Menampilkan Tabel
    st.dataframe(df, use_container_width=True)

else:
    st.error("Gagal memuat data pasar.")
    st.error("Gagal mengambil data dari Indodax. Silakan refresh.")

import streamlit as st
import requests
import pandas as pd

# Konfigurasi Tampilan
st.set_page_config(page_title="Pro Crypto Dashboard", layout="wide")

# Judul dan Styling CSS
st.markdown("""
    <style>
    .main {background-color: #f5f7f9;}
    .stMetric {background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);}
    </style>
""", unsafe_allow_html=True)

st.title("🚀 Pro Crypto Dashboard")

# Fungsi Ambil Data
@st.cache_data(ttl=60) # Data di-refresh setiap 60 detik
def get_data():
    url = "https://indodax.com/api/summaries"
    try:
        response = requests.get(url)
        data = response.json()['tickers']
        rows = []
        for pair, info in data.items():
            rows.append({
                "Koin": pair.upper(),
                "Harga": float(info['last']),
                "Volume": float(info.get('vol_idr', 0))
            })
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()

df = get_data()

if not df.empty:
    # Top 3 Statistik
    col1, col2, col3 = st.columns(3)
    max_vol_coin = df.loc[df['Volume'].idxmax()]
    col1.metric("Total Koin", len(df))
    col2.metric("Volume Tertinggi", max_vol_coin['Koin'], f"{max_vol_coin['Volume']:,.0f}")
    col3.metric("BTC/IDR", f"{df[df['Koin']=='BTC_IDR']['Harga'].values[0]:,.0f}")

    # Grafik Volume
    st.subheader("Visualisasi Volume Perdagangan")
    top_10 = df.nlargest(10, 'Volume')
    st.bar_chart(top_10.set_index('Koin')['Volume'])

    # Tabel Pencarian
    st.subheader("Data Market")
    query = st.text_input("🔍 Cari koin (misal: ETH):")
    if query:
        df = df[df['Koin'].str.contains(query.upper())]
    
    st.dataframe(df.sort_values(by='Volume', ascending=False), use_container_width=True)
else:
    st.warning("Data sedang dimuat atau gagal terhubung ke server Indodax.")

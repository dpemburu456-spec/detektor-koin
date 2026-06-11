import streamlit as st
import requests
import pandas as pd

# Konfigurasi Layout agar lebar dan padat
st.set_page_config(page_title="Indodax Pro Dashboard", layout="wide")

st.title("📊 Indodax Real-time Dashboard")

@st.cache_data(ttl=30) # Refresh lebih sering
def get_detailed_data():
    url = "https://indodax.com/api/summaries"
    try:
        response = requests.get(url)
        data = response.json()['tickers']
        rows = []
        for pair, info in data.items():
            # Menghitung % perubahan jika ada data base_volume/last
            last = float(info['last'])
            high = float(info['high'])
            low = float(info['low'])
            vol = float(info.get('vol_idr', 0))
            
            rows.append({
                "Koin": pair.upper().replace("_IDR", ""),
                "Harga (IDR)": last,
                "High (24h)": high,
                "Low (24h)": low,
                "Volume (IDR)": vol
            })
        return pd.DataFrame(rows)
    except:
        return pd.DataFrame()

df = get_detailed_data()

if not df.empty:
    # Sidebar untuk filter
    st.sidebar.header("Filter Market")
    min_vol = st.sidebar.slider("Minimal Volume (Miliar IDR)", 0, int(df['Volume (IDR)'].max()/1000000000), 0)
    
    # Terapkan filter
    df_filtered = df[df['Volume (IDR)'] >= (min_vol * 1000000000)]
    
    # Tampilan tabel dengan format angka agar mudah dibaca
    st.dataframe(
        df_filtered.style.format({
            "Harga (IDR)": "{:,.0f}",
            "High (24h)": "{:,.0f}",
            "Low (24h)": "{:,.0f}",
            "Volume (IDR)": "{:,.0f}"
        }),
        use_container_width=True,
        height=600
    )
else:
    st.error("Gagal mengambil data dari Indodax.")

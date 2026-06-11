import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Detektor Pump Indodax", layout="wide")
st.title("📊 Detektor Koin Pump - Indodax")

def get_indodax_data():
    url = "https://indodax.com/api/summaries"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()['tickers']
    except:
        return None
    return None

data = get_indodax_data()
if data:
    tickers = []
    for pair, info in data.items():
        # Menggunakan .get agar tidak error jika data tidak ditemukan
        vol = info.get('vol_idr', info.get('vol_btc', 0)) 
        tickers.append({
            "Koin": pair.upper(),
            "Harga": float(info.get('last', 0)),
            "Volume": float(vol)
        })
    
    df = pd.DataFrame(tickers)
    avg_vol = df['Volume'].mean()
    pump_coins = df[df['Volume'] > avg_vol * 2].sort_values(by='Volume', ascending=False)
    
    st.subheader("Koin dengan Lonjakan Volume Tinggi:")
    st.table(pump_coins.head(10))
else:
    st.error("Gagal mengambil data dari Indodax. Silakan refresh.")

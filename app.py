import streamlit as st
import requests
import pandas as pd

st.set_page_config(page_title="Detektor Pump Indodax", layout="wide")
st.title("📊 Detektor Koin Pump - Indodax")

# Mengambil data dari API publik Indodax
def get_indodax_data():
    url = "https://indodax.com/api/summaries"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()['tickers']
    return None

data = get_indodax_data()
if data:
    tickers = []
    for pair, info in data.items():
        tickers.append({
            "Koin": pair.upper(),
            "Harga": float(info['last']),
            "Volume": float(info['vol_idr'])
        })
    
    df = pd.DataFrame(tickers)
    
    # Filter: Tampilkan yang volume-nya di atas rata-rata
    avg_vol = df['Volume'].mean()
    pump_coins = df[df['Volume'] > avg_vol * 2].sort_values(by='Volume', ascending=False)
    
    st.subheader("Koin dengan Lonjakan Volume Tinggi:")
    st.table(pump_coins.head(10)) 
else:
    st.error("Gagal mengambil data dari Indodax.")

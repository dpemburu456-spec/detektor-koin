# app.py
import streamlit as st
import requests
import pandas as pd
import time
from streamlit_autorefresh import st_autorefresh

# Konfigurasi halaman
st.set_page_config(
    page_title="Indodax Pump Detector",
    page_icon="📈",
    layout="wide"
)

# Fungsi untuk mengambil data ticker dari Indodax
@st.cache_data(ttl=30)  # cache data selama 30 detik untuk menghindari request berlebihan
def fetch_ticker_all():
    url = "https://indodax.com/api/ticker_all"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data
    except Exception as e:
        st.error(f"Gagal mengambil data dari API Indodax: {e}")
        return None

# Fungsi untuk memproses data ticker menjadi DataFrame
def process_ticker_data(data, filter_idr=True):
    if not data:
        return pd.DataFrame()
    
    rows = []
    for pair, info in data.items():
        # Filter hanya pasangan dengan IDR (jika diinginkan)
        if filter_idr and not pair.endswith('_idr'):
            continue
        
        try:
            last_price = float(info.get('last', 0))
            volume = float(info.get('vol', 0))
            high = float(info.get('high', 0))
            low = float(info.get('low', 0))
            
            rows.append({
                'pair': pair.upper(),
                'last_price': last_price,
                'volume_24h': volume,
                'high_24h': high,
                'low_24h': low
            })
        except (ValueError, TypeError):
            continue
    
    df = pd.DataFrame(rows)
    return df

# Inisialisasi session state untuk menyimpan snapshot harga sebelumnya
if 'last_snapshot' not in st.session_state:
    st.session_state.last_snapshot = {}  # {pair: (timestamp, last_price)}

# Sidebar untuk parameter
st.sidebar.title("⚙️ Parameter Deteksi")
threshold = st.sidebar.number_input("🚀 Threshold Pump (%)", min_value=0.5, max_value=50.0, value=3.0, step=0.5)
period = st.sidebar.number_input("⏱️ Periode Deteksi (detik)", min_value=30, max_value=600, value=60, step=10)
refresh_interval = st.sidebar.number_input("🔄 Interval Refresh (detik)", min_value=5, max_value=120, value=10, step=5)
min_volume = st.sidebar.number_input("💰 Volume 24h Minimum (IDR)", min_value=0, value=100000000, step=10000000, format="%d")
filter_idr = st.sidebar.checkbox("🇮🇩 Hanya Pasangan IDR", value=True)

# Auto-refresh halaman
st_autorefresh(interval=refresh_interval * 1000, key="auto_refresh")

# Header
st.title("📈 Indodax Pump Detector")
st.markdown(f"Memantau **{threshold}%** kenaikan dalam **{period} detik** | Refresh setiap **{refresh_interval} detik**")

# Ambil data terbaru
data = fetch_ticker_all()
if data is None:
    st.stop()

df_current = process_ticker_data(data, filter_idr=filter_idr)
total_pairs = len(df_current)
st.info(f"📊 Memantau {total_pairs} pasangan koin")

if df_current.empty:
    st.warning("Tidak ada data pasangan yang ditemukan. Coba nonaktifkan filter IDR.")
    st.stop()

# Waktu sekarang (timestamp Unix)
current_time = time.time()

# Dictionary untuk menyimpan sinyal pump
pump_signals = []

# Proses setiap pair untuk deteksi pump
for _, row in df_current.iterrows():
    pair = row['pair']
    current_price = row['last_price']
    volume = row['volume_24h']
    
    # Filter volume minimum
    if volume < min_volume:
        continue
    
    # Cek apakah pair sudah pernah disimpan snapshotnya
    if pair in st.session_state.last_snapshot:
        last_time, last_price = st.session_state.last_snapshot[pair]
        elapsed = current_time - last_time
        
        # Jika sudah melewati periode deteksi, hitung perubahan harga
        if elapsed >= period:
            if last_price > 0:
                pct_change = (current_price - last_price) / last_price * 100
                if pct_change >= threshold:
                    pump_signals.append({
                        'Pair': pair,
                        'Perubahan (%)': round(pct_change, 2),
                        'Harga Sekarang': current_price,
                        'Harga Sebelumnya': last_price,
                        'Volume (24h)': volume,
                        'Waktu Deteksi': time.strftime('%H:%M:%S', time.localtime(current_time))
                    })
            # Update snapshot dengan data terbaru (timestamp dan harga sekarang)
            st.session_state.last_snapshot[pair] = (current_time, current_price)
    else:
        # Pair baru: simpan snapshot tanpa deteksi
        st.session_state.last_snapshot[pair] = (current_time, current_price)

# Tampilkan hasil deteksi
st.subheader("🚨 Sinyal Pump Terdeteksi")
if pump_signals:
    df_signals = pd.DataFrame(pump_signals)
    df_signals = df_signals.sort_values('Perubahan (%)', ascending=False)
    st.dataframe(df_signals, use_container_width=True)
    
    # Notifikasi tambahan jika ada sinyal baru (opsional)
    st.balloons()
    st.success(f"🎉 Terdeteksi {len(df_signals)} sinyal pump!")
else:
    st.info("Belum ada sinyal pump dalam periode terakhir. Pantau terus.")

# Tampilkan semua pasangan yang dipantau (opsional, bisa diexpand)
with st.expander("📋 Daftar Semua Pasangan yang Dipantau"):
    st.dataframe(df_current[['pair', 'last_price', 'volume_24h']].head(50), use_container_width=True)
    if total_pairs > 50:
        st.caption(f"Menampilkan 50 dari {total_pairs} pasangan. Scroll untuk melihat lebih banyak (tidak ditampilkan karena keterbatasan tampilan).")

# Tampilkan status snapshot
with st.expander("ℹ️ Status Detektor"):
    st.write(f"Jumlah snapshot tersimpan: {len(st.session_state.last_snapshot)}")
    st.write("Snapshot akan terus diperbarui setiap refresh. Deteksi hanya terjadi setelah periode yang ditentukan.")
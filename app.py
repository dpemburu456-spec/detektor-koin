import streamlit as st
import requests
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# ==========================================
# 1. KONFIGURASI HALAMAN DAN TEMA GELAP (CSS)
# ==========================================
st.set_page_config(
    page_title="HELAYO Clone - Radar Pump Indodax",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Menyuntikkan CSS Kustom agar tampilan menyerupai dashboard premium asli
st.markdown("""
    <style>
    /* Mengubah latar belakang utama */
    .stApp { background-color: #030914; color: #ffffff; }
    
    /* Desain Kotak Metrik / Kartu Informasi */
    .metric-container {
        background-color: #0b1528;
        border-radius: 8px;
        padding: 15px;
        border: 1px solid #142544;
        text-align: center;
        margin-bottom: 10px;
    }
    .metric-title { color: #8fa0dd; font-size: 12px; font-weight: bold; text-transform: uppercase; }
    .metric-value { color: #00ffcc; font-size: 22px; font-weight: bold; margin: 5px 0; }
    .metric-desc { color: #506690; font-size: 11px; }
    
    /* Desain Kotak Sinyal Pump */
    .signal-card {
        background-color: #0d1b3e;
        border-left: 4px solid #ff9900;
        padding: 12px;
        border-radius: 4px;
        margin-bottom: 8px;
    }
    .badge-new {
        background-color: #ff5500; color: white; padding: 2px 6px;
        border-radius: 3px; font-size: 10px; font-weight: bold;
    }
    
    /* Menghilangkan elemen default Streamlit */
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. PROSES PENGAMBILAN DATA (API INDODAX)
# ==========================================
@st.cache_data(ttl=10)  # Sinkronisasi super cepat setiap 10 detik
def fetch_market_data():
    url = "https://indodax.com/api/summaries"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            tickers = response.json().get('tickers', {})
            prices = response.json().get('prices_24h', {})
            
            rows = []
            for pair, info in tickers.items():
                if not pair.endswith('_idr'): 
                    continue  # Hanya fokus ke pasar IDR murni seperti HELAYO
                
                last = float(info.get('last', 0))
                high = float(info.get('high', 0))
                low = float(info.get('low', 0))
                vol_idr = float(info.get('vol_idr', 0))
                
                # Mengalkulasi estimasi harga pembukaan 24 jam lalu untuk melacak persentase naik/turun
                open_24h = prices.get(pair, last)
                change_pct = ((last - open_24h) / open_24h * 100) if open_24h > 0 else 0.0
                
                rows.append({
                    "Koin": pair.upper().replace("_IDR", ""),
                    "Harga": last,
                    "High": high,
                    "Low": low,
                    "Volume": vol_idr,
                    "Change_Pct": change_pct
                })
            return pd.DataFrame(rows)
    except Exception as e:
        st.error(f"Koneksi API Gagal: {e}")
    return pd.DataFrame()

df = fetch_market_data()

if df.empty:
    st.error("Gagal menyinkronkan data dengan Server Indodax. Silakan periksa koneksi internet Anda.")
    st.stop()

# ==========================================
# 3. STRUKTUR MENU BILAH SAMPING (SIDEBAR)
# ==========================================
with st.sidebar:
    st.title("🦊 HELAYO")
    st.caption("RADAR PUMP INDODAX • VERSI PRO")
    st.markdown("---")
    
    st.subheader("🟢 MONITOR SERVER 24/7")
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        st.success("Aktif")
    with col_btn2:
        if st.button("Restart"):
            st.rerun()
            
    st.markdown("---")
    st.subheader("⚙️ PENGATURAN DETEKSI")
    pump_threshold = st.slider("Min. Pump Threshold (%)", 1, 20, 10)
    min_volume = st.number_input("Min. Volume 24H (Rupiah)", min_value=10000000, value=500000000, step=50000000)
    
    st.markdown("---")
    st.subheader("📊 ANALISIS TEKNIKAL")
    st.toggle("Pola Candlestick", value=True)
    st.toggle("RSI (14)", value=True)
    st.toggle("MACD (12, 26, 9)", value=True)
    st.toggle("Volume × Harga", value=True)

# ==========================================
# 4. DASBOR UTAMA (BERANDA)
# ==========================================
now_str = datetime.now().strftime("%H:%M:%S")
st.markdown(f"### 🏠 Beranda <span style='color:#506690; font-size:14px;'>• Update terakhir: {now_str} | {len(df)} Pasangan Koin</span>", unsafe_allow_html=True)

# Filter awal berdasarkan parameter volume minimum di bilah samping
df_active = df[df['Volume'] >= min_volume]
df_naik = df_active[df_active['Change_Pct'] > 0]
df_turun = df_active[df_active['Change_Pct'] < 0]
df_pump = df_active[df_active['Change_Pct'] >= pump_threshold]

# Baris Kotak Informasi Utama (Top Metrik)
c1, c2, c3, c4, c5 = st.columns(5)
with c1:
    total_vol_miliar = df['Volume'].sum() / 1e9
    st.markdown(f"<div class='metric-container'><div class='metric-title'>Total Volume 24H</div><div class='metric-value'>Rp {total_vol_miliar:,.2f} M</div><div class='metric-desc'>Seluruh Pasar Indodax</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='metric-container'><div class='metric-title'>🟢 Koin Naik</div><div class='metric-value'>{len(df_naik)}</div><div class='metric-desc'>{len(df_naik)/len(df_active)*100:.1f}% dari aktif</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div class='metric-container'><div class='metric-title'>🔴 Koin Turun</div><div class='metric-value'>{len(df_turun)}</div><div class='metric-desc'>{len(df_turun)/len(df_active)*100:.1f}% dari aktif</div></div>", unsafe_allow_html=True)
with c4:
    st.markdown(f"<div class='metric-container'><div class='metric-title'>⚡ Sinyal Pump</div><div class='metric-value' style='color:#ffaa00;'>{len(df_pump)}</div><div class='metric-desc'>Memenuhi ambang batas</div></div>", unsafe_allow_html=True)
with c5:
    st.markdown(f"<div class='metric-container'><div class='metric-title'>Total Koin</div><div class='metric-value' style='color:#ffffff;'>{len(df)}</div><div class='metric-desc'>Pasangan IDR Terdaftar</div></div>", unsafe_allow_html=True)

# Layout Tengah: Pengukur Sentimen Pasar & Sinyal Pump Terbaru
col_mid1, col_mid2 = st.columns([4, 6])

with col_mid1:
    st.markdown("#### 🧭 Sentimen Pasar (Real-time)")
    # Kalkulasi skor sentimen rasional berdasarkan persentase koin yang mengalami kenaikan harga
    sentimen_score = int((len(df_naik) / len(df_active)) * 100) if len(df_active) > 0 else 50
    
    # Membuat komponen Gauge Chart interaktif menggunakan Plotly
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=sentimen_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "#ffffff"},
            'bar': {'color': "#ffffff"},
            'bgcolor': "#0b1528",
            'borderwidth': 2,
            'bordercolor': "#142544",
            'steps': [
                {'range': [0, 30], 'color': '#ff3333'},
                {'range': [30, 45], 'color': '#ff9933'},
                {'range': [45, 65], 'color': '#e6b800'},
                {'range': [65, 85], 'color': '#33cc33'},
                {'range': [85, 100], 'color': '#00ffcc'}
            ],
        }
    ))
    fig_gauge.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "#ffffff", 'family': "Arial"},
        height=220,
        margin=dict(l=10, r=10, t=10, b=10)
    )
    st.plotly_chart(fig_gauge, use_container_width=True)

with col_mid2:
    st.markdown("#### 🔥 Sinyal Pump Terbaru")
    if not df_pump.empty:
        # Menampilkan koin dengan lonjakan harga tertinggi di urutan paling atas
        df_pump_sorted = df_pump.sort_values(by='Change_Pct', ascending=False).head(4)
        for _, row in df_pump_sorted.iterrows():
            st.markdown(f"""
                <div class='signal-card'>
                    <span class='badge-new'>BARU</span>
                    <strong style='color:#00ffcc; font-size:16px; margin-left:5px;'>{row['Koin']}</strong> 
                    <span style='color:#ffffff; margin-left:10px;'>Harga: Rp {row['Harga']:,.0f}</span>
                    <span style='float:right; color:#00ff55; font-weight:bold;'>+{row['Change_Pct']:.2f}%</span>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.info("Belum mendeteksi koin yang menembus kriteria batas pump dalam jangka waktu ini.")

# Layout Bawah: Komparasi Berdampingan Dua Tabel Analisis Utama
st.markdown("---")
col_bot1, col_bot2 = st.columns(2)

with col_bot1:
    st.markdown("#### 🔥 10 Trending Koin (% 24h)")
    df_trending = df_active.sort_values(by='Change_Pct', ascending=False).head(10)[['Koin', 'Harga', 'Change_Pct']]
    # Pemformatan visual tabel agar rapi dan bersih
    df_trending.columns = ['Nama Koin', 'Harga Terakhir (Rp)', 'Kenaikan 24H']
    st.dataframe(
        df_trending.style.format({
            'Harga Terakhir (Rp)': '{:,.0f}',
            'Kenaikan 24H': '{:+.2f}%'
        }), 
        use_container_width=True, 
        hide_index=True
    )

with col_bot2:
    st.markdown("#### 🐳 10 Volume Tertinggi Indodax")
    df_volume_top = df_active.sort_values(by='Volume', ascending=False).head(10)[['Koin', 'Harga', 'Volume']]
    df_volume_top.columns = ['Nama Koin', 'Harga Terakhir (Rp)', 'Akumulasi Volume (IDR)']
    st.dataframe(
        df_volume_top.style.format({
            'Harga Terakhir (Rp)': '{:,.0f}',
            'Akumulasi Volume (IDR)': 'Rp {:,.0f}'
        }), 
        use_container_width=True, 
        hide_index=True
    )

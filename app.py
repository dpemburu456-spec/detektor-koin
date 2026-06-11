def get_indodax_tickers():
    # Coba ambil data real dari Indodax
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get('https://indodax.com/api/tickers', headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('success') == 1 and data.get('tickers'):
                return data['tickers']
    except Exception as e:
        st.warning(f"Gagal ambil data real: {str(e)[:100]}")
    
    # Jika gagal, gunakan mock data (data simulasi)
    st.info("Menggunakan data simulasi (mock) karena API Indodax tidak dapat dijangkau.")
    import random
    mock = {}
    coins = ['btc','eth','xrp','ada','doge','matic','sol','dot','avax','ltc','bnb','link','xlm','trx','eos']
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

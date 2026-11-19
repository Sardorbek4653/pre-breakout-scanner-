
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

from yfinance import EquityQuery

st.set_page_config(
    page_title="US Pre-Breakout Scanner",
    page_icon="📈",
    layout="wide"
)

st.title("📈 US PRE-BREAKOUT SCANNER")
st.caption("NASDAQ + NYSE | Custom Market Cap | Daily")

# =========================
# SIDEBAR SETTINGS
# =========================

st.sidebar.header("Scanner sozlamalari")

# Sector tanlash
sector_options = [
    "Technology",
    "Healthcare",
    "Financial Services",
    "Consumer Cyclical",
    "Consumer Defensive",
    "Industrials",
    "Energy",
    "Basic Materials",
    "Communication Services",
    "Real Estate",
    "Utilities"
]

selected_sectors = st.sidebar.multiselect(
    "Sektor tanlash (bo'sh = barcha sektorlar)",
    options=sector_options,
    default=[]
)

# Custom Market Cap
st.sidebar.subheader("Market Cap ($ Billion)")

min_cap_b = st.sidebar.number_input(
    "Min Market Cap ($B)",
    min_value=0.0,
    value=1.0,
    step=0.5
)

max_cap_b = st.sidebar.number_input(
    "Max Market Cap ($B)",
    min_value=0.0,
    value=500.0,
    step=5.0
)

min_cap = int(min_cap_b * 1_000_000_000)
max_cap = int(max_cap_b * 1_000_000_000)

# Resistance
distance_limit = st.sidebar.slider(
    "Resistance masofasi (%)",
    1.0, 10.0, 5.0
)

# Consolidation
range_limit = st.sidebar.slider(
    "Konsolidatsiya diapazoni (%)",
    3.0, 25.0, 15.0
)

# Scan limit
max_stocks = st.sidebar.selectbox(
    "Tekshiriladigan aksiyalar soni",
    [250, 500, 750, 1000],
    index=1
)

# Trend filter
require_trend = st.sidebar.checkbox(
    "EMA20 > EMA50 sharti",
    False
)

# =========================
# VALIDATION
# =========================

if min_cap_b > max_cap_b:
    st.sidebar.error("Min Market Cap Max qiymatidan katta bo'lishi mumkin emas.")

# =========================
# GET STOCK UNIVERSE
# =========================

def get_universe(limit, min_cap, max_cap):

    query = EquityQuery("and", [
        EquityQuery("eq", ["region", "us"]),
        EquityQuery("gte", ["intradaymarketcap", min_cap]),
        EquityQuery("lte", ["intradaymarketcap", max_cap]),
        EquityQuery("is-in", ["exchange", "NMS", "NYQ"])
    ])

    stocks = []
    offset = 0

    while len(stocks) < limit:

        size = min(250, limit - len(stocks))

        data = yf.screen(
            query,
            offset=offset,
            size=size,
            sortField="intradaymarketcap",
            sortAsc=False
        )

        quotes = data.get("quotes", [])

        if not quotes:
            break

        stocks.extend(quotes)
        offset += len(quotes)

        if len(quotes) < size:
            break

    return stocks[:limit]


# =========================
# GET SECTOR
# =========================

@st.cache_data(ttl=3600, show_spinner=False)
def get_stock_sector(ticker):

    try:
        info = yf.Ticker(ticker).get_info()
        return info.get("sector", "Unknown")
    except Exception:
        return "Unknown"


def filter_by_sector(universe, selected_sectors):

    # Hech qanday sektor tanlanmasa - barcha aksiyalar
    if not selected_sectors:
        return universe

    filtered = []

    for stock in universe:

        ticker = stock.get("symbol")

        if not ticker:
            continue

        sector = get_stock_sector(ticker)

        if sector in selected_sectors:
            filtered.append(stock)

    return filtered


# =========================
# ANALYZE STOCK
# =========================

def analyze(ticker):

    df = yf.Ticker(ticker).history(
        period="6mo",
        interval="1d",
        auto_adjust=True
    )

    if df.empty or len(df) < 55:
        return None, "Ma'lumot yetarli emas"

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    price = float(close.iloc[-1])

    # Resistance
    resistance = high.shift(1).rolling(20).max().iloc[-1]

    if pd.isna(resistance) or resistance <= 0:
        return None, "Resistance aniqlanmadi"

    distance = (resistance - price) / resistance * 100

    # EMA
    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]

    # RSI
    delta = close.diff()

    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    rsi_value = rsi.iloc[-1]

    # Volume
    avg_volume = volume.iloc[-21:-1].mean()

    volume_ratio = (
        volume.iloc[-1] / avg_volume
        if avg_volume > 0 else 0
    )

    # Consolidation range
    range_pct = (
        (high.iloc[-10:].max() - low.iloc[-10:].min())
        / price * 100
    )

    reasons = []

    if distance <= 0:
        reasons.append("Resistance buzilgan")
    elif distance > distance_limit:
        reasons.append("Resistance uzoq")

    if range_pct > range_limit:
        reasons.append("Konsolidatsiya zaif")

    if require_trend and ema20 <= ema50:
        reasons.append("EMA trend mos emas")

    if reasons:
        return None, ", ".join(reasons)

    # =========================
    # SCORE
    # =========================

    score = 0

    if distance <= 2:
        score += 30
    elif distance <= 3:
        score += 25
    else:
        score += 15

    if ema20 > ema50:
        score += 20

    if pd.notna(rsi_value) and 50 <= rsi_value <= 70:
        score += 20

    if volume_ratio >= 1.2:
        score += 15

    if range_pct <= 8:
        score += 15

    # =========================
    # RESULT
    # =========================

    return {
        "Ticker": ticker,
        "Narx": round(price, 2),
        "Resistance": round(float(resistance), 2),
        "Masofa %": round(float(distance), 2),
        "RSI": round(float(rsi_value), 1)
        if pd.notna(rsi_value) else None,
        "Volume x": round(float(volume_ratio), 2),
        "EMA20 > EMA50": "Ha" if ema20 > ema50 else "Yo'q",
        "Range %": round(float(range_pct), 2),
        "Score": score
    }, "Nomzod"


# =========================
# SCANNER BUTTON
# =========================

scan_button = st.button("🚀 AKSIYALARNI SKANERLASH")

if scan_button:

    if min_cap_b > max_cap_b:
        st.error("Min Market Cap Max Market Cap'dan katta!")
        st.stop()

    try:

        with st.spinner("Yahoo Finance aksiyalar ro'yxatini yuklamoqda..."):

            universe = get_universe(
                max_stocks,
                min_cap,
                max_cap
            )

        if not universe:
            st.error(
                "Aksiyalar ro'yxati kelmadi. "
                "Keyinroq qayta urinib ko'ring."
            )
            st.stop()

        st.success(
            f"{len(universe)} ta aksiya Market Cap filtri bo'yicha olindi."
        )

        # Sector filter
        if selected_sectors:

            with st.spinner("Sektorlar tekshirilmoqda..."):

                universe = filter_by_sector(
                    universe,
                    selected_sectors
                )

            st.info(
                f"Sektor filtridan keyin {len(universe)} ta aksiya qoldi."
            )

        if not universe:
            st.warning("Tanlangan sektorda aksiyalar topilmadi.")
            st.stop()

        results = []
        diagnostics = []

        progress = st.progress(0)
        status = st.empty()

        # =========================
        # ANALYSIS LOOP
        # =========================

        for i, stock in enumerate(universe):

            ticker = stock.get("symbol")

            if not ticker:
                continue

            try:

                result, reason = analyze(ticker)

                if result:
                    results.append(result)

                diagnostics.append({
                    "Ticker": ticker,
                    "Holat": reason
                })

            except Exception as e:

                diagnostics.append({
                    "Ticker": ticker,
                    "Holat": "Xatolik: " + str(e)[:100]
                })

            progress.progress((i + 1) / len(universe))

            status.write(
                f"Tekshirilmoqda: {ticker} ({i+1}/{len(universe)})"
            )

        # =========================
        # RESULTS
        # =========================

        st.subheader("🎯 PRE-BREAKOUT NOMZODLARI")

        if results:

            result_df = pd.DataFrame(results)

            result_df = result_df.sort_values(
                "Score",
                ascending=False
            )

            st.success(
                f"{len(results)} ta nomzod topildi."
            )

            st.dataframe(
                result_df,
                use_container_width=True,
                hide_index=True
            )

            st.download_button(
                "📥 Natijalarni CSV yuklab olish",
                result_df.to_csv(index=False),
                "pre_breakout_results.csv",
                "text/csv"
            )

        else:

            st.warning("Mos aksiya topilmadi.")

        # =========================
        # DIAGNOSTICS
        # =========================

        st.subheader("🔎 Tekshiruv diagnostikasi")

        st.dataframe(
            pd.DataFrame(diagnostics),
            use_container_width=True,
            hide_index=True
        )

        st.caption(
            f"Market Cap: ${min_cap_b:g}B – ${max_cap_b:g}B | "
            f"Sektor: {', '.join(selected_sectors) if selected_sectors else 'All Sectors'} | "
            "Yahoo Finance | Daily"
        )

    except Exception as e:

        st.error(
            f"Scanner xatoligi: {str(e)}"
        )
        

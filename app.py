
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import time

from yfinance import EquityQuery

st.set_page_config(
    page_title="US Pre-Breakout Scanner",
    page_icon="📈",
    layout="wide"
)

st.title("📈 US PRE-BREAKOUT SCANNER")
st.caption("NASDAQ + NYSE | Market Cap $10B+ | Daily")

st.sidebar.header("Scanner sozlamalari")

min_cap = 10_000_000_000

distance_limit = st.sidebar.slider(
    "Resistance masofasi (%)", 1.0, 10.0, 5.0
)

range_limit = st.sidebar.slider(
    "Konsolidatsiya diapazoni (%)", 3.0, 25.0, 15.0
)

max_stocks = st.sidebar.selectbox(
    "Tekshiriladigan aksiyalar soni",
    [250, 500, 750, 1000],
    index=1
)

require_trend = st.sidebar.checkbox(
    "EMA20 > EMA50 sharti", False
)

def get_universe(limit):
    query = EquityQuery("and", [
        EquityQuery("eq", ["region", "us"]),
        EquityQuery("gte", ["intradaymarketcap", min_cap]),
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

    resistance = high.shift(1).rolling(20).max().iloc[-1]

    if pd.isna(resistance) or resistance <= 0:
        return None, "Resistance aniqlanmadi"

    distance = (resistance - price) / resistance * 100

    ema20 = close.ewm(span=20).mean().iloc[-1]
    ema50 = close.ewm(span=50).mean().iloc[-1]

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi_value = rsi.iloc[-1]

    avg_volume = volume.iloc[-21:-1].mean()
    volume_ratio = (
        volume.iloc[-1] / avg_volume
        if avg_volume > 0 else 0
    )

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

    score = 0

    if distance <= 2:
        score += 30
    elif distance <= 3:
        score += 25
    else:
        score += 15

    if ema20 > ema50:
        score += 20

    if 50 <= rsi_value <= 70:
        score += 20

    if volume_ratio >= 1.2:
        score += 15

    if range_pct <= 8:
        score += 15

    return {
        "Ticker": ticker,
        "Narx": round(price, 2),
        "Resistance": round(float(resistance), 2),
        "Masofa %": round(distance, 2),
        "RSI": round(float(rsi_value), 1)
        if pd.notna(rsi_value) else None,
        "Volume x": round(float(volume_ratio), 2),
        "EMA20 > EMA50": "Ha" if ema20 > ema50 else "Yo'q",
        "Range %": round(range_pct, 2),
        "Score": score
    }, "Nomzod"


if st.button("🚀 BARCHA $10B+ AKSIYALARNI SKANERLASH"):

    try:
        with st.spinner("Yahoo Finance aksiyalar ro'yxatini yuklamoqda..."):
            universe = get_universe(max_stocks)

        if not universe:
            st.error("Aksiyalar ro'yxati kelmadi. Keyinroq qayta urinib ko'ring.")
            st.stop()

        st.success(
            f"{len(universe)} ta $10B+ aksiya ro'yxati olindi."
        )

        results = []
        diagnostics = []

        progress = st.progress(0)
        status = st.empty()

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

        st.subheader("🎯 PRE-BREAKOUT NOMZODLARI")

        if results:
            result_df = pd.DataFrame(results)
            result_df = result_df.sort_values(
                "Score", ascending=False
            )

            st.success(f"{len(results)} ta nomzod topildi.")

            st.dataframe(
                result_df,
                use_container_width=True
            )

            st.download_button(
                "Natijalarni CSV yuklab olish",
                result_df.to_csv(index=False),
                "pre_breakout_results.csv",
                "text/csv"
            )
        else:
            st.warning("Mos aksiya topilmadi.")

        st.subheader("🔎 Tekshiruv diagnostikasi")
        st.dataframe(
            pd.DataFrame(diagnostics),
            use_container_width=True
        )

        st.caption(
            "Market cap chegarasi: $10 milliard. "
            "Ma'lumotlar Yahoo Finance orqali olinadi."
        )

    except Exception as e:
        st.error(f"Scanner xatoligi: {str(e)}")
    

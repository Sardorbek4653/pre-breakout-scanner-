
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

from yfinance import EquityQuery

st.set_page_config(
    page_title="Professional Breakout Scanner",
    page_icon="📈",
    layout="wide"
)

st.title("🚀 PROFESSIONAL PRE-BREAKOUT SCANNER")
st.caption("USA Stocks | Market Cap $10B+ | Daily")

# SETTINGS
st.sidebar.header("Scanner sozlamalari")

min_cap = 10_000_000_000

distance_limit = st.sidebar.slider(
    "Resistance masofasi %",
    1.0, 10.0, 5.0
)

range_limit = st.sidebar.slider(
    "Konsolidatsiya diapazoni %",
    3.0, 25.0, 15.0
)

max_stocks = st.sidebar.selectbox(
    "Aksiyalar soni",
    [250, 500, 750, 1000],
    index=1
)


# AUTOMATIC STOCK LIST
@st.cache_data(ttl=3600)
def get_universe(limit):

    query = EquityQuery("and", [
        EquityQuery("eq", ["region", "us"]),
        EquityQuery("gte", [
            "intradaymarketcap", min_cap
        ]),
        EquityQuery("is-in", [
            "exchange", "NMS", "NYQ"
        ])
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


# ANALYSIS
def analyze(ticker):

    df = yf.Ticker(ticker).history(
        period="6mo",
        interval="1d",
        auto_adjust=True
    )

    if df.empty or len(df) < 60:
        return None, "Ma'lumot yetarli emas"

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    price = float(close.iloc[-1])

    # RESISTANCE
    resistance = high.shift(1).rolling(20).max().iloc[-1]

    if pd.isna(resistance) or resistance <= 0:
        return None, "Resistance yo'q"

    distance = (resistance - price) / resistance * 100

    # EMA
    ema20 = close.ewm(span=20).mean()
    ema50 = close.ewm(span=50).mean()

    # RSI
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = -delta.clip(upper=0).rolling(14).mean()

    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))

    if loss.iloc[-1] == 0 and gain.iloc[-1] > 0:
        rsi_value = 100.0
    else:
        rsi_value = float(rsi.iloc[-1])

    # VOLUME CONTRACTION
    recent_volume = volume.iloc[-5:].mean()
    previous_volume = volume.iloc[-25:-5].mean()

    volume_ratio = (
        recent_volume / previous_volume
        if previous_volume > 0 else np.nan
    )

    # ATR CONTRACTION
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)

    atr_pct = tr.rolling(14).mean() / close * 100

    recent_atr = atr_pct.iloc[-5:].mean()
    previous_atr = atr_pct.iloc[-25:-5].mean()

    atr_ratio = (
        recent_atr / previous_atr
        if previous_atr > 0 else np.nan
    )

    # RESISTANCE TOUCHES
    recent_highs = high.iloc[-60:-1]

    touches = int((
        (recent_highs >= resistance * 0.985) &
        (recent_highs <= resistance * 1.015)
    ).sum())

    # CONSOLIDATION
    range_pct = (
        (high.iloc[-10:].max() -
         low.iloc[-10:].min()) / price
    ) * 100

    # FILTER
    if distance <= 0:
        return None, "Resistance buzilgan"

    if distance > distance_limit:
        return None, "Resistance uzoq"

    if range_pct > range_limit:
        return None, "Konsolidatsiya yo'q"

    # SCORE 0-100
    score = 0

    if distance <= 2:
        score += 20
    elif distance <= 3:
        score += 15
    else:
        score += 10

    if touches >= 3:
        score += 20
    elif touches == 2:
        score += 10

    if pd.notna(volume_ratio):
        if volume_ratio <= 0.80:
            score += 20
        elif volume_ratio <= 1.0:
            score += 10

    if pd.notna(atr_ratio):
        if atr_ratio <= 0.85:
            score += 20
        elif atr_ratio <= 1.0:
            score += 10

    if ema20.iloc[-1] > ema50.iloc[-1]:
        score += 10

    if pd.notna(rsi_value) and 50 <= rsi_value <= 70:
        score += 10

    result = {
        "Ticker": ticker,
        "Narx": round(price, 2),
        "Resistance": round(float(resistance), 2),
        "Masofa %": round(distance, 2),
        "Touches": touches,
        "Volume Ratio": round(float(volume_ratio), 2)
        if pd.notna(volume_ratio) else None,
        "ATR Ratio": round(float(atr_ratio), 2)
        if pd.notna(atr_ratio) else None,
        "RSI": round(rsi_value, 1),
        "EMA Trend": "Bullish"
        if ema20.iloc[-1] > ema50.iloc[-1]
        else "Bearish",
        "Score": score
    }

    return result, "Nomzod"


# CHART
def show_chart(ticker):

    df = yf.Ticker(ticker).history(
        period="6mo",
        interval="1d",
        auto_adjust=True
    )

    if df.empty:
        st.error("Grafik ma'lumotlari topilmadi.")
        return

    df["EMA20"] = df["Close"].ewm(span=20).mean()
    df["EMA50"] = df["Close"].ewm(span=50).mean()

    resistance = df["High"].shift(1).rolling(20).max().iloc[-1]

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"],
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        name="Price"
    ))

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["EMA20"],
        name="EMA20",
        line=dict(width=1.5)
    ))

    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["EMA50"],
        name="EMA50",
        line=dict(width=1.5)
    ))

    fig.add_hline(
        y=resistance,
        line_dash="dash",
        annotation_text="Resistance"
    )

    fig.update_layout(
        height=550,
        xaxis_rangeslider_visible=False,
        template="plotly_dark",
        title=f"{ticker} - Daily Chart"
    )

    st.plotly_chart(fig, use_container_width=True)


# MAIN SCANNER
if st.button("🚀 SKANERLASH"):

    try:

        with st.spinner("AQSh aksiyalari yuklanmoqda..."):
            universe = get_universe(max_stocks)

        if not universe:
            st.error("Aksiyalar ro'yxati kelmadi.")
            st.stop()

        results = []
        errors = []

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
                elif "XATOLIK" in reason:
                    errors.append({
                        "Ticker": ticker,
                        "Sabab": reason
                    })

            except Exception as e:
                errors.append({
                    "Ticker": ticker,
                    "Sabab": str(e)[:100]
                })

            progress.progress((i + 1) / len(universe))

            status.write(
                f"Tekshirilmoqda: {ticker} "
                f"({i+1}/{len(universe)})"
            )

        st.session_state["results"] = results

        if errors:
            st.session_state["errors"] = errors

    except Exception as e:
        st.error(f"Scanner xatosi: {e}")


# RESULTS
if "results" in st.session_state:

    results = st.session_state["results"]

    st.subheader("🎯 PRE-BREAKOUT NOMZODLARI")

    if results:

        result_df = pd.DataFrame(results)

        result_df = result_df.sort_values(
            "Score", ascending=False
        )

        st.success(
            f"{len(results)} ta nomzod topildi."
        )

        st.dataframe(
            result_df,
            use_container_width=True
        )

        st.download_button(
            "CSV yuklab olish",
            result_df.to_csv(index=False),
            "breakout_scanner.csv",
            "text/csv"
        )

        st.subheader("📊 Aksiya grafigi")

        selected = st.selectbox(
            "Grafik ko'rish uchun aksiyani tanlang",
            result_df["Ticker"].tolist()
        )

        show_chart(selected)

    else:
        st.warning("Nomzod topilmadi.")

    if st.session_state.get("errors"):
        with st.expander("Xatoliklar"):
            st.dataframe(
                pd.DataFrame(st.session_state["errors"])
            )

    st.caption(
        "Score — texnik saralash balli, "
        "praboy ehtimolining foizi emas."
    )
    

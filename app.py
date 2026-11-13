
import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Pre-Breakout Scanner",
    page_icon="📈",
    layout="wide"
)

st.title("📈 US Pre-Breakout Scanner")
st.write("AQSh aksiyalarida praboydan oldingi zonalarni topish")

tickers_text = st.text_area(
    "Aksiya tickerlari",
    "MU, NVDA, AMD, MRVL, TER, FORM, QCOM, INTC"
)

distance = st.slider(
    "Resistance gacha masofa (%)",
    1.0, 10.0, 3.0
)

if st.button("Skanerlash"):
    tickers = [
        x.strip().upper()
        for x in tickers_text.replace("\n", ",").split(",")
        if x.strip()
    ]

    results = []

    progress = st.progress(0)

    for i, ticker in enumerate(tickers):
        try:
            df = yf.Ticker(ticker).history(
                period="6mo",
                interval="1d"
            )

            if len(df) < 55:
                continue

            close = df["Close"]
            high = df["High"]
            low = df["Low"]
            volume = df["Volume"]

            price = close.iloc[-1]
            ema20 = close.ewm(span=20).mean().iloc[-1]
            ema50 = close.ewm(span=50).mean().iloc[-1]

            resistance = high.shift(1).rolling(20).max().iloc[-1]

            delta = close.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = -delta.clip(upper=0).rolling(14).mean()

            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            rsi_value = rsi.iloc[-1]

            avg_volume = volume.iloc[-21:-1].mean()
            volume_ratio = volume.iloc[-1] / avg_volume if avg_volume > 0 else 0

            distance_pct = (resistance - price) / resistance * 100

            range_pct = (
                (high.iloc[-10:].max() - low.iloc[-10:].min())
                / price * 100
            )

            if (
                0 < distance_pct <= distance
                and ema20 > ema50
                and range_pct <= 12
                and pd.notna(rsi_value)
            ):
                results.append({
                    "Ticker": ticker,
                    "Narx": round(price, 2),
                    "Resistance": round(resistance, 2),
                    "Masofa %": round(distance_pct, 2),
                    "RSI": round(rsi_value, 1),
                    "Volume x": round(volume_ratio, 2),
                    "EMA20 > EMA50": "Ha"
                })

        except Exception:
            pass

        progress.progress((i + 1) / len(tickers))

    st.subheader("Natijalar")

    if results:
        result_df = pd.DataFrame(results)
        result_df = result_df.sort_values("Masofa %")
        st.dataframe(result_df, use_container_width=True)
    else:
        st.warning("Mos aksiya topilmadi.")
      

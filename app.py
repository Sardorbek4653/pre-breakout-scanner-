
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
st.caption("1D | AQSh aksiyalari | Breakout oldi zonalari")

tickers_text = st.text_area(
    "Aksiya tickerlari",
    "MU, NVDA, AMD, MRVL, TER, FORM, QCOM, INTC"
)

distance_limit = st.slider(
    "Resistance gacha masofa (%)",
    1.0, 10.0, 5.0
)

range_limit = st.slider(
    "10 kunlik narx diapazoni (%)",
    3.0, 25.0, 15.0
)

require_trend = st.checkbox(
    "EMA20 > EMA50 shartini talab qilish",
    value=False
)

if st.button("🔍 SKANERLASH"):
    tickers = list(dict.fromkeys([
        x.strip().upper()
        for x in tickers_text.replace("\n", ",").split(",")
        if x.strip()
    ]))

    results = []
    diagnostics = []

    progress = st.progress(0)

    for i, ticker in enumerate(tickers):

        try:
            df = yf.Ticker(ticker).history(
                period="6mo",
                interval="1d",
                auto_adjust=True
            )

            if df.empty or len(df) < 55:
                diagnostics.append({
                    "Ticker": ticker,
                    "Holat": "Ma'lumot yetarli emas",
                    "Masofa %": None,
                    "Sabab": "55 kunlik ma'lumot yo'q"
                })
                continue

            close = df["Close"]
            high = df["High"]
            low = df["Low"]
            volume = df["Volume"]

            price = float(close.iloc[-1])

            ema20 = close.ewm(span=20).mean().iloc[-1]
            ema50 = close.ewm(span=50).mean().iloc[-1]

            resistance = high.shift(1).rolling(20).max().iloc[-1]

            if pd.isna(resistance) or resistance <= 0:
                continue

            distance = (
                (resistance - price) / resistance
            ) * 100

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
                (high.iloc[-10:].max() -
                 low.iloc[-10:].min()) / price
            ) * 100

            reasons = []

            if distance <= 0:
                reasons.append("Resistance buzilgan yoki narx undan yuqori")

            elif distance > distance_limit:
                reasons.append("Resistance juda uzoq")

            if range_pct > range_limit:
                reasons.append("Narx konsolidatsiyasi yetarli emas")

            if require_trend and ema20 <= ema50:
                reasons.append("EMA trend sharti bajarilmadi")

            if reasons:
                status = "Mos emas"
            else:
                status = "PRE-BREAKOUT NOMZODI"

                results.append({
                    "Ticker": ticker,
                    "Narx": round(price, 2),
                    "Resistance": round(float(resistance), 2),
                    "Masofa %": round(distance, 2),
                    "RSI": round(float(rsi_value), 1)
                    if pd.notna(rsi_value) else None,
                    "Volume x": round(float(volume_ratio), 2),
                    "EMA20 > EMA50": "Ha" if ema20 > ema50 else "Yo'q",
                    "Range %": round(float(range_pct), 2)
                })

            diagnostics.append({
                "Ticker": ticker,
                "Holat": status,
                "Masofa %": round(distance, 2),
                "Sabab": "; ".join(reasons) if reasons else "Barcha filtrdan o'tdi"
            })

        except Exception as e:
            diagnostics.append({
                "Ticker": ticker,
                "Holat": "XATOLIK",
                "Masofa %": None,
                "Sabab": str(e)[:150]
            })

        progress.progress((i + 1) / len(tickers))

    st.subheader("🎯 PRE-BREAKOUT NOMZODLARI")

    if results:
        result_df = pd.DataFrame(results)
        result_df = result_df.sort_values("Masofa %")
        st.success(f"{len(results)} ta nomzod topildi!")
        st.dataframe(result_df, use_container_width=True)
    else:
        st.warning("Hozircha mos aksiya topilmadi.")

    st.subheader("🔎 Barcha aksiyalar diagnostikasi")

    if diagnostics:
        st.dataframe(
            pd.DataFrame(diagnostics),
            use_container_width=True
        )
        

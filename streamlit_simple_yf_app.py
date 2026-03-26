# streamlit_simple_yf_app.py
import streamlit as st
import pandas as pd
import altair as alt
from simple_collar_backtest_yf import BacktestInput, run_backtest

st.set_page_config(page_title="Simple Collar Backtest (Yahoo Finance)", layout="wide")
st.title("🌐 Simple Annual Collar Backtest — Yahoo Finance")
st.caption("Uses Yahoo Finance Adj Close for annual total returns. European-style collar: clip each year's return to [floor, cap]. No option pricing. Not financial advice.")

with st.sidebar:
    st.header("Inputs")
    ticker = st.text_input("Ticker (ETF/Index/Stock; e.g., SPY, ^GSPC)", "SPY")

    # Floor and cap as percentages (converted to decimals internally)
    floor_pct = st.number_input("Floor (%)", value=-2.0, step=0.5, format="%.1f")
    cap_pct   = st.number_input("Cap (%)", value=11.0, step=0.5, format="%.1f")
    floor = floor_pct / 100.0
    cap   = cap_pct / 100.0

    # Default start year set to 1990
    start_year = st.number_input("Start Year", value=1990, step=1)
    start_year_val = int(start_year) if start_year > 0 else None

    initial_value = st.number_input("Initial Portfolio ($)", value=100000, step=1000)

    run = st.button("▶️ Run", use_container_width=True)

if run:
    try:
        df = run_backtest(BacktestInput(
            ticker=ticker,
            floor=float(floor),
            cap=float(cap),
            start_year=start_year_val,
            initial_value=float(initial_value),
        ))
    except Exception as e:
        st.error(f"Backtest failed: {e}")
        st.stop()

    if df.empty:
        st.warning("No results produced for the chosen inputs.")
    else:
        # Quick summary under charts
        st.info(f"Ending values — Market: ${df['market_value'].iloc[-1]:,.0f} | Collar: ${df['collar_value'].iloc[-1]:,.0f}")

        tab_charts, tab_table = st.tabs(["📈 Charts", "📋 Table"])

        with tab_charts:
            # Build a long-form frame for Altair lines (cumulative portfolio values)
            long_vals = df.melt(
                id_vars=["year"],
                value_vars=["market_value", "collar_value"],
                var_name="Series",
                value_name="Value"
            )
            long_vals["Series"] = long_vals["Series"].map({
                "market_value": "Market (Adj Close TR)",
                "collar_value": "Collar (clipped)"
            })

            st.subheader("Cumulative Portfolio Value ($)")
            line_chart = (
                alt.Chart(long_vals)
                .mark_line(point=True)
                .encode(
                    x=alt.X("year:O", title="Year"),
                    y=alt.Y("Value:Q", title="Portfolio Value ($)", scale=alt.Scale(zero=False)),
                    color=alt.Color("Series:N", title=""),
                    tooltip=[
                        alt.Tooltip("year:O", title="Year"),
                        alt.Tooltip("Series:N", title=""),
                        alt.Tooltip("Value:Q", title="Value ($)", format=",.0f"),
                    ],
                )
                .properties(height=380)
                .interactive()
            )
            st.altair_chart(line_chart, use_container_width=True)

            # Annual returns comparison
            ret_long = df.melt(
                id_vars=["year"],
                value_vars=["market_ret", "collar_ret"],
                var_name="Series",
                value_name="Return"
            )
            ret_long["Series"] = ret_long["Series"].map({
                "market_ret": "Market (Adj Close TR)",
                "collar_ret": "Collar (clipped)"
            })
            st.subheader("Annual Returns (%)")
            bar_chart = (
                alt.Chart(ret_long)
                .mark_bar()
                .encode(
                    x=alt.X("year:O", title="Year"),
                    y=alt.Y("Return:Q", title="Annual Return", axis=alt.Axis(format="%")),
                    color=alt.Color("Series:N", title=""),
                    tooltip=[
                        alt.Tooltip("year:O", title="Year"),
                        alt.Tooltip("Series:N", title=""),
                        alt.Tooltip("Return:Q", title="Return", format=".2%"),
                    ],
                )
                .properties(height=380)
                .interactive()
            )
            st.altair_chart(bar_chart, use_container_width=True)

            # Quick summary under charts
            st.info(f"Ending values — Market: ${df['market_value'].iloc[-1]:,.0f} | Collar: ${df['collar_value'].iloc[-1]:,.0f}")

        with tab_table:
            st.subheader("Results Table")
            st.dataframe(
                df.style.format({
                    "market_ret": "{:.2%}",
                    "collar_ret": "{:.2%}",
                    "market_value": "${:,.0f}",
                    "collar_value": "${:,.0f}",
                }),
                use_container_width=True
            )

            # Download button with the table
            st.download_button(
                "Download results (CSV)",
                df.to_csv(index=False).encode("utf-8"),
                file_name=f"{ticker}_yf_simple_collar_results.csv",
                mime="text/csv",
                use_container_width=True
            )

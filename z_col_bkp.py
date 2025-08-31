
# import streamlit as st
# import pandas as pd
# import numpy as np
# from datetime import datetime
# import secrets
# from dateutil.relativedelta import relativedelta

# # ========================= Helpers =========================

# def round_to_strike(x: float, step: int = 5) -> int:
#     return int(round(float(x) / step) * step)

# # Common index aliases: use one symbol for price, another for options
# ALIAS = {
#     "SPX": ("^GSPC", "SPY"),
#     "NDX": ("^NDX", "QQQ"),
#     "RUT": ("^RUT", "IWM"),
#     "DJI": ("^DJI", "DIA"),
# }

# def compute_rows(
#     ticker: str,
#     price: float,
#     dividend_pct: float,
#     put_quotes: dict[int | float, float],
#     call_quotes: dict[int | float, float],
#     put_strikes: list[int | float],
#     call_strikes: list[int | float],
# ) -> pd.DataFrame:
#     rows = []
#     for kp in sorted(put_strikes):
#         ppx = put_quotes.get(kp)
#         if ppx is None or not np.isfinite(ppx):
#             continue
#         for kc in sorted(call_strikes):
#             if kp > kc:
#                 continue
#             cpx = call_quotes.get(kc)
#             if cpx is None or not np.isfinite(cpx):
#                 continue
#             # New sign convention: positive net = credit (call premium received minus put premium paid)
#             net = round(cpx - ppx, 2)
#             net_pct = 100.0 * net / price
#             downside_pct = 100.0 * (kp / price - 1.0)
#             # Effective downside = intrinsic downside + net premium % (credit reduces downside; debit increases it)
#             eff_down_pct = downside_pct + net_pct
#             upside_pct = 100.0 * (kc / price - 1.0)
#             dividend_rep = float(dividend_pct)
#             up_div_pct = upside_pct + dividend_rep
#             net_band_pct = up_div_pct + eff_down_pct
#             rows.append({
#                 "Ticker": ticker.upper(),
#                 "Price $": round(price, 2),
#                 "Put": float(kp),
#                 "Put $": round(ppx, 2),
#                 "Call": float(kc),
#                 "Call $": round(cpx, 2),
#                 "Net Premium $": net,
#                 "Net Premium %": round(net_pct, 2),
#                 "Downside %": round(downside_pct, 2),
#                 "Effective Downside %": round(eff_down_pct, 2),
#                 "Upside %": round(upside_pct, 2),
#                 "Dividend %": round(dividend_rep, 2),
#                 "Upside + Dividend %": round(up_div_pct, 2),
#                 "Net Band %": round(net_band_pct, 2),
#             })
#     df = pd.DataFrame(rows)
#     if not df.empty:
#         cols = [
#             "Ticker","Price $","Put","Put $","Call","Call $",
#             "Net Premium $","Net Premium %","Downside %","Effective Downside %",
#             "Upside %","Dividend %","Upside + Dividend %","Net Band %",
#         ]
#         df = df[cols].sort_values(["Put", "Call"]).reset_index(drop=True)
#     return df

# def fetch_ttm_dividend_yield(symbol: str, fallback_symbol: str | None, price: float) -> tuple[float, str]:
#     try:
#         import yfinance as yf
#     except Exception:
#         return 0.0, "yfinance not installed — dividend set to 0%"

#     def _ttm(sym: str) -> float | None:
#         try:
#             t = yf.Ticker(sym)
#             div = t.dividends
#             if div is None or div.empty:
#                 return None
#             cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=365)
#             ttm = float(div[div.index >= cutoff].sum())
#             if price and price > 0:
#                 return 100.0 * ttm / float(price)
#         except Exception:
#             return None
#         return None

#     y1 = _ttm(symbol)
#     if y1 is not None and np.isfinite(y1):
#         return y1, f"Dividend from {symbol}"

#     if fallback_symbol:
#         y2 = _ttm(fallback_symbol)
#         if y2 is not None and np.isfinite(y2):
#             return y2, f"Dividend from {fallback_symbol}"

#     return 0.0, "No dividend series found; using 0%"

# # ========================= UI =========================

# st.set_page_config(page_title="Simple Collar Builder", layout="wide")
# st.title("Simple Option Collar Builder")
# st.caption("Inputs at the top; results below. Uses Yahoo Finance for price & option chains. Handles index aliases (SPX→SPY, NDX→QQQ, RUT→IWM, DJI→DIA). Dividend % auto-fetched (TTM) by default.")

# st.subheader("Inputs")
# with st.form("inputs_form", clear_on_submit=False):
#     c1, c2, c3, c4, c5 = st.columns(5)
#     with c1:
#         base_ticker = st.text_input("Base Ticker", value="SPY").strip().upper()
#         expiry_input = st.date_input("Expiry Date", value=datetime(2026, 9, 18)).strftime("%Y-%m-%d")
#     default_price_sym, default_opt_sym = ALIAS.get(base_ticker, (base_ticker, base_ticker))
#     with c2:
#         price_symbol = st.text_input("Price Symbol (for price)", value=default_price_sym).strip()
#         strike_step = st.number_input("Strike Step ($)", value=5, step=1)
#     with c3:
#         put_start_pct = st.number_input("Put start (% below ATM)", value=5.0, step=0.5)
#         put_end_pct = st.number_input("Put end (% above ATM)", value=5.0, step=0.5)
#     with c4:
#         call_end_pct = st.number_input("Call end (% above ATM)", value=15.0, step=0.5)
#         st.write("")
#     with c5:
#         auto_div = st.checkbox("Auto dividend % (TTM)", value=True)
#         manual_div = st.number_input("Manual Dividend %", value=1.10, step=0.05, disabled=auto_div)

#     b1, b2, b3, b4, b5 = st.columns(5)
#     with b1:
#         if "_build_btn_uid" not in st.session_state:
#             st.session_state["_build_btn_uid"] = secrets.token_hex(8)
#         run_btn = st.form_submit_button("Build Table", key=f"build_table_btn_{st.session_state['_build_btn_uid']}")

# if run_btn:
#     try:
#         import yfinance as yf
#         YF_AVAILABLE = True
#     except Exception:
#         YF_AVAILABLE = False

#     if not YF_AVAILABLE:
#         st.error("yfinance is not installed. Please `pip install yfinance` and rerun.")
#     else:
#         try:
#             default_price_sym, default_opt_sym = ALIAS.get(base_ticker, (price_symbol, price_symbol))
#             options_symbol = default_opt_sym if base_ticker in ALIAS else price_symbol

#             t_price = yf.Ticker(price_symbol)
#             hist = t_price.history(period="1d")
#             if hist.empty:
#                 raise RuntimeError(f"No price history for '{price_symbol}'.")
#             price = float(hist["Close"].iloc[-1])

#             long_name = None
#             try:
#                 info = t_price.get_info() if hasattr(t_price, "get_info") else t_price.info
#                 if isinstance(info, dict):
#                     long_name = info.get("longName") or info.get("shortName")
#             except Exception:
#                 long_name = None

#             if auto_div:
#                 div_pct, _ = fetch_ttm_dividend_yield(symbol=price_symbol, fallback_symbol=options_symbol, price=price)
#             else:
#                 div_pct, _ = float(manual_div), "Manual dividend %"

#             t_opt = yf.Ticker(options_symbol)
#             all_expiries = t_opt.options or []
#             if not all_expiries:
#                 raise RuntimeError(f"No option expiries for '{options_symbol}'.")

#             wanted = expiry_input
#             if wanted not in all_expiries:
#                 try:
#                     target = datetime.strptime(wanted, "%Y-%m-%d").date()
#                     chosen = min(all_expiries, key=lambda s: abs((datetime.strptime(s, "%Y-%m-%d").date() - target).days))
#                 except Exception:
#                     chosen = all_expiries[0]
#             else:
#                 chosen = wanted

#             expiry_date = datetime.strptime(chosen, "%Y-%m-%d").date()
#             delta = relativedelta(expiry_date, datetime.today().date())
#             months_out = delta.months + 12 * delta.years

#             st.markdown(f"**{long_name or base_ticker}** | Expiry: **{chosen}** ({months_out} months out)")

#             m1, m2, m3 = st.columns(3)
#             with m1:
#                 st.metric("Pricing Ticker", price_symbol)
#             with m2:
#                 st.metric("Last Price", f"${price:,.2f}")
#             with m3:
#                 st.metric("Dividend % (TTM)", f"{div_pct:.2f}%")

#             put_start = round_to_strike(price * (1 - float(put_start_pct) / 100.0), int(strike_step))
#             put_end   = round_to_strike(price * (1 + float(put_end_pct) / 100.0), int(strike_step))
#             call_end  = round_to_strike(price * (1 + float(call_end_pct) / 100.0), int(strike_step))
#             atm = round_to_strike(price, int(strike_step))
#             desired_puts  = list(range(put_start, put_end + int(strike_step), int(strike_step)))
#             desired_calls = list(range(atm, call_end + int(strike_step), int(strike_step)))

#             chain = t_opt.option_chain(chosen)
#             calls_df = chain.calls[["strike", "lastPrice", "bid", "ask"]].copy()
#             puts_df  = chain.puts [["strike", "lastPrice", "bid", "ask"]].copy()
#             calls_df["mid"] = (calls_df["bid"].fillna(0) + calls_df["ask"].fillna(0)).replace(0, np.nan) / 2
#             puts_df ["mid"] = (puts_df ["bid"].fillna(0) + puts_df ["ask"].fillna(0)).replace(0, np.nan) / 2
#             calls_df["q"] = calls_df["mid"].fillna(calls_df["lastPrice"]).astype(float)
#             puts_df ["q"] = puts_df ["mid"] .fillna(puts_df ["lastPrice"]).astype(float)

#             step = int(strike_step)
#             calls_df["strike_key"] = calls_df["strike"].apply(lambda s: round_to_strike(s, step)).astype(int)
#             puts_df ["strike_key"] = puts_df ["strike"].apply(lambda s: round_to_strike(s, step)).astype(int)
#             call_map = calls_df.drop_duplicates("strike_key").set_index("strike_key")["q"].to_dict()
#             put_map  = puts_df .drop_duplicates("strike_key").set_index("strike_key")["q"].to_dict()

#             call_quotes = {k: float(call_map.get(k, np.nan)) for k in desired_calls}
#             put_quotes  = {k: float(put_map .get(k, np.nan)) for k in desired_puts }

#             df = compute_rows(
#                 ticker=base_ticker,
#                 price=price,
#                 dividend_pct=float(div_pct),
#                 put_quotes=put_quotes,
#                 call_quotes=call_quotes,
#                 put_strikes=desired_puts,
#                 call_strikes=desired_calls,
#             )

#             st.subheader("Results")
#             if df.empty:
#                 st.warning("No rows produced. Try adjusting % bands or step, or pick a different options proxy.")
#             else:
#                 st.dataframe(df, use_container_width=True)
#                 csv = df.to_csv(index=False).encode("utf-8")
#                 st.download_button("Download CSV", data=csv, file_name=f"{base_ticker}_collars_{chosen}.csv", mime="text/csv")

#         except Exception as e:
#             st.error(f"Error: {e}")

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import secrets
from dateutil.relativedelta import relativedelta

# ========================= Helpers =========================

def round_to_strike(x: float, step: int = 5) -> int:
    return int(round(float(x) / step) * step)

# Common index aliases: use one symbol for price, another for options
ALIAS = {
    "SPX": ("^GSPC", "SPY"),
    "NDX": ("^NDX", "QQQ"),
    "RUT": ("^RUT", "IWM"),
    "DJI": ("^DJI", "DIA"),
}

def compute_rows(
    ticker: str,
    price: float,
    dividend_pct: float,
    put_quotes: dict[int | float, float],
    call_quotes: dict[int | float, float],
    put_strikes: list[int | float],
    call_strikes: list[int | float],
) -> pd.DataFrame:
    rows = []
    for kp in sorted(put_strikes):
        ppx = put_quotes.get(kp)
        if ppx is None or not np.isfinite(ppx):
            continue
        for kc in sorted(call_strikes):
            if kp > kc:
                continue
            cpx = call_quotes.get(kc)
            if cpx is None or not np.isfinite(cpx):
                continue
            # New sign convention: positive net = credit (call premium received minus put premium paid)
            net = round(cpx - ppx, 2)
            net_pct = 100.0 * net / price
            downside_pct = 100.0 * (kp / price - 1.0)
            # Effective downside = intrinsic downside + net premium % (credit reduces downside; debit increases it)
            eff_down_pct = downside_pct + net_pct
            upside_pct = 100.0 * (kc / price - 1.0)
            dividend_rep = float(dividend_pct)
            up_div_pct = upside_pct + dividend_rep
            net_band_pct = up_div_pct + eff_down_pct
            rows.append({
                "Ticker": ticker.upper(),
                "Price $": round(price, 2),
                "Put": float(kp),
                "Put $": round(ppx, 2),
                "Call": float(kc),
                "Call $": round(cpx, 2),
                "Net Premium $": net,
                "Net Premium %": round(net_pct, 2),
                "Downside %": round(downside_pct, 2),
                "Effective Downside %": round(eff_down_pct, 2),
                "Upside %": round(upside_pct, 2),
                "Dividend %": round(dividend_rep, 2),
                "Upside + Dividend %": round(up_div_pct, 2),
                "Net Band %": round(net_band_pct, 2),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        cols = [
            "Ticker","Price $","Put","Put $","Call","Call $",
            "Net Premium $","Net Premium %","Downside %","Effective Downside %",
            "Upside %","Dividend %","Upside + Dividend %","Net Band %",
        ]
        df = df[cols].sort_values(["Put", "Call"]).reset_index(drop=True)
    return df

def fetch_ttm_dividend_yield(symbol: str, fallback_symbol: str | None, price: float) -> tuple[float, str]:
    try:
        import yfinance as yf
    except Exception:
        return 0.0, "yfinance not installed — dividend set to 0%"

    def _ttm(sym: str) -> float | None:
        try:
            t = yf.Ticker(sym)
            div = t.dividends
            if div is None or div.empty:
                return None
            cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=365)
            ttm = float(div[div.index >= cutoff].sum())
            if price and price > 0:
                return 100.0 * ttm / float(price)
        except Exception:
            return None
        return None

    y1 = _ttm(symbol)
    if y1 is not None and np.isfinite(y1):
        return y1, f"Dividend from {symbol}"

    if fallback_symbol:
        y2 = _ttm(fallback_symbol)
        if y2 is not None and np.isfinite(y2):
            return y2, f"Dividend from {fallback_symbol}"

    return 0.0, "No dividend series found; using 0%"

# ========================= UI =========================

st.set_page_config(page_title="Simple Collar Builder", layout="wide")
# Global UI scale (approx. like browser zoom 90%)
st.markdown(
    """
    <style>
      /* Works in most browsers (Chrome/Edge/Firefox); Safari may ignore zoom */
      html { zoom: 0.90; }

      /* Fallback for Safari: scale the body and compensate width */
      @supports not (zoom: 1) {
        body { transform: scale(0.90); transform-origin: 0 0; width: 111.11%; }
      }

      /* Slightly tighten paddings on inputs and metrics */
      .stTextInput>div>div>input,
      .stNumberInput>div>div>input,
      .stDateInput>div>div>input { padding: 0.25rem 0.5rem; }
      .stMetric { padding-top: 0.25rem; padding-bottom: 0.25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    """
    <style>
        /* Reduce whitespace at the very top of the page */
        .block-container {
            padding-top: 1rem;   /* default is ~6rem */
            padding-bottom: 1rem;
        }
    </style>
    """,
    unsafe_allow_html=True
)

st.title("Simple Option Collar Builder")
st.caption("Inputs at the top; results below. Uses Yahoo Finance for price & option chains. Handles index aliases (SPX→SPY, NDX→QQQ, RUT→IWM, DJI→DIA). Dividend % auto-fetched (TTM) by default.")

st.subheader("Inputs")
with st.form("inputs_form", clear_on_submit=False):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        base_ticker = st.text_input("Base Ticker", value="SPY").strip().upper()
        expiry_input = st.date_input("Expiry Date", value=datetime(2026, 9, 18)).strftime("%Y-%m-%d")
    default_price_sym, default_opt_sym = ALIAS.get(base_ticker, (base_ticker, base_ticker))
    with c2:
        price_symbol = st.text_input("Price Symbol (for price)", value=default_price_sym).strip()
        strike_step = st.number_input("Strike Step ($)", value=5, step=1)
    with c3:
        put_start_pct = st.number_input("Put start (% below ATM)", value=5.0, step=0.5)
        put_end_pct = st.number_input("Put end (% above ATM)", value=5.0, step=0.5)
    with c4:
        call_end_pct = st.number_input("Call end (% above ATM)", value=15.0, step=0.5)
        st.write("")
    with c5:
        auto_div = st.checkbox("Auto dividend % (TTM)", value=True)
        manual_div = st.number_input("Manual Dividend %", value=1.10, step=0.05, disabled=auto_div)

    b1, b2, b3, b4, b5 = st.columns(5)
    with b1:
        if "_build_btn_uid" not in st.session_state:
            st.session_state["_build_btn_uid"] = secrets.token_hex(8)
        run_btn = st.form_submit_button("Build Table", key=f"build_table_btn_{st.session_state['_build_btn_uid']}")

if run_btn:
    try:
        import yfinance as yf
        YF_AVAILABLE = True
    except Exception:
        YF_AVAILABLE = False

    if not YF_AVAILABLE:
        st.error("yfinance is not installed. Please `pip install yfinance` and rerun.")
    else:
        try:
            default_price_sym, default_opt_sym = ALIAS.get(base_ticker, (price_symbol, price_symbol))
            options_symbol = default_opt_sym if base_ticker in ALIAS else price_symbol

            t_price = yf.Ticker(price_symbol)
            hist = t_price.history(period="1d")
            if hist.empty:
                raise RuntimeError(f"No price history for '{price_symbol}'.")
            price = float(hist["Close"].iloc[-1])

            long_name = None
            try:
                info = t_price.get_info() if hasattr(t_price, "get_info") else t_price.info
                if isinstance(info, dict):
                    long_name = info.get("longName") or info.get("shortName")
            except Exception:
                long_name = None

            if auto_div:
                div_pct, _ = fetch_ttm_dividend_yield(symbol=price_symbol, fallback_symbol=options_symbol, price=price)
            else:
                div_pct, _ = float(manual_div), "Manual dividend %"

            t_opt = yf.Ticker(options_symbol)
            all_expiries = t_opt.options or []
            if not all_expiries:
                raise RuntimeError(f"No option expiries for '{options_symbol}'.")

            wanted = expiry_input
            if wanted not in all_expiries:
                try:
                    target = datetime.strptime(wanted, "%Y-%m-%d").date()
                    chosen = min(all_expiries, key=lambda s: abs((datetime.strptime(s, "%Y-%m-%d").date() - target).days))
                except Exception:
                    chosen = all_expiries[0]
            else:
                chosen = wanted

            expiry_date = datetime.strptime(chosen, "%Y-%m-%d").date()
            delta = relativedelta(expiry_date, datetime.today().date())
            months_out = delta.months + 12 * delta.years

            st.markdown(f"**{long_name or base_ticker}** | Expiry: **{chosen}** ({months_out} months out)")

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Pricing Ticker", price_symbol)
            with m2:
                st.metric("Last Price", f"${price:,.2f}")
            with m3:
                st.metric("Dividend % (TTM)", f"{div_pct:.2f}%")

            put_start = round_to_strike(price * (1 - float(put_start_pct) / 100.0), int(strike_step))
            put_end   = round_to_strike(price * (1 + float(put_end_pct) / 100.0), int(strike_step))
            call_end  = round_to_strike(price * (1 + float(call_end_pct) / 100.0), int(strike_step))
            atm = round_to_strike(price, int(strike_step))
            desired_puts  = list(range(put_start, put_end + int(strike_step), int(strike_step)))
            desired_calls = list(range(atm, call_end + int(strike_step), int(strike_step)))

            chain = t_opt.option_chain(chosen)
            calls_df = chain.calls[["strike", "lastPrice", "bid", "ask"]].copy()
            puts_df  = chain.puts [["strike", "lastPrice", "bid", "ask"]].copy()
            calls_df["mid"] = (calls_df["bid"].fillna(0) + calls_df["ask"].fillna(0)).replace(0, np.nan) / 2
            puts_df ["mid"] = (puts_df ["bid"].fillna(0) + puts_df ["ask"].fillna(0)).replace(0, np.nan) / 2
            calls_df["q"] = calls_df["mid"].fillna(calls_df["lastPrice"]).astype(float)
            puts_df ["q"] = puts_df ["mid"] .fillna(puts_df ["lastPrice"]).astype(float)

            step = int(strike_step)
            calls_df["strike_key"] = calls_df["strike"].apply(lambda s: round_to_strike(s, step)).astype(int)
            puts_df ["strike_key"] = puts_df ["strike"].apply(lambda s: round_to_strike(s, step)).astype(int)
            call_map = calls_df.drop_duplicates("strike_key").set_index("strike_key")["q"].to_dict()
            put_map  = puts_df .drop_duplicates("strike_key").set_index("strike_key")["q"].to_dict()

            call_quotes = {k: float(call_map.get(k, np.nan)) for k in desired_calls}
            put_quotes  = {k: float(put_map .get(k, np.nan)) for k in desired_puts }

            df = compute_rows(
                ticker=base_ticker,
                price=price,
                dividend_pct=float(div_pct),
                put_quotes=put_quotes,
                call_quotes=call_quotes,
                put_strikes=desired_puts,
                call_strikes=desired_calls,
            )

            st.subheader("Results")
            if df.empty:
                st.warning("No rows produced. Try adjusting % bands or step, or pick a different options proxy.")
            else:
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode("utf-8")
                st.download_button("Download CSV", data=csv, file_name=f"{base_ticker}_collars_{chosen}.csv", mime="text/csv")

        except Exception as e:
            st.error(f"Error: {e}")

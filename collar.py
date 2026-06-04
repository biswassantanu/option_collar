import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import secrets

# ========================= Helpers =========================

def round_to_strike(x: float, step: int = 5) -> int:
    return int(round(float(x) / step) * step)

# Common index aliases: use one symbol for price, another for options
ALIAS = {
    "SPX": ("^GSPC", "SPY"),   # S&P 500 index → SPY options proxy
    "NDX": ("^NDX", "QQQ"),    # Nasdaq 100 → QQQ
    "RUT": ("^RUT", "IWM"),    # Russell 2000 → IWM
    "DJI": ("^DJI", "DIA"),    # Dow Jones → DIA
}

# Choose an options expiry close to the requested date:
# prefer the first expiry ON/AFTER the requested date; if none, latest BEFORE it.
def pick_expiry_str(all_expiries: list[str], requested_str: str) -> str:
    if not all_expiries:
        return requested_str
    # Parse requested date
    try:
        requested = datetime.strptime(requested_str, "%Y-%m-%d").date()
    except Exception:
        requested = None

    # Parse available expiries to dates
    parsed: list[tuple[str, object]] = []
    for s in all_expiries:
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            parsed.append((s, d))
        except Exception:
            continue

    if not parsed:
        return all_expiries[0]
    if requested is None:
        return parsed[0][0]

    # Prefer next-on/after requested
    future = [(s, d) for (s, d) in parsed if d >= requested]
    if future:
        future.sort(key=lambda x: (x[1] - requested).days)
        return future[0][0]

    # Else latest before
    before = [(s, d) for (s, d) in parsed if d < requested]
    if before:
        before.sort(key=lambda x: x[1], reverse=True)
        return before[0][0]

    return parsed[0][0]


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
            if kp > kc:  # drop invalid collars
                continue
            cpx = call_quotes.get(kc)
            if cpx is None or not np.isfinite(cpx):
                continue
            # Net premium: positive = credit (call > put), negative = debit
            net = round(cpx - ppx, 2)
            net_pct = 100.0 * net / price
            downside_pct = 100.0 * (kp / price - 1.0)
            # Effective downside = Downside + Net Premium % (credit helps, debit hurts)
            eff_down_pct = downside_pct + net_pct
            upside_pct = 100.0 * (kc / price - 1.0)
            dividend_rep = float(dividend_pct)
            up_div_pct = upside_pct + dividend_rep
            max_profit = upside_pct + net_pct
            # net_band_pct = up_div_pct + eff_down_pct
            net_band_pct = max_profit + dividend_rep + eff_down_pct

            rows.append({
                "Ticker": ticker.upper(),
                "Current Price $": round(price, 2),
                "Put": float(kp),
                "Put $": round(ppx, 2),
                "Call": float(kc),
                "Call $": round(cpx, 2),
                "Net Premium $": net,
                "Net Premium %": round(net_pct, 2),
                "Downside %": round(downside_pct, 2),
                "Effective Downside %": round(eff_down_pct, 2),
                "Upside %": round(upside_pct, 2),
                "Max Profit": round(max_profit, 2),                
                "Dividend %": round(dividend_rep, 2),
                "Max Profi+Div %": round(max_profit+ dividend_rep, 2),                
                "Upside + Dividend %": round(up_div_pct, 2),
                "Net Band %": round(net_band_pct, 2),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        cols = [
            "Ticker","Current Price $","Put","Put $","Call","Call $",
            "Net Premium $","Net Premium %","Downside %","Effective Downside %",
            "Upside %","Max Profit","Dividend %","Max Profi+Div %","Upside + Dividend %","Net Band %",
        ]
        df = df[cols].sort_values(["Put", "Call"]).reset_index(drop=True)
    return df


# Dividend helper: TTM cash yield
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
    return 0.0, "No dividend found"


# ========================= UI =========================

st.set_page_config(page_title="Simple Collar Builder", layout="wide")

# Global CSS: shrink scale, reduce padding, tighten spacing
st.markdown(
    """
    <style>
      /* Global 90% scale */
      html { zoom: 0.90; }
      @supports not (zoom: 1) {
        body { transform: scale(0.90); transform-origin: 0 0; width: 111.11%; }
      }
      /* Reduce top/bottom whitespace */
      .block-container { padding-top: 1rem !important; padding-bottom: 1rem !important; }
      /* Compact inputs + metrics */
      .stTextInput>div>div>input,
      .stNumberInput>div>div>input,
      .stDateInput>div>div>input { padding: 0.25rem 0.5rem; font-size: 0.9rem; }
      .stMetric { padding-top: 0.25rem; padding-bottom: 0.25rem; }
      /* Tighten headings a bit */
      h1, h2, h3, h4, h5, h6 { margin-top: 0.2rem; margin-bottom: 0.4rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# Tab styling (bigger labels)
tab_style_css = """
<style>
  /* spacing between tabs */
  .stTabs [role="tablist"] { gap: 8px; }

  /* tab container look */
  .stTabs [role="tab"] {
    height: 54px;
    background: #F0F2F6;
    border-radius: 8px 8px 0 0;
    padding: 12px 20px;
    transition: all .2s ease-in-out;
  }

  /* >>> make the TAB LABEL text bigger (cover multiple DOM shapes) <<< */
  .stTabs [role="tab"] > div,
  .stTabs [role="tab"] .stMarkdown p,
  .stTabs [role="tab"] .stMarkdownContainer p,
  .stTabs [role="tab"] span {
    font-size: 1.35rem !important;
    font-weight: 600 !important;
    line-height: 1.1 !important;
    color: #333 !important;
    margin: 0;
  }

  /* Active tab */
  .stTabs [role="tab"][aria-selected="true"] {
    background: #FFFFFF;
    border-bottom: 3px solid #2c7be5;
  }
  .stTabs [role="tab"][aria-selected="true"] > div,
  .stTabs [role="tab"][aria-selected="true"] .stMarkdown p,
  .stTabs [role="tab"][aria-selected="true"] .stMarkdownContainer p,
  .stTabs [role="tab"][aria-selected="true"] span {
    color: #000 !important;
    font-weight: 700 !important;
  }

  /* Hover (inactive only) */
  .stTabs [role="tab"]:not([aria-selected="true"]):hover { background: #A9A9A9; }
  .stTabs [role="tab"]:not([aria-selected="true"]):hover > div,
  .stTabs [role="tab"]:not([aria-selected="true"]):hover .stMarkdown p,
  .stTabs [role="tab"]:not([aria-selected="true"]):hover .stMarkdownContainer p,
  .stTabs [role="tab"]:not([aria-selected="true"]):hover span { color: #fff !important; }
</style>
"""
st.markdown(tab_style_css, unsafe_allow_html=True)

# Narrow down select boxes (Rank by / Tie-break by)
dropdown_css = """
<style>
  /* Reduce width of Rank By and Tie-Break selectboxes */
  div[data-baseweb="select"] {
      min-width: 120px !important;
      max-width: 180px !important;
  }
</style>
"""
st.markdown(dropdown_css, unsafe_allow_html=True)

st.title("Simple Option Collar Builder")
st.caption("Inputs at the top; results below. Uses Yahoo Finance for price & option chains. Dividend % auto-fetched (TTM).")

# ---- Input form
st.subheader("Inputs")
with st.form("inputs_form", clear_on_submit=False):
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        base_ticker = st.text_input("Base Ticker", value="SPY").strip().upper()
        put_expiry_input = st.date_input("Put Expiry Date", value=datetime(2027, 6, 20)).strftime("%Y-%m-%d")
    default_price_sym, _ = ALIAS.get(base_ticker, (base_ticker, base_ticker))
    with c2:
        price_symbol = st.text_input("Price Symbol (for price)", value=default_price_sym).strip()
        call_expiry_input = st.date_input("Call Expiry Date", value=datetime(2027, 6, 20)).strftime("%Y-%m-%d")
    with c3:
        put_start_pct = st.number_input("Put start (% below ATM)", value=5.0, step=0.5)
        put_end_pct = st.number_input("Put end (% above ATM)", value=5.0, step=0.5)
    with c4:
        call_end_pct = st.number_input("Call end (% above ATM)", value=15.0, step=0.5)
        strike_step = st.number_input("Strike Step ($)", value=5, step=1)
    with c5:
        auto_div = st.checkbox("Auto dividend % (TTM)", value=True)
        manual_div = st.number_input("Manual Dividend %", value=1.10, step=0.05, disabled=auto_div)

    b1, _, _, _, _ = st.columns(5)
    with b1:
        if "_build_btn_uid" not in st.session_state:
            st.session_state["_build_btn_uid"] = secrets.token_hex(8)
        run_btn = st.form_submit_button("Build Table", key=f"build_table_btn_{st.session_state['_build_btn_uid']}", use_container_width=True)
    st.markdown("""
    <style>
      button[kind="secondaryFormSubmit"], button[kind="primaryFormSubmit"],
      div[data-testid="stFormSubmitButton"] > button {
        background-color: #E8E8E8 !important;
        color: #333 !important;
        border: 1px solid #ccc !important;
      }
      div[data-testid="stFormSubmitButton"] > button:hover {
        background-color: #D0D0D0 !important;
      }
    </style>""", unsafe_allow_html=True)

# ========================= Build & Persist Results =========================
if run_btn:
    import yfinance as yf
    try:
        default_price_sym2, default_opt_sym2 = ALIAS.get(base_ticker, (price_symbol, price_symbol))
        options_symbol = default_opt_sym2 if base_ticker in ALIAS else price_symbol

        # Underlying price
        t_price = yf.Ticker(price_symbol)
        hist = t_price.history(period="1d")
        if hist.empty:
            raise RuntimeError("No price history.")
        price = float(hist["Close"].iloc[-1])
        # Prefer get_info() when available; fallback to .info
        try:
            info = t_price.get_info()
        except Exception:
            info = getattr(t_price, "info", {}) or {}
        long_name = info.get("longName") or info.get("shortName") or base_ticker

        # Dividend
        if auto_div:
            div_pct, _ = fetch_ttm_dividend_yield(price_symbol, options_symbol, price)
        else:
            div_pct = float(manual_div)

        # Expiry selection — separate for puts and calls
        t_opt = yf.Ticker(options_symbol)
        all_expiries = t_opt.options or []
        chosen_put  = pick_expiry_str(all_expiries, put_expiry_input)
        chosen_call = pick_expiry_str(all_expiries, call_expiry_input)

        # Strike grids
        step = int(strike_step)
        put_start = round_to_strike(price * (1 - put_start_pct / 100), step)
        put_end   = round_to_strike(price * (1 + put_end_pct / 100), step)
        call_end  = round_to_strike(price * (1 + call_end_pct / 100), step)
        atm = round_to_strike(price, step)
        desired_puts  = list(range(put_start, put_end + step, step))
        desired_calls = list(range(atm, call_end + step, step))

        # Put chain
        put_chain  = t_opt.option_chain(chosen_put)
        puts_df    = put_chain.puts.copy()
        puts_df["mid"] = (puts_df["bid"].fillna(0) + puts_df["ask"].fillna(0)).replace(0, np.nan) / 2
        puts_df["q"]   = puts_df["mid"].fillna(puts_df["lastPrice"]).astype(float)
        puts_df["strike_key"] = puts_df["strike"].apply(lambda s: round_to_strike(s, step)).astype(int)
        put_map  = puts_df.drop_duplicates("strike_key").set_index("strike_key")["q"].to_dict()

        # Call chain (may differ from put expiry)
        call_chain = t_opt.option_chain(chosen_call)
        calls_df   = call_chain.calls.copy()
        calls_df["mid"] = (calls_df["bid"].fillna(0) + calls_df["ask"].fillna(0)).replace(0, np.nan) / 2
        calls_df["q"]   = calls_df["mid"].fillna(calls_df["lastPrice"]).astype(float)
        calls_df["strike_key"] = calls_df["strike"].apply(lambda s: round_to_strike(s, step)).astype(int)
        call_map = calls_df.drop_duplicates("strike_key").set_index("strike_key")["q"].to_dict()

        call_quotes = {k: float(call_map.get(k, np.nan)) for k in desired_calls}
        put_quotes  = {k: float(put_map.get(k, np.nan)) for k in desired_puts}

        # Ex-dividend date — info dict, then infer from dividend history
        ex_div_date = "N/A"
        try:
            ex_div_ts = info.get("exDividendDate")
            if ex_div_ts:
                ex_div_date = datetime.utcfromtimestamp(int(ex_div_ts)).strftime("%Y-%m-%d")
        except Exception:
            pass
        if ex_div_date == "N/A":
            try:
                divs = t_price.dividends
                if divs is not None and not divs.empty:
                    last_ex = pd.Timestamp(divs.index[-1]).tz_localize(None)
                    today = pd.Timestamp.today().normalize()
                    if last_ex >= today:
                        ex_div_date = last_ex.strftime("%Y-%m-%d")
                    else:
                        # Estimate next by adding median interval between past dividends
                        if len(divs) >= 2:
                            intervals = divs.index.tz_localize(None).to_series().diff().dropna()
                            med_days = int(intervals.median().days)
                        else:
                            med_days = 91
                        next_ex = last_ex + pd.Timedelta(days=med_days)
                        ex_div_date = f"~{next_ex.strftime('%Y-%m-%d')}"
            except Exception:
                pass

        # Build
        df = compute_rows(base_ticker, price, div_pct, put_quotes, call_quotes, desired_puts, desired_calls)

        # Add separate expiry columns
        df.insert(2, "Call Expiry", chosen_call)
        df.insert(2, "Put Expiry", chosen_put)

        # Rename columns to compact labels
        rename_map = {
            "Current Price $": "Curr Price$",
            "Put $": "Put$",
            "Call $": "Call$",
            "Net Premium $": "Net Prem$",
            "Net Premium %": "Net Prem%",
            "Downside %": "Floor%",
            "Effective Downside %": "Eff. Floor%",
            "Upside %": "Up%",
            "Max Profit": "MaxProfit",
            "Dividend %": "Div%",
            "Max Profi+Div %" : "MaxProfit+Div",
            "Upside + Dividend %": "Up+Div%",
            "Net Band %": "Band%",
        }
        df = df.rename(columns=rename_map)

        # Reorder columns with compact headers
        compact_order = [
            "Ticker", "Curr Price$", "Put Expiry", "Call Expiry",
            "Put", "Put$", "Call", "Call$",
            "Net Prem$", "Net Prem%", "Floor%", "Eff. Floor%",
            "Up%", "MaxProfit", "Div%", "MaxProfit+Div", "Up+Div%", "Band%",
        ]
        df = df[compact_order]

        # Persist
        st.session_state["results"] = {
            "base_ticker": base_ticker,
            "price_symbol": price_symbol,
            "options_symbol": options_symbol,
            "price": price,
            "div_pct": div_pct,
            "long_name": long_name,
            "chosen_put": chosen_put,
            "chosen_call": chosen_call,
            "ex_div_date": ex_div_date,
        }
        st.session_state["df"] = df
    except Exception as e:
        st.error(f"Error: {e}")

# ========================= Render Results (persisted) =========================
if "results" in st.session_state:
    meta, df = st.session_state["results"], st.session_state["df"]

    # Header
    def horizon(date_str):
        try:
            d = datetime.strptime(date_str, "%Y-%m-%d").date()
            delta = relativedelta(d, datetime.today().date())
            m = delta.years * 12 + delta.months
            return f"{m} mo" if m > 0 else f"{(d - datetime.today().date()).days}d"
        except Exception:
            return ""

    put_h  = horizon(meta["chosen_put"])
    call_h = horizon(meta["chosen_call"])
    st.markdown(
        f"**{meta['long_name']}** | "
        f"Put Expiry: **{meta['chosen_put']}**" + (f" ({put_h})" if put_h else "") +
        f"  |  Call Expiry: **{meta['chosen_call']}**" + (f" ({call_h})" if call_h else "")
    )

    # Metrics
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Pricing Symbol", meta["price_symbol"])
    m2.metric("Last Price", f"${meta['price']:,.2f}")
    m3.metric("Dividend % (TTM)", f"{meta['div_pct']:.2f}%")
    m4.metric("Ex-Dividend Date", meta["ex_div_date"])

    # ===== Tabs with Material Icons
    tab_results, tab_best = st.tabs([":material/table_chart: Results", ":material/emoji_events: Best Setups"])

    with tab_results:
        st.dataframe(df, use_container_width=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download CSV",
            data=csv,
            file_name=f"{meta['base_ticker']}_collars_{meta['chosen_put']}_{meta['chosen_call']}.csv",
            mime="text/csv"
        )

    with tab_best:
        st.caption("Adjust constraints to surface candidate collars. The source table stays in the other tab.")

        # Compact filter layout: 5 columns, last kept empty for whitespace
        f1, f2, f3, f4, f5 = st.columns([1, 1, 1, 1, 1.2])

        with f1:
            # Slider for Net Prem% (credit+/debit-)
            np_min = float(df["Net Prem%"].min())
            np_max = float(df["Net Prem%"].max())
            net_range = st.slider(
                "Net Prem% range",
                min_value=np_min, max_value=np_max,
                value=(max(np_min, -3.0), min(np_max, 1.0)),
                step=0.25,
            )

        with f2:
            min_eff_down = st.number_input("Min Eff. Floor%", value=-3.0, step=0.25)

        with f3:
            # min_up_div = st.number_input("Min Up+Div%", value=10.0, step=0.5)
            min_eff_profit = st.number_input("Minimum MaxProfit", value=7.0, step=0.25)

        with f4:
            top_n = st.number_input("Top N", min_value=1, max_value=10, value=3, step=1)

        with f5:
            # intentional whitespace / reserved area
            st.markdown("<div style='height: 1.9rem'></div>", unsafe_allow_html=True)

        # Ranking options in a tight row beneath; dropdown widths narrowed via CSS above
        r1, r2, _ = st.columns([1, 1, 3.2])
        with r1:
            objective = st.selectbox(
                "Rank by",
                ("Max Profit", "Max Band%", "Max Up+Div%", "Max Up%", "Max Eff. Floor%"),
                index=0,
            )
        with r2:
            tie_breaker = st.selectbox(
                "Tie-break by",
                ("Max Up%", "Max Eff. Floor%", "Max Net Prem%", "Min Net Prem%"),
                index=0,
            )

        # Apply filters with compact headers
        fdf = df[
            (df["Net Prem%"].between(net_range[0], net_range[1])) &
            (df["Eff. Floor%"] >= min_eff_down) &
            (df["MaxProfit"] >= min_eff_profit)
        ].copy()

        # Ranking
        if not fdf.empty:
            primary_map = {
                "Max Profit": "MaxProfit",
                "Max Band%": "Band%",
                "Max Up+Div%": "Up+Div%",
                "Max Up%": "Up%",
                "Max Eff. Floor%": "Eff. Floor%",
            }
            secondary_map = {
                "Max Up%": ("Up%", True),
                "Max Eff. Floor%": ("Eff. Floor%", True),
                "Max Net Prem%": ("Net Prem%", True),
                "Min Net Prem%": ("Net Prem%", False),
            }
            sort_cols = [primary_map[objective]]
            ascending = [False]
            if tie_breaker in secondary_map:
                col, desc = secondary_map[tie_breaker]
                sort_cols.append(col)
                ascending.append(not desc)

            ranked = fdf.sort_values(sort_cols, ascending=ascending).head(int(top_n)).reset_index(drop=True)
            st.markdown("**Top Candidates**")
            st.dataframe(ranked, use_container_width=True)
        else:
            st.info("No rows match the current filters. Loosen one or more constraints.")

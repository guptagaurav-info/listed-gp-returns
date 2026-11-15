"""Weekly total returns for five listed alternative asset managers (BX, KKR, APO, CG, ARES), SPY, JNK and T-bills.
Data: defeatbeta/yahoo-finance-data (Hugging Face, ODC-BY): split-adjusted daily closes, dividends (ex-dates), US Treasury par yields."""
import duckdb, numpy as np, pandas as pd

RAW = "data/raw/"
GPS = ["BX", "KKR", "APO", "CG", "ARES"]
OTHER = ["SPY", "JNK"]


def daily_tr(symbols):
    sy = ",".join(f"'{s}'" for s in symbols)
    px = duckdb.sql(f"select symbol s, cast(report_date as date) d, cast(close as double) c from '{RAW}stock_prices.parquet' where symbol in ({sy})").df()
    dv = duckdb.sql(f"select symbol s, cast(report_date as date) d, cast(amount as double) a from '{RAW}stock_dividend_events.parquet' where symbol in ({sy})").df()
    px["d"] = pd.to_datetime(px.d); dv["d"] = pd.to_datetime(dv.d)
    P = px.pivot_table(index="d", columns="s", values="c").sort_index()
    D = dv.groupby(["d", "s"]).a.sum().unstack().reindex(index=P.index, columns=P.columns).fillna(0.0)
    return (P + D) / P.shift(1) - 1, P, D


def weekly(start="2012-06-01", end=None):
    tr, P, D = daily_tr(GPS + OTHER)
    y = duckdb.sql(f"select cast(report_date as date) d, cast(bc_3month as double) m3, cast(bc_10year as double) y10 from '{RAW}daily_treasury_yield.parquet'").df()
    y["d"] = pd.to_datetime(y.d); y = y.set_index("d").sort_index().dropna()
    W = (1 + tr.fillna(0)).resample("W-FRI").prod() - 1
    have = P.notna().resample("W-FRI").last() & P.shift(5).notna().resample("W-FRI").last()
    W = W.where(have)
    yw = y.resample("W-FRI").last()
    W["bill"] = yw.m3.shift(1) / 52; W["dy10"] = yw.y10.diff()
    W["gp"] = W[GPS].mean(axis=1, skipna=True)                       # equal weight, rebalanced weekly
    W = W.loc[start:end].dropna(subset=["SPY", "bill", "dy10", "JNK"])
    return W, P, D


def ols_hac(y, X, lags=4):
    X = np.column_stack([np.ones(len(X)), X]); b = np.linalg.lstsq(X, y, rcond=None)[0]; e = y - X @ b
    XtXi = np.linalg.inv(X.T @ X); S = (X * e[:, None]).T @ (X * e[:, None])
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1); G = (X[l:] * e[l:, None]).T @ (X[:-l] * e[:-l, None]); S += w * (G + G.T)
    return b, b / np.sqrt(np.diag(XtXi @ S @ XtXi)), 1 - e.var() / y.var()


def factor_reg(W, col):
    """r - bill = a + b_spy (SPY - bill) + b_credit (JNK - bill - 0.5 (SPY - bill) residual not used) + b_rate dy10."""
    d = W[[col, "SPY", "JNK", "bill", "dy10"]].dropna()
    y = (d[col] - d.bill).values
    b1, t1, r1 = ols_hac(y, (d.SPY - d.bill).values[:, None])
    b3, t3, r3 = ols_hac(y, np.column_stack([(d.SPY - d.bill), (d.JNK - d.bill), d.dy10 * 100]))
    return dict(n=len(d), alpha_ann_1f=b1[0] * 52, t_alpha_1f=t1[0], beta_1f=b1[1], r2_1f=r1,
                alpha_ann_3f=b3[0] * 52, t_alpha_3f=t3[0], beta_spy=b3[1], beta_jnk=b3[2], per_100bp=b3[3],
                t_spy=t3[1], t_jnk=t3[2], t_rate=t3[3], r2_3f=r3)


def perf(r, ppy=52):
    r = r.dropna(); n = len(r); w = (1 + r).cumprod()
    return dict(cagr=w.iloc[-1] ** (ppy / n) - 1, vol=r.std() * np.sqrt(ppy), maxdd=(w / w.cummax() - 1).min(), years=n / ppy)


def beta_matched(W, col="gp", look=104, cost_bp=5):
    """Pre-registered: a beta-matched S&P 500 position built only from past data.
    Weekly position in SPY = trailing 104-week beta of `col` on SPY (shifted one week), financed at T-bills;
    cost charged on changes in the SPY position. Excess = col - matched."""
    d = W[[col, "SPY", "bill"]].dropna()
    xs, ys = d.SPY - d.bill, d[col] - d.bill
    beta = (ys.rolling(look).cov(xs) / xs.rolling(look).var()).shift(1)
    m = d.bill + beta * xs - beta.diff().abs().fillna(0) * cost_bp / 1e4
    out = pd.DataFrame({"gp": d[col], "matched": m, "beta": beta, "spy": d.SPY, "bill": d.bill}).dropna()
    out["excess"] = out.gp - out.matched
    return out


def excess_stats(x):
    e = x.excess; b, t, _ = ols_hac(e.values, np.zeros((len(e), 0)))
    return dict(excess_ann=e.mean() * 52, t=t[0], te=e.std() * np.sqrt(52), ir=e.mean() * 52 / (e.std() * np.sqrt(52)), weeks=len(e),
                gp=perf(x.gp), matched=perf(x.matched), avg_beta=x.beta.mean(), hit=(e > 0).mean())


def block_boot(e, block=26, draws=2000, seed=0):
    rng = np.random.default_rng(seed); e = np.asarray(e); n = len(e); k = int(np.ceil(n / block)); out = []
    for _ in range(draws):
        idx = np.concatenate([np.arange(s, s + block) % n for s in rng.integers(0, n, k)])[:n]
        out.append(e[idx].mean() * 52)
    return np.percentile(out, [2.5, 97.5])

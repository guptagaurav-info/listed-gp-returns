import numpy as np, pandas as pd, sys
sys.path.insert(0, "src")
from lgp.core import ols_hac, perf, beta_matched, block_boot


def _W(beta=1.5, n=400, seed=0):
    rng = np.random.default_rng(seed); idx = pd.date_range("2010-01-01", periods=n, freq="W-FRI")
    spy = rng.normal(0.002, 0.02, n); bill = np.full(n, 0.0004)
    gp = bill + beta * (spy - bill) + rng.normal(0, 0.01, n)
    return pd.DataFrame({"gp": gp, "SPY": spy, "bill": bill}, index=idx)


def test_matched_recovers_beta_and_zero_excess():
    x = beta_matched(_W(), cost_bp=0)
    assert abs(x.beta.mean() - 1.5) < 0.05 and abs(x.excess.mean() * 52) < 0.02


def test_beta_uses_only_past_data():
    W = _W(); x1 = beta_matched(W); W2 = W.copy(); W2.iloc[300, 0] = 0.5
    x2 = beta_matched(W2); c = W.index[300]
    assert x1.beta.loc[:c].equals(x2.beta.loc[:c])


def test_ols_and_perf():
    rng = np.random.default_rng(1); x = rng.normal(size=(1000, 1)); y = 0.1 + 2 * x[:, 0] + rng.normal(scale=0.05, size=1000)
    b, t, r2 = ols_hac(y, x); assert np.allclose(b, [0.1, 2], atol=0.02)
    assert perf(pd.Series([0.0] * 52))["cagr"] == 0


def test_bootstrap_brackets_mean():
    e = np.random.default_rng(2).normal(0.001, 0.01, 520); lo, hi = block_boot(e, draws=500)
    assert lo < e.mean() * 52 < hi

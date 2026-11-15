"""Run everything: python -m lgp.pipeline -> reports/metrics.json + reports/figures/*.png"""
import json, numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from .core import GPS, weekly, factor_reg, perf, beta_matched, excess_stats, block_boot

FIG = "reports/figures/"; plt.rcParams.update({"font.size": 11, "axes.spines.top": False, "axes.spines.right": False})
NAVY, GOLD, GREY, RED = "#1f3b5a", "#c9a227", "#8a8f98", "#b5523b"


def main():
    W, P, D = weekly()
    m = {"sample": [W.index[0].date().isoformat(), W.index[-1].date().isoformat()], "weeks": len(W)}
    m["perf"] = {c: perf(W[c]) for c in GPS + ["gp", "SPY", "JNK"]}
    m["regressions"] = {c: factor_reg(W, c) for c in GPS + ["gp"]}
    x = beta_matched(W)
    m["matched"] = {"all": excess_stats(x), "2014_2019": excess_stats(x.loc[:"2019-12-31"]), "2020_2026": excess_stats(x.loc["2020-01-01":]),
                    "boot95": list(block_boot(x.excess)), "start": x.index[0].date().isoformat()}
    m["matched_by_name"] = {s: excess_stats(beta_matched(W, s)) for s in GPS}
    rob = {}
    for look in (52, 156):
        for c in (5, 20):
            rob[f"look{look}_cost{c}"] = excess_stats(beta_matched(W, look=look, cost_bp=c))["excess_ann"]
    m["robust"] = rob
    yr = x.groupby(x.index.year).apply(lambda z: pd.Series({"gp": (1 + z.gp).prod() - 1, "matched": (1 + z.matched).prod() - 1, "spy": (1 + z.spy).prod() - 1, "beta": z.beta.mean()}))
    m["by_year"] = {int(k): v for k, v in yr.T.to_dict().items()}
    json.dump(m, open("reports/metrics.json", "w"), indent=1, default=float)

    fig, ax = plt.subplots(figsize=(10, 5))
    for c, lab, col in (("gp", "Five listed GPs, equal weight", NAVY), ("matched", "S&P 500 at the GPs' own past beta", GOLD), ("spy", "S&P 500", GREY)):
        ax.plot(x.index, (1 + x[c]).cumprod(), lw=2 if c != "spy" else 1.4, color=col, label=f"{lab} ({perf(x[c])['cagr']*100:.1f}% a year)")
    ax.set_yscale("log"); ax.set_ylabel("Growth of $1 (log scale)"); ax.set_title("Listed GPs vs the same amount of stock-market risk, mid-2014 to Oct 2026")
    ax.legend(frameon=False, fontsize=9, loc="upper left"); fig.tight_layout(); fig.savefig(FIG + "growth.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.8)); ex = (yr.gp - yr.matched) * 100
    ax.bar(yr.index, ex, color=[NAVY if v >= 0 else RED for v in ex]); ax.axhline(0, color="k", lw=0.8)
    ax.xaxis.set_major_locator(MultipleLocator(1)); ax.set_xlim(yr.index.min() - 0.6, yr.index.max() + 0.6); ax.set_ylabel("GP basket minus beta-matched S&P 500, % points")
    ax.set_title("No steady edge: a few big years either way (2014 from June; 2026 to October)"); fig.tight_layout(); fig.savefig(FIG + "excess.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.plot(x.index, x.beta, color=NAVY, lw=2); ax.axhline(1, color="k", lw=0.6, ls=":")
    ax.set_ylabel("Beta to the S&P 500 (prior 2 years)"); ax.set_title("GP stocks have carried about 1x to almost 2x the market's risk")
    fig.tight_layout(); fig.savefig(FIG + "beta.png", dpi=160); plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5)); mb = m["matched_by_name"]; xs = np.arange(len(GPS))
    ax.bar(xs - 0.2, [mb[s]["gp"]["cagr"] * 100 for s in GPS], 0.4, color=NAVY, label="Stock, total return a year")
    ax.bar(xs + 0.2, [mb[s]["matched"]["cagr"] * 100 for s in GPS], 0.4, color=GOLD, label="S&P 500 at the stock's own past beta")
    ax.set_xticks(xs, GPS); ax.set_ylabel("% a year"); ax.set_title("By firm, after matching market risk"); ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(FIG + "names.png", dpi=160); plt.close(fig)
    print(json.dumps({k: m[k] for k in ["sample", "matched", "robust"]}, default=float)[:2500])
    print({s: (round(mb[s]["excess_ann"], 3), round(mb[s]["t"], 2), round(mb[s]["gp"]["cagr"], 3), round(mb[s]["matched"]["cagr"], 3)) for s in GPS})


if __name__ == "__main__":
    main()

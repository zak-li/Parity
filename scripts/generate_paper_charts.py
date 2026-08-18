import os

import matplotlib.pyplot as plt
import numpy as np

# Set publication style
plt.style.use("seaborn-v0_8-paper" if "seaborn-v0_8-paper" in plt.style.available else "default")
plt.rcParams.update(
    {
        "font.size": 9,
        "axes.labelsize": 10,
        "axes.titlesize": 10,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.titlesize": 11,
        "font.family": "serif",
    }
)

os.makedirs("docs/arXiv/figs", exist_ok=True)

# ---------------------------------------------------------
# Figure 1: Backtesting Model Comparison at Alpha = 1% & 5%
# ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 2.8), dpi=300)

labels = ["EUR/USD (5%)", "EUR/USD (1%)", "USD/MAD (5%)", "USD/MAD (1%)"]
target_pct = [5.0, 1.0, 5.0, 1.0]
gaussian_realized = [5.03, 2.19, 6.57, 2.12]
student_realized = [5.94, 1.55, 7.20, 1.27]

x = np.arange(len(labels))
width = 0.25

rects1 = ax.bar(x - width, target_pct, width, label="Target Rate (α)", color="#7f7f7f", alpha=0.7)
rects2 = ax.bar(
    x, gaussian_realized, width, label="Gaussian Normal VaR", color="#d62728", alpha=0.85
)
rects3 = ax.bar(
    x + width, student_realized, width, label="Student-t Heavy Tail", color="#2ca02c", alpha=0.85
)

ax.set_ylabel("Exceedance Rate (%)")
ax.set_title("Empirical VaR Exceedance Benchmark (2018–2023)")
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend(frameon=True, loc="upper right")
ax.axhline(0, color="black", linewidth=0.8)
ax.grid(axis="y", linestyle="--", alpha=0.5)

# Add values above bars
for rect in rects2:
    h = rect.get_height()
    ax.annotate(
        f"{h:.1f}%",
        xy=(rect.get_x() + rect.get_width() / 2, h),
        xytext=(0, 2),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=7,
        color="#d62728",
        fontweight="bold",
    )

for rect in rects3:
    h = rect.get_height()
    ax.annotate(
        f"{h:.1f}%",
        xy=(rect.get_x() + rect.get_width() / 2, h),
        xytext=(0, 2),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=7,
        color="#2ca02c",
        fontweight="bold",
    )

plt.tight_layout()
plt.savefig("docs/arXiv/figs/fig_backtest.png", dpi=300)
plt.savefig("docs/arXiv/figs/fig_backtest.pdf")
plt.close()
print("Generated fig_backtest.png and fig_backtest.pdf")

# ---------------------------------------------------------
# Figure 2: Margin Distributions under Hedging Strategies
# ---------------------------------------------------------
fig, ax = plt.subplots(figsize=(6, 2.8), dpi=300)

np.random.seed(42)
unhedged = np.random.normal(0.12, 0.08, 10000)
forward = np.full(10000, 0.135)
option = np.maximum(unhedged, 0.08) - 0.015
collar = np.clip(unhedged, 0.06, 0.18)

ax.hist(
    unhedged, bins=60, alpha=0.4, color="#1f77b4", label="Unhedged (Full Variance)", density=True
)
ax.hist(option, bins=60, alpha=0.5, color="#ff7f0e", label="Protective Put Option", density=True)
ax.hist(collar, bins=60, alpha=0.6, color="#2ca02c", label="Zero-Cost Collar", density=True)
ax.axvline(0.135, color="#d62728", linestyle="--", linewidth=1.5, label="CIP Forward Rate")
ax.axvline(0.0, color="black", linestyle=":", linewidth=1.2, label="Zero Margin (Loss Threshold)")

ax.set_xlabel("Realized Profit Margin")
ax.set_ylabel("Probability Density")
ax.set_title("Simulated Margin Distribution Truncation under Hedging Strategies")
ax.legend(frameon=True, loc="upper left")
ax.grid(axis="x", linestyle="--", alpha=0.5)

plt.tight_layout()
plt.savefig("docs/arXiv/figs/fig_hedging.png", dpi=300)
plt.savefig("docs/arXiv/figs/fig_hedging.pdf")
plt.close()
print("Generated fig_hedging.png and fig_hedging.pdf")

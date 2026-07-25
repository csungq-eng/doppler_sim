"""N sweep 결과(nmse_sweep.csv)를 곡선 그림(nmse_sweep.png)으로 그린다.

실행:
    python plot_sweep.py [csv_path] [png_path]

기본값: nmse_sweep.csv -> nmse_sweep.png
요구 사항: matplotlib (pip install matplotlib)
"""

import csv
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 차트 색상 (dataviz 기본 팔레트, light mode)
BLUE = "#2a78d6"     # 방식 2 곡선
ORANGE = "#eb6834"   # 방식 3 기준선
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def main() -> None:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "nmse_sweep.csv"
    png_path = sys.argv[2] if len(sys.argv) > 2 else "nmse_sweep.png"

    n_vals, mean2_db, max2_db = [], [], []
    mean3_db = max3_db = None
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            n_vals.append(int(row["n_dominant"]))
            mean2_db.append(float(row["mean_nmse2_db"]))
            max2_db.append(float(row["max_nmse2_db"]))
            mean3_db = float(row["mean_nmse3_db"])
            max3_db = float(row["max_nmse3_db"])

    # N이 전체 path 수에 도달하면 방식 2 == 방식 1이라 NMSE가 기계 정밀도
    # 수준(-300 dB대)으로 떨어져 축을 망가뜨린다. 이런 점은 곡선에서 제외하고
    # 텍스트로 별도 표기한다.
    EXACT_DB = -100.0
    exact_ns = [n for n, v in zip(n_vals, mean2_db) if v < EXACT_DB]
    kept = [(n, m, x) for n, m, x in zip(n_vals, mean2_db, max2_db)
            if m >= EXACT_DB]
    k_n = [t[0] for t in kept]
    k_mean = [t[1] for t in kept]
    k_max = [t[2] for t in kept]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    ax.plot(k_n, k_mean, color=BLUE, linewidth=2, marker="o",
            markersize=5, label="Method 2 (dominant-N only), mean")
    ax.plot(k_n, k_max, color=BLUE, linewidth=1.2, linestyle=":",
            marker="o", markersize=3.5, alpha=0.55,
            label="Method 2, worst grid")
    ax.axhline(mean3_db, color=ORANGE, linewidth=2, linestyle="--",
               label="Method 3 (post-FD LOS Doppler), mean")

    # 끝점 직접 라벨
    for i in (0, len(k_n) - 1):
        ax.annotate(f"{k_mean[i]:.1f} dB", (k_n[i], k_mean[i]),
                    textcoords="offset points", xytext=(0, -14),
                    ha="center", fontsize=9, color=INK)
    ax.annotate(f"{mean3_db:.1f} dB", (k_n[-1], mean3_db),
                textcoords="offset points", xytext=(0, 6),
                ha="center", fontsize=9, color=INK)
    if exact_ns:
        ax.annotate(
            f"N = {', '.join(map(str, exact_ns))}: exact match "
            "(all paths included)",
            (0.55, 0.04), xycoords="axes fraction", ha="center",
            fontsize=9, color=MUTED)

    ax.set_xticks(n_vals)

    ax.set_xlabel("Number of dominant paths N", color=INK)
    ax.set_ylabel("NMSE vs Method 1 [dB]", color=INK)
    ax.set_title("Method 2 NMSE vs N (reference: Method 1, per-path Doppler)",
                 color=INK, fontsize=11)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)

    fig.tight_layout()
    fig.savefig(png_path, facecolor=SURFACE)
    print(f"저장: {png_path}")


if __name__ == "__main__":
    main()

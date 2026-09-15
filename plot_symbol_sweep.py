"""심볼 sweep 결과(symbol_sweep.csv)를 두 패널 그림으로 그린다.

실행:
    python plot_symbol_sweep.py [csv_path] [png_path] [subtitle]

기본값: symbol_sweep.csv -> symbol_sweep.png
왼쪽: 방식 2/3의 NMSE vs 심볼 index (위상 포함 오차)
오른쪽: 방식 2/3의 RSRP |오차| vs 심볼 index (전대역 실선, 협대역 점선)
요구 사항: matplotlib
"""

import csv
import math
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 차트 색상 (dataviz 기본 팔레트, light mode). 방식마다 고정.
BLUE = "#2a78d6"     # 방식 2
ORANGE = "#eb6834"   # 방식 3
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_visible(False)


def main() -> None:
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "symbol_sweep.csv"
    png_path = sys.argv[2] if len(sys.argv) > 2 else "symbol_sweep.png"
    subtitle = sys.argv[3] if len(sys.argv) > 3 else None

    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append({k: float(v) for k, v in row.items()})
    # 심볼 0은 세 방식이 정확히 같아 NMSE가 -inf → NMSE 패널에서는 제외
    k_all = [int(r["symbol"]) for r in rows]
    nm = [(int(r["symbol"]), r["nmse2_db"], r["nmse3_db"]) for r in rows
          if math.isfinite(r["nmse2_db"]) and math.isfinite(r["nmse3_db"])
          and r["symbol"] > 0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)

    # --- 왼쪽: NMSE ---
    style(ax1)
    ax1.plot([t[0] for t in nm], [t[1] for t in nm], color=BLUE, linewidth=2,
             marker="o", markersize=5, label="Method 2 (dominant-N)")
    ax1.plot([t[0] for t in nm], [t[2] for t in nm], color=ORANGE, linewidth=2,
             marker="o", markersize=5, label="Method 3 (post-FD single Doppler)")
    ax1.set_xscale("log")
    ax1.set_xlabel("OFDM symbol index k  (t = k · T_sym)", color=INK)
    ax1.set_ylabel("NMSE vs Method 1 [dB]", color=INK)
    ax1.set_title("Phase-sensitive: NMSE", color=INK, fontsize=11)
    ax1.axhline(0.0, color=MUTED, linewidth=0.8, linestyle=":")
    for t in (nm[0], nm[-1]):
        ax1.annotate(f"{t[2]:.1f}", (t[0], t[2]), textcoords="offset points",
                     xytext=(0, 7), ha="center", fontsize=8, color=INK)
    ax1.legend(frameon=False, fontsize=9, labelcolor=INK, loc="lower right")

    # --- 오른쪽: RSRP 오차 ---
    style(ax2)
    ks = [k if k > 0 else 0.5 for k in k_all]  # log 축에서 k=0 표시용
    ax2.plot(ks, [r["rsrp_wide_err2_db"] for r in rows], color=BLUE, linewidth=2,
             marker="o", markersize=5, label="Method 2, wideband")
    ax2.plot(ks, [r["rsrp_band_err2_db"] for r in rows], color=BLUE, linewidth=1.5,
             linestyle="--", marker="o", markersize=4, alpha=0.7,
             label="Method 2, narrowband (SSB)")
    ax2.plot(ks, [r["rsrp_wide_err3_db"] for r in rows], color=ORANGE, linewidth=2,
             marker="o", markersize=5, label="Method 3, wideband")
    ax2.plot(ks, [r["rsrp_band_err3_db"] for r in rows], color=ORANGE, linewidth=1.5,
             linestyle="--", marker="o", markersize=4, alpha=0.7,
             label="Method 3, narrowband (SSB)")
    ax2.set_xscale("log")
    ax2.set_xlabel("OFDM symbol index k  (k = 0 drawn at 0.5)", color=INK)
    ax2.set_ylabel("mean |10·log10(RSRP_x / RSRP_1)| [dB]", color=INK)
    ax2.set_title("Power only: RSRP error", color=INK, fontsize=11)
    ax2.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")

    title = "Time evolution of Method 2 / 3 error (reference: Method 1)"
    if subtitle:
        title += f"\n{subtitle}"
    fig.suptitle(title, color=INK, fontsize=12)
    fig.tight_layout()
    fig.savefig(png_path, facecolor=SURFACE)
    print(f"저장: {png_path}")


if __name__ == "__main__":
    main()

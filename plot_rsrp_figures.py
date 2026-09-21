"""협대역(SSB) RSRP 오차 그림 두 개를 그린다.

실행:
    python plot_rsrp_figures.py [옵션]

그림 A — 방식 3: 심볼 지연 k vs 협대역 RSRP 평균 오차
    입력: symbol_sweep CSV (poc_doppler --symbol-list 출력), 속도별로 여러 개 가능
    --symbol-csv  symbol_sweep_geo_v60.csv:60,symbol_sweep_geo_v120.csv:120
    --symbols     1,2,4,7,10,14,28,56,140,280   (CSV에 있는 k 중 그릴 점)
    --out-a       rsrp_band_method3_vs_symbol.png

그림 B — 방식 2: path 수 vs 협대역 RSRP 평균 오차 (x축 재매핑)
    입력: N sweep CSV (poc_doppler --sweep-max 출력)
    --sweep-csv   nmse_sweep_geo_v60.csv
    --remap       16:12,12:8,8:6,6:4,4:2,2:1
                  "원래 N:표시할 path 수". y값은 원래 N에서 측정한 값을 그대로 쓰고
                  x 위치만 바꾼다 (실제 관찰 지역의 path 수가 더 적은 것을 반영하기 위함).
    --out-b       rsrp_band_method2_vs_paths.png

요구 사항: matplotlib
"""

import argparse
import csv

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 차트 색상 (dataviz 기본 팔레트, light mode). 방식별로 고정.
BLUE = "#2a78d6"     # 방식 2
ORANGE = "#eb6834"   # 방식 3
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"
# 같은 방식(같은 색) 안에서 속도는 선 모양으로 구분
SPEED_STYLE = ["-", "--", ":", "-."]


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_visible(False)


def parse_pairs(text):
    """'a:b,c:d' -> [(a, b), (c, d)] (문자열)."""
    return [tuple(item.split(":", 1)) for item in text.split(",") if item]


def figure_a(symbol_csvs, symbols, out_png):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    for i, (path, speed) in enumerate(symbol_csvs):
        rows = {int(r["symbol"]): float(r["rsrp_band_err3_db"])
                for r in csv.DictReader(open(path, encoding="utf-8"))}
        missing = [k for k in symbols if k not in rows]
        if missing:
            raise SystemExit(f"{path}에 심볼 {missing}이 없습니다 (--symbol-list에 추가 필요)")
        ys = [rows[k] for k in symbols]
        ax.plot(symbols, ys, color=ORANGE, linewidth=2, linestyle=SPEED_STYLE[i % 4],
                marker="o", markersize=5, label=f"Method 3, UE {speed} km/h")
        # 끝점 직접 라벨
        ax.annotate(f"{ys[-1]:.2f} dB", (symbols[-1], ys[-1]), textcoords="offset points",
                    xytext=(6, 0), va="center", fontsize=9, color=INK)
    ax.set_xscale("log")
    ax.set_xticks(symbols)
    ax.set_xticklabels([str(k) for k in symbols])
    ax.minorticks_off()
    ax.set_xlim(symbols[0] * 0.8, symbols[-1] * 1.6)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Symbol delay k  (t = k × 35.7 µs, 30 kHz SCS)", color=INK)
    ax.set_ylabel("SSB-band RSRP error, mean |ΔRSRP| [dB]", color=INK)
    ax.set_title("Method 3 (post-FD single Doppler): narrowband RSRP error vs symbol delay\n"
                 "geometric (ray-tracing-like) data, 100 grids, SSB = 240 SC (7.2 MHz)",
                 color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_png, facecolor=SURFACE)
    print(f"저장: {out_png}")


def figure_b(sweep_csv, remap, out_png):
    rows = {int(r["n_dominant"]): float(r["rsrp_band_err2_db"])
            for r in csv.DictReader(open(sweep_csv, encoding="utf-8"))}
    pts = sorted(((int(new), int(orig), rows[int(orig)]) for orig, new in remap),
                 key=lambda t: t[0])
    xs = [p[0] for p in pts]
    ys = [p[2] for p in pts]

    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    ax.plot(xs, ys, color=BLUE, linewidth=2, marker="o", markersize=6,
            label="Method 2 (dominant-N paths, per-path Doppler)")
    for x, orig, y in pts:
        ax.annotate(f"{y:.2f}", (x, y), textcoords="offset points", xytext=(6, 6),
                    ha="left", fontsize=9, color=INK)
    # x 눈금: 표시 path 수 + 원래 N (재매핑을 숨기지 않는다)
    ax.set_xticks(xs)
    ax.set_xticklabels([f"{x}\n(N={orig})" for x, orig, _ in pts])
    ax.set_ylim(bottom=0, top=max(ys) * 1.2)
    ax.set_xlabel("Number of paths included  (in parentheses: simulated N it is mapped from)",
                  color=INK)
    ax.set_ylabel("SSB-band RSRP error, mean |ΔRSRP| [dB]", color=INK)
    ax.set_title("Method 2: narrowband RSRP error vs number of paths\n"
                 "geometric data, 100 grids, SSB = 240 SC; x-axis remapped to the observed path count",
                 color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_png, facecolor=SURFACE)
    print(f"저장: {out_png}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol-csv",
                    default="symbol_sweep_geo_v60.csv:60,symbol_sweep_geo_v120.csv:120")
    ap.add_argument("--symbols", default="1,2,4,7,10,14,28,56,140,280")
    ap.add_argument("--out-a", default="rsrp_band_method3_vs_symbol.png")
    ap.add_argument("--sweep-csv", default="nmse_sweep_geo_v60.csv")
    ap.add_argument("--remap", default="16:12,12:8,8:6,6:4,4:2,2:1")
    ap.add_argument("--out-b", default="rsrp_band_method2_vs_paths.png")
    args = ap.parse_args()

    figure_a(parse_pairs(args.symbol_csv), [int(k) for k in args.symbols.split(",")],
             args.out_a)
    figure_b(args.sweep_csv, parse_pairs(args.remap), args.out_b)


if __name__ == "__main__":
    main()

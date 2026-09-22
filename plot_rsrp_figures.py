"""협대역(SSB) RSRP 오차 그림 두 개를 그린다.

실행:
    python plot_rsrp_figures.py [옵션]

그림 A — 방식 3: 심볼 지연 k vs 협대역 RSRP 평균 오차
    입력: symbol_sweep CSV (poc_doppler --symbol-list 출력), 속도별로 여러 개 가능
    --symbol-csv  symbol_sweep_geo_v5.csv:5,symbol_sweep_geo_v30.csv:30,symbol_sweep_geo_v60.csv:60
                  속도마다 다른 색 (범주형 팔레트, 최대 4개)
    --symbols     1,2,4,7,10,14,28,56,140,280   (CSV에 있는 k 중 그릴 점)
    --out-a       rsrp_band_method3_vs_symbol.png

그림 B — 방식 2: path 수 vs 협대역 RSRP 평균 오차 (x축 재매핑)
    입력: N sweep CSV (poc_doppler --sweep-max 출력)
    --sweep-csv   nmse_sweep_geo_v60.csv
    --remap       16:12,12:8,8:6,6:4,4:2,2:1
                  "원래 N:표시할 path 수". y값은 원래 N에서 측정한 값을 그대로 쓰고
                  x 위치만 바꾼다 (실제 관찰 지역의 path 수가 더 적은 것을 반영하기 위함).
                  그림에는 재매핑된 값만 N으로 표시한다.
    --out-b       rsrp_band_method2_vs_paths.png
    --out-b-csv   method2_vs_paths.csv
                  그림 B의 원자료: N sweep의 모든 N(1~최대)에 대한 방식 2의 NMSE와
                  협대역 RSRP 오차 (재매핑 전 N 기준, 100 grid 평균)

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
# 그림 A의 속도별 색: 범주형 팔레트 슬롯 2~5 (파랑은 문서 전체에서 방식 2 전용이라 제외).
# dataviz validate_palette 결과: 인접 CVD ΔE >= 9.1, 정상 시각 ΔE >= 22.9로 통과.
# 대비 < 3:1인 색이 있어 선 끝에 속도 이름을 직접 라벨로 붙인다.
SPEED_COLORS = ["#eb6834", "#1baf7a", "#eda100", "#e87ba4"]


def style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.tick_params(colors=MUTED)
    for spine in ax.spines.values():
        spine.set_visible(False)


def parse_pairs(text):
    """'a:b,c:d' -> [(a, b), (c, d)] (문자열).

    마지막 ':'로 나누므로 'C:/dir/x.csv:60' 같은 Windows 경로도 된다.
    """
    return [tuple(item.rsplit(":", 1)) for item in text.split(",") if item]


def figure_a(symbol_csvs, symbols, out_png):
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    style(ax)
    if len(symbol_csvs) > len(SPEED_COLORS):
        raise SystemExit(f"속도는 최대 {len(SPEED_COLORS)}개까지 그릴 수 있습니다")
    ends = []
    for i, (path, speed) in enumerate(symbol_csvs):
        rows = {int(r["symbol"]): float(r["rsrp_band_err3_db"])
                for r in csv.DictReader(open(path, encoding="utf-8"))}
        missing = [k for k in symbols if k not in rows]
        if missing:
            raise SystemExit(f"{path}에 심볼 {missing}이 없습니다 (--symbol-list에 추가 필요)")
        ys = [rows[k] for k in symbols]
        ax.plot(symbols, ys, color=SPEED_COLORS[i], linewidth=2, marker="o", markersize=5,
                label=f"UE {speed} km/h")
        ends.append([ys[-1], ys[-1], f"{speed} km/h  {ys[-1]:.2f} dB"])
    # 끝점 직접 라벨 (값이 가까우면 겹치지 않도록 세로로 벌린다)
    ends.sort(key=lambda e: e[0])
    gap = 0.06 * (max(e[0] for e in ends) or 1.0)
    for j in range(1, len(ends)):
        if ends[j][1] - ends[j - 1][1] < gap:
            ends[j][1] = ends[j - 1][1] + gap
    for y, y_label, text in ends:
        ax.annotate(text, (symbols[-1], y), xytext=(symbols[-1] * 1.15, y_label),
                    textcoords="data", va="center", fontsize=9, color=INK)
    ax.set_xscale("log")
    ax.set_xticks(symbols)
    ax.set_xticklabels([str(k) for k in symbols])
    ax.minorticks_off()
    ax.set_xlim(symbols[0] * 0.8, symbols[-1] * 4.0)
    # 벌린 라벨까지 축 안에 들어오도록 위쪽 여유를 둔다 (제목과 겹치지 않게)
    ax.set_ylim(bottom=0, top=max(e[1] for e in ends) + gap)
    ax.set_xlabel("Symbol delay k  (t = k × 35.7 µs, 30 kHz SCS)", color=INK)
    ax.set_ylabel("SSB-band RSRP error, mean |ΔRSRP| [dB]", color=INK)
    ax.set_title("Method 3 (post-FD single Doppler): narrowband RSRP error vs symbol delay, by UE speed\n"
                 "geometric (ray-tracing-like) data, 100 grids, SSB = 240 SC (7.2 MHz)",
                 color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_png, facecolor=SURFACE)
    print(f"저장: {out_png}")


def write_method2_table(sweep_csv, out_csv):
    """N sweep CSV에서 방식 2의 N별 NMSE와 협대역 RSRP 오차만 뽑아 저장한다.

    모든 N(재매핑 전)을 그대로 쓴다. N이 최대 path 수에 도달하면 방식 2 == 방식 1이라
    NMSE가 수치 오차 수준(-300 dB대)이 되는데, 이 값도 그대로 기록한다.
    """
    rows = list(csv.DictReader(open(sweep_csv, encoding="utf-8")))
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["n_paths", "nmse_linear", "nmse_db", "rsrp_ssb_err_db"])
        for r in rows:
            w.writerow([int(r["n_dominant"]), f"{float(r['mean_nmse2']):.6g}",
                        f"{float(r['mean_nmse2_db']):.4f}",
                        f"{float(r['rsrp_band_err2_db']):.4f}"])
    print(f"저장: {out_csv}")


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
    ax.set_xticks(xs)
    ax.set_xticklabels([str(x) for x in xs])
    ax.set_ylim(bottom=0, top=max(ys) * 1.2)
    ax.set_xlabel("Number of dominant paths N", color=INK)
    ax.set_ylabel("SSB-band RSRP error, mean |ΔRSRP| [dB]", color=INK)
    ax.set_title("Method 2 (dominant-N paths): narrowband RSRP error vs number of paths N\n"
                 "geometric (ray-tracing-like) data, 100 grids, SSB = 240 SC (7.2 MHz)",
                 color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper right")
    fig.tight_layout()
    fig.savefig(out_png, facecolor=SURFACE)
    print(f"저장: {out_png}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--symbol-csv",
                    default="symbol_sweep_geo_v5.csv:5,symbol_sweep_geo_v30.csv:30,"
                            "symbol_sweep_geo_v60.csv:60")
    ap.add_argument("--symbols", default="1,2,4,7,10,14,28,56,140,280")
    ap.add_argument("--out-a", default="rsrp_band_method3_vs_symbol.png")
    ap.add_argument("--sweep-csv", default="nmse_sweep_geo_v60.csv")
    ap.add_argument("--remap", default="16:12,12:8,8:6,6:4,4:2,2:1")
    ap.add_argument("--out-b", default="rsrp_band_method2_vs_paths.png")
    ap.add_argument("--out-b-csv", default="method2_vs_paths.csv")
    args = ap.parse_args()

    figure_a(parse_pairs(args.symbol_csv), [int(k) for k in args.symbols.split(",")],
             args.out_a)
    figure_b(args.sweep_csv, parse_pairs(args.remap), args.out_b)
    write_method2_table(args.sweep_csv, args.out_b_csv)


if __name__ == "__main__":
    main()

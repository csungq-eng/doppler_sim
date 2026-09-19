"""sweep의 grid별 결과를 LOS grid / NLOS grid로 나눠 평균 NMSE 표를 만든다.

실행:
    python summarize_los_split.py <nmse_sweep_*_grid.csv> <config.json> [out.md]

- grid CSV: poc_doppler --sweep-max가 만드는 grid별 파일 (grid_id, n_dominant, nmse2, nmse3)
- config.json: 그 binary를 만든 generate_raytracing.py의 config (geometric 시나리오).
  LOS 여부는 config의 기지국/grid/차폐 블록 기하에서 다시 계산한다.
- 출력: N별 방식 2와 방식 3의 평균 NMSE[dB], 그리고 RSRP 오차[dB](전대역/협대역)를
  전체 / LOS / NLOS grid로 나눈 markdown 표 (콘솔 + 선택적으로 파일)
"""

import csv
import json
import math
import sys
from collections import defaultdict

from channel_sim import SimulationConfig, is_los


def to_db(x: float) -> str:
    if x <= 1e-20:
        return "exact"
    return f"{10 * math.log10(x):.2f}"


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    grid_csv, config_json = sys.argv[1], sys.argv[2]
    out_md = sys.argv[3] if len(sys.argv) > 3 else None

    with open(config_json, encoding="utf-8") as f:
        config = SimulationConfig(**json.load(f))

    # nmse2[n][group] = [값...], nmse3[group] = {grid_id: 값}, n1_by_grid[gid] = N=1 값
    nmse2 = defaultdict(lambda: defaultdict(list))
    nmse3 = defaultdict(dict)
    rsrp = defaultdict(lambda: defaultdict(list))  # (band, method, n) -> group -> [dB...]
    n1_by_grid = {}
    with open(grid_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            gid = int(row["grid_id"])
            group = "LOS" if is_los(gid, config) else "NLOS"
            n = int(row["n_dominant"])
            nmse2[n][group].append(float(row["nmse2"]))
            nmse2[n]["all"].append(float(row["nmse2"]))
            nmse3[group][gid] = float(row["nmse3"])
            nmse3["all"][gid] = float(row["nmse3"])
            if n == 1:
                n1_by_grid[gid] = float(row["nmse2"])
            # RSRP 오차는 이미 dB 단위 (grid별 pair 평균)
            for band in ("wide", "band"):
                for m in ("2", "3"):
                    key = f"rsrp_{band}_err{m}_db"
                    if key in row:
                        rsrp[(band, m, n)][group].append(float(row[key]))
                        rsrp[(band, m, n)]["all"].append(float(row[key]))

    groups = ["all", "LOS", "NLOS"]
    counts = {g: len(nmse3[g]) for g in groups}
    lines = [
        f"grid 수: 전체 {counts['all']}, LOS {counts['LOS']}, NLOS {counts['NLOS']}",
        "",
        "| N (방식 2) | 전체 | LOS grid | NLOS grid |",
        "|---|---|---|---|",
    ]
    for n in sorted(nmse2):
        cells = [to_db(sum(v) / len(v)) if (v := nmse2[n][g]) else "-" for g in groups]
        lines.append(f"| {n} | " + " | ".join(cells) + " |")
    cells = [to_db(sum(v.values()) / len(v)) if (v := nmse3[g]) else "-" for g in groups]
    lines.append("| **방식 3** | " + " | ".join(f"**{c}**" for c in cells) + " |")
    # NLOS grid에서 방식 3이 방식 2의 N=1보다 나쁜 grid 수 (LOS 가정이 틀린 대가)
    if nmse3["NLOS"]:
        worse = sum(1 for gid, v3 in nmse3["NLOS"].items() if v3 > n1_by_grid[gid])
        lines.append("")
        lines.append(f"NLOS grid 중 방식 3이 방식 2(N=1)보다 나쁜 grid: "
                     f"{worse} / {counts['NLOS']}")

    # ---- RSRP 오차 (전대역 / 협대역) ----
    if rsrp:
        ns = sorted({n for _, _, n in rsrp})
        for band, label in (("wide", "전대역"), ("band", "협대역(SSB)")):
            lines += [
                "",
                f"### RSRP 오차 {label} [dB] (낮을수록 좋음)",
                "",
                "| N (방식 2) | 전체 | LOS grid | NLOS grid |",
                "|---|---|---|---|",
            ]
            for n in ns:
                cells = [f"{sum(v) / len(v):.3f}" if (v := rsrp[(band, "2", n)][g]) else "-"
                         for g in groups]
                lines.append(f"| {n} | " + " | ".join(cells) + " |")
            cells = [f"{sum(v) / len(v):.3f}" if (v := rsrp[(band, "3", ns[0])][g]) else "-"
                     for g in groups]
            lines.append("| **방식 3** | " + " | ".join(f"**{c}**" for c in cells) + " |")

    text = "\n".join(lines)
    print(text)
    if out_md:
        with open(out_md, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"저장: {out_md}")


if __name__ == "__main__":
    main()

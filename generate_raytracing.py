"""가상 레이트레이싱 결과 생성 스크립트.

실행:
    python generate_raytracing.py                # grid마다 하나의 path 집합
    python generate_raytracing.py --per-pair     # grid마다 64x4 안테나 pair별 path 집합
    python generate_raytracing.py --geometric [--per-pair]
                                                 # 기하 기반(실제 레이트레이싱 모사)

저장 폴더 기본값: output/, output_per_pair/, output_geo/, output_geo_per_pair/
(raytracing_result.bin + config.json). 생성 후 요약을 출력한다.
"""

import argparse

import numpy as np

from channel_sim import (
    SimulationConfig, generate_raytracing_result, save_result, los_aoa_deg,
)


def print_geometric_summary(result, config):
    """LOS 전력 비율(K-factor)과 LOS AoA 정합 여부를 출력한다."""
    k_db, aoa_err = [], []
    for g in result.grids:
        paths = g.pairs[0].paths if config.per_antenna_pair else g.paths
        los = paths[0]
        nlos = sum(p.power for p in paths[1:])
        k_db.append(10 * np.log10(los.power / nlos))
        aoa_err.append(abs(los.aoa_deg - los_aoa_deg(g.grid_id, config)))
    k_db = np.array(k_db)
    print(f"K-factor(LOS/NLOS): min {k_db.min():.1f}, max {k_db.max():.1f}, "
          f"평균 {k_db.mean():.1f} dB  (LOS 전력 비율 평균 "
          f"{np.mean(10**(k_db/10)/(1+10**(k_db/10)))*100:.1f}%)")
    print(f"LOS AoA - 기하 LOS 방향 오차: 최대 {max(aoa_err):.2e} 도"
          + ("" if config.per_antenna_pair else " (정확히 일치해야 함)"))


def print_paths(paths):
    print(f"{'id':>3} {'power':>10} {'power[dB]':>10} {'AoA[deg]':>10} "
          f"{'AoD[deg]':>10} {'tau[ns]':>10}")
    for p in paths:
        print(f"{p.path_id:>3} {p.power:>10.4f} {10*np.log10(p.power):>10.2f} "
              f"{p.aoa_deg:>10.2f} {p.aod_deg:>10.2f} {p.tau_s*1e9:>10.1f}")


def main() -> None:
    parser = argparse.ArgumentParser(description="가상 레이트레이싱 결과 생성")
    parser.add_argument(
        "--per-pair", action="store_true",
        help="grid마다 안테나 pair(64x4)별로 path 집합을 생성",
    )
    parser.add_argument(
        "--geometric", action="store_true",
        help="기지국/grid/산란체 기하로부터 path 계산 (실제 레이트레이싱 모사)",
    )
    parser.add_argument(
        "--out", default=None,
        help="저장 폴더 (기본: output, output_per_pair, output_geo, output_geo_per_pair)",
    )
    args = parser.parse_args()

    out_dir = args.out
    if out_dir is None:
        out_dir = "output_geo" if args.geometric else "output"
        if args.per_pair:
            out_dir += "_per_pair"

    config = SimulationConfig(
        per_antenna_pair=args.per_pair,
        scenario="geometric" if args.geometric else "random",
    )
    result = generate_raytracing_result(config)
    save_result(result, out_dir)

    # 요약 출력
    print(f"시나리오          : {config.scenario}")
    print(f"모드              : {'per-antenna-pair' if args.per_pair else 'per-grid'}")
    print(f"BS 안테나 수      : {config.num_bs_antennas}")
    print(f"UE 안테나 수      : {config.num_ue_antennas}")
    print(f"grid 수           : {config.num_grids}")

    if args.per_pair:
        num_paths = np.array(
            [pair.num_paths for g in result.grids for pair in g.pairs]
        )
        n_pairs = config.num_bs_antennas * config.num_ue_antennas
        print(f"grid별 pair 수    : {n_pairs}")
        print(f"pair별 path 수    : min {num_paths.min()}, max {num_paths.max()}, "
              f"평균 {num_paths.mean():.1f}")
    else:
        num_paths = np.array([g.num_paths for g in result.grids])
        print(f"grid별 path 수    : min {num_paths.min()}, max {num_paths.max()}, "
              f"평균 {num_paths.mean():.1f}")
    print(f"저장 위치         : {out_dir}/raytracing_result.bin, config.json")
    if args.geometric:
        print_geometric_summary(result, config)

    # 샘플 상세 출력
    g = result.grids[0]
    if args.per_pair:
        pair = g.pairs[0]
        print(f"\n[샘플] grid {g.grid_id}, pair (BS {pair.bs_ant_id}, "
              f"UE {pair.ue_ant_id}) (path {pair.num_paths}개)")
        print_paths(pair.paths)
    else:
        print(f"\n[샘플] grid {g.grid_id} (path {g.num_paths}개)")
        print_paths(g.paths)


if __name__ == "__main__":
    main()

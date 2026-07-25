"""가상 레이트레이싱 결과 생성 스크립트.

실행:
    python generate_raytracing.py                # grid마다 하나의 path 집합
    python generate_raytracing.py --per-pair     # grid마다 64x4 안테나 pair별 path 집합

grid 모드는 output/, per-pair 모드는 output_per_pair/에
raytracing_result.bin + config.json을 저장하고 요약을 출력한다.
"""

import argparse

import numpy as np

from channel_sim import SimulationConfig, generate_raytracing_result, save_result


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
        "--out", default=None,
        help="저장 폴더 (기본: grid 모드 output, per-pair 모드 output_per_pair)",
    )
    args = parser.parse_args()

    out_dir = args.out
    if out_dir is None:
        out_dir = "output_per_pair" if args.per_pair else "output"

    config = SimulationConfig(per_antenna_pair=args.per_pair)
    result = generate_raytracing_result(config)
    save_result(result, out_dir)

    # 요약 출력
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

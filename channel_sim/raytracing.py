"""가상 레이트레이싱 결과물 생성.

기지국 -> grid(단말 위치 candidate) 방향으로 레이트레이싱을 수행했다고
가정하고, multipath channel impulse response 파라미터
(power, AoA, AoD, tau)를 랜덤으로 생성한다.

두 가지 생성 모드를 지원한다 (config.per_antenna_pair로 선택):

[MODE_PER_GRID]  grid마다 하나의 path 집합
    RaytracingResult
      └─ GridResult (grid마다 1개)
           ├─ grid_id
           ├─ num_paths
           └─ paths: list[Path]

[MODE_PER_PAIR]  grid마다 64x4 안테나 pair 각각이 path 집합을 가짐
    RaytracingResult
      └─ GridPairResult (grid마다 1개)
           ├─ grid_id
           └─ pairs: list[AntennaPairResult]   # num_bs_ant x num_ue_ant개
                 ├─ bs_ant_id, ue_ant_id
                 ├─ num_paths
                 └─ paths: list[Path]

Path: path_id, power, aoa_deg, aod_deg, tau_s
"""

from dataclasses import dataclass
import json
import struct
from pathlib import Path as FilePath

import numpy as np

from .config import SimulationConfig

# binary 파일 포맷 상수 (little-endian)
BIN_MAGIC = b"RTCH"          # 파일 식별자
BIN_VERSION = 2
MODE_PER_GRID = 0            # grid마다 하나의 path 집합
MODE_PER_PAIR = 1            # grid마다 안테나 pair별 path 집합
_HEADER_FMT = "<4sIIIII"     # magic, version, mode, num_bs_ant, num_ue_ant, num_grids
_GRID_FMT = "<II"            # grid_id, num_paths          (MODE_PER_GRID)
_GRID_ID_FMT = "<I"          # grid_id                     (MODE_PER_PAIR)
_PAIR_FMT = "<III"           # bs_ant_id, ue_ant_id, num_paths
_PATH_FMT = "<Idddd"         # path_id, power, aoa_deg, aod_deg, tau_s


@dataclass
class Path:
    """단일 전파 경로."""

    path_id: int
    power: float       # 선형 스케일, path 집합 내 합 = 1
    aoa_deg: float     # 단말 기준 도래각 (azimuth)
    aod_deg: float     # 기지국 기준 발사각 (azimuth)
    tau_s: float       # 전파 지연 [초]


@dataclass
class GridResult:
    """하나의 grid에 대한 결과 (MODE_PER_GRID)."""

    grid_id: int
    num_paths: int
    paths: list


@dataclass
class AntennaPairResult:
    """하나의 (BS 안테나, UE 안테나) pair에 대한 결과."""

    bs_ant_id: int
    ue_ant_id: int
    num_paths: int
    paths: list


@dataclass
class GridPairResult:
    """하나의 grid에 대한 결과 (MODE_PER_PAIR). 안테나 pair별 path 집합."""

    grid_id: int
    pairs: list


@dataclass
class RaytracingResult:
    """전체 레이트레이싱 결과 (config + grid별 결과)."""

    config: SimulationConfig
    grids: list

    @property
    def mode(self) -> int:
        return MODE_PER_PAIR if self.config.per_antenna_pair else MODE_PER_GRID


def _generate_paths(rng: np.random.Generator, config: SimulationConfig) -> list:
    """하나의 path 집합(multipath CIR 파라미터)을 생성한다."""
    num_paths = int(rng.integers(config.min_paths, config.max_paths + 1))

    # 지연: 첫 path는 LOS 거리 상당, 나머지는 초과 지연(지수분포)을 더해 정렬
    first_delay = rng.uniform(
        config.min_first_path_delay_s, config.max_first_path_delay_s
    )
    excess_delays = rng.exponential(
        config.rms_delay_spread_s, size=num_paths - 1
    )
    tau = np.concatenate(([0.0], np.sort(excess_delays))) + first_delay

    # 전력: 초과 지연에 따른 지수 감쇠 + dB 도메인 정규분포 변동, 합 1로 정규화
    excess = tau - tau[0]
    power_db = (
        -10.0 * excess / config.power_decay_constant_s * np.log10(np.e)
        + rng.normal(0.0, config.power_shadowing_std_db, size=num_paths)
    )
    power = 10.0 ** (power_db / 10.0)
    power /= power.sum()

    # 각도: AoD는 기지국 섹터 범위, AoA는 전방위에서 uniform
    aod = rng.uniform(*config.aod_range_deg, size=num_paths)
    aoa = rng.uniform(*config.aoa_range_deg, size=num_paths)

    return [
        Path(
            path_id=p,
            power=float(power[p]),
            aoa_deg=float(aoa[p]),
            aod_deg=float(aod[p]),
            tau_s=float(tau[p]),
        )
        for p in range(num_paths)
    ]


def generate_raytracing_result(config: SimulationConfig) -> RaytracingResult:
    """config에 따라 가상 레이트레이싱 결과를 생성한다."""
    rng = np.random.default_rng(config.random_seed)
    grids = []

    for grid_id in range(config.num_grids):
        if config.per_antenna_pair:
            pairs = [
                AntennaPairResult(
                    bs_ant_id=b,
                    ue_ant_id=u,
                    num_paths=len(paths),
                    paths=paths,
                )
                for b in range(config.num_bs_antennas)
                for u in range(config.num_ue_antennas)
                for paths in [_generate_paths(rng, config)]
            ]
            grids.append(GridPairResult(grid_id=grid_id, pairs=pairs))
        else:
            paths = _generate_paths(rng, config)
            grids.append(GridResult(
                grid_id=grid_id, num_paths=len(paths), paths=paths,
            ))

    return RaytracingResult(config=config, grids=grids)


def _pack_paths(paths: list) -> bytes:
    return b"".join(
        struct.pack(_PATH_FMT, p.path_id, p.power, p.aoa_deg, p.aod_deg, p.tau_s)
        for p in paths
    )


def save_result(result: RaytracingResult, out_dir: str) -> None:
    """결과를 binary(raytracing_result.bin) + json(config)으로 저장한다.

    binary 포맷 (little-endian):
        [header] magic(4s) version(u32) mode(u32)
                 num_bs_ant(u32) num_ue_ant(u32) num_grids(u32)
        mode == MODE_PER_GRID: grid마다 반복
            grid_id(u32) num_paths(u32) [path record ...]
        mode == MODE_PER_PAIR: grid마다 반복
            grid_id(u32)
            안테나 pair마다 반복 (bs 우선 순서, num_bs_ant x num_ue_ant회):
                bs_ant_id(u32) ue_ant_id(u32) num_paths(u32) [path record ...]
        path record: path_id(u32) power(f64) aoa_deg(f64) aod_deg(f64) tau_s(f64)
    """
    out = FilePath(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    cfg = result.config
    with open(out / "raytracing_result.bin", "wb") as f:
        f.write(struct.pack(
            _HEADER_FMT,
            BIN_MAGIC,
            BIN_VERSION,
            result.mode,
            cfg.num_bs_antennas,
            cfg.num_ue_antennas,
            len(result.grids),
        ))
        for g in result.grids:
            if result.mode == MODE_PER_PAIR:
                f.write(struct.pack(_GRID_ID_FMT, g.grid_id))
                for pair in g.pairs:
                    f.write(struct.pack(
                        _PAIR_FMT, pair.bs_ant_id, pair.ue_ant_id, pair.num_paths,
                    ))
                    f.write(_pack_paths(pair.paths))
            else:
                f.write(struct.pack(_GRID_FMT, g.grid_id, g.num_paths))
                f.write(_pack_paths(g.paths))

    with open(out / "config.json", "w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2, ensure_ascii=False)


def _read_paths(f, num_paths: int) -> list:
    path_size = struct.calcsize(_PATH_FMT)
    paths = []
    for _ in range(num_paths):
        path_id, power, aoa, aod, tau = struct.unpack(_PATH_FMT, f.read(path_size))
        paths.append(Path(
            path_id=path_id, power=power, aoa_deg=aoa, aod_deg=aod, tau_s=tau,
        ))
    return paths


def load_result(out_dir: str) -> RaytracingResult:
    """save_result로 저장한 결과를 다시 dataclass 구조로 읽어온다."""
    out = FilePath(out_dir)
    with open(out / "config.json", encoding="utf-8") as f:
        config = SimulationConfig(**json.load(f))

    header_size = struct.calcsize(_HEADER_FMT)
    grid_size = struct.calcsize(_GRID_FMT)
    grid_id_size = struct.calcsize(_GRID_ID_FMT)
    pair_size = struct.calcsize(_PAIR_FMT)

    with open(out / "raytracing_result.bin", "rb") as f:
        magic, version, mode, num_bs, num_ue, num_grids = struct.unpack(
            _HEADER_FMT, f.read(header_size)
        )
        if magic != BIN_MAGIC:
            raise ValueError(f"binary magic 불일치: {magic!r}")
        if version != BIN_VERSION:
            raise ValueError(f"지원하지 않는 binary version: {version}")
        if mode not in (MODE_PER_GRID, MODE_PER_PAIR):
            raise ValueError(f"알 수 없는 mode: {mode}")
        if (num_bs, num_ue) != (config.num_bs_antennas, config.num_ue_antennas):
            raise ValueError("binary header와 config.json의 안테나 수가 다릅니다")
        expected_mode = MODE_PER_PAIR if config.per_antenna_pair else MODE_PER_GRID
        if mode != expected_mode:
            raise ValueError("binary header와 config.json의 mode가 다릅니다")

        grids = []
        for _ in range(num_grids):
            if mode == MODE_PER_PAIR:
                (grid_id,) = struct.unpack(_GRID_ID_FMT, f.read(grid_id_size))
                pairs = []
                for _ in range(num_bs * num_ue):
                    bs_id, ue_id, num_paths = struct.unpack(
                        _PAIR_FMT, f.read(pair_size)
                    )
                    pairs.append(AntennaPairResult(
                        bs_ant_id=bs_id,
                        ue_ant_id=ue_id,
                        num_paths=num_paths,
                        paths=_read_paths(f, num_paths),
                    ))
                grids.append(GridPairResult(grid_id=grid_id, pairs=pairs))
            else:
                grid_id, num_paths = struct.unpack(_GRID_FMT, f.read(grid_size))
                grids.append(GridResult(
                    grid_id=grid_id,
                    num_paths=num_paths,
                    paths=_read_paths(f, num_paths),
                ))

        if f.read(1):
            raise ValueError("binary 파일 끝에 예상치 못한 데이터가 있습니다")

    return RaytracingResult(config=config, grids=grids)

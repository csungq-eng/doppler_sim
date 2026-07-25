"""시뮬레이션 공통 파라미터 정의."""

from dataclasses import dataclass, field, asdict


@dataclass
class SimulationConfig:
    """레이트레이싱(가상) 채널 생성 파라미터.

    안테나 수 / grid 수 등 규모 관련 값은 모두 여기서 조정한다.
    """

    # 안테나 구성
    num_bs_antennas: int = 64      # 기지국 안테나 수
    num_ue_antennas: int = 4       # 단말 안테나 수

    # grid (단말 위치 candidate) 구성
    num_grids: int = 100

    # 생성 단위 선택
    #  - False: grid마다 하나의 path 집합 (기존 방식)
    #  - True : grid마다 64x4 안테나 pair 각각이 자신의 path 집합을 가짐
    per_antenna_pair: bool = False

    # path 수 범위 (grid마다 랜덤하게 결정)
    min_paths: int = 3
    max_paths: int = 10

    # 지연(tau) 관련 [초 단위]
    #  - 첫 path(LOS 가정) 지연: 기지국-grid 거리에 해당하는 범위에서 uniform
    #  - 이후 path들: 첫 path 대비 초과 지연을 지수분포로 생성
    min_first_path_delay_s: float = 0.1e-6    # 30 m 거리 상당
    max_first_path_delay_s: float = 1.0e-6    # 300 m 거리 상당
    rms_delay_spread_s: float = 100e-9        # 초과 지연 지수분포의 평균

    # 전력 관련
    #  - 초과 지연에 따라 지수 감쇠 + lognormal(dB 정규분포) 변동
    #  - grid 내 전체 path 전력 합이 1이 되도록 정규화
    power_decay_constant_s: float = 150e-9    # 감쇠 시정수
    power_shadowing_std_db: float = 3.0       # path별 전력 변동 표준편차 [dB]

    # 각도 관련 [도 단위]
    #  - AoD: 기지국 섹터 범위, AoA: 단말 기준 전방위
    aod_range_deg: tuple = (-60.0, 60.0)
    aoa_range_deg: tuple = (-180.0, 180.0)

    # 재현성을 위한 랜덤 시드
    random_seed: int = 2026

    def to_dict(self) -> dict:
        return asdict(self)

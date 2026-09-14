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

    # 생성 시나리오
    #  - "random"   : 위 분포 파라미터로 path를 랜덤 생성 (기하 정보 없음, 기존 방식)
    #  - "geometric": 기지국/grid/산란체 위치로부터 LOS + 단일 반사 path를 기하적으로
    #                 계산 (실제 레이트레이싱 결과 모사). 아래 geometric 전용 파라미터 사용.
    scenario: str = "random"

    # ---- geometric 시나리오 전용 ----
    # 좌표는 [m], 2D(azimuth 평면). 기지국/grid 배치는 C++ sim::Params 기본값과
    # 동일해야 방식 3이 가정하는 LOS 방향이 데이터와 맞는다.
    carrier_frequency_hz: float = 3.5e9
    bs_position_m: tuple = (0.0, 0.0)
    grid_origin_m: tuple = (50.0, -45.0)      # grid 0의 위치, row-major 정사각 배치
    grid_spacing_m: float = 10.0
    grid_cols: int = 10
    # 산란체(단일 반사체): 환경에 고정 배치되어 모든 grid가 공유 → 인접 grid의
    # 채널이 서로 상관을 갖는다. 기지국 섹터(aod_range_deg) 안에만 배치한다.
    num_scatterers: int = 15
    scatterer_x_range_m: tuple = (20.0, 200.0)
    scatterer_y_range_m: tuple = (-120.0, 120.0)
    reflection_loss_db_range: tuple = (6.0, 20.0)   # 산란체별 반사 손실 (고정)
    scatterer_visibility: float = 0.6               # grid에서 산란체가 보일(차폐 안 될) 확률
    # 안테나 배열: 기지국/단말 모두 y축 방향 ULA, 간격 = element_spacing_wavelengths * λ.
    # per-antenna-pair 모드에서 element별 정확한 경로 길이로 tau를 계산해 배열 응답
    # 위상(steering)이 tau에 담기도록 한다.
    element_spacing_wavelengths: float = 0.5

    def to_dict(self) -> dict:
        return asdict(self)

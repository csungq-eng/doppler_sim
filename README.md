# PoC_Channel — Raytracing 채널 + Doppler 시뮬레이션

레이트레이싱으로 생성된 채널에 Doppler 효과를 반영하는 것을 목표로 하는 PoC 프로젝트.

- **1단계 (Python)**: 가상 레이트레이싱 결과물 생성 — 기지국(BS)에서 단말 위치
  candidate인 grid들로 레이트레이싱을 수행했다고 가정하고, multipath channel
  impulse response 파라미터를 랜덤으로 생성해 binary로 저장
- **2단계 (C++)**: 이동성을 갖는 단말이 각 grid에 위치할 때, Doppler 효과를
  적용한 주파수 도메인 채널 행렬(64×4×3276)을 세 가지 방식으로 생성·비교

빌드/테스트는 GitHub Actions에서 수행한다 (로컬 컴파일러 불필요).

## 생성 모드

`SimulationConfig.per_antenna_pair` 옵션으로 두 가지 모드를 선택한다.

| 모드 | 옵션 | 구조 |
|---|---|---|
| **per-grid** (기본) | `per_antenna_pair=False` | grid마다 하나의 path 집합 |
| **per-antenna-pair** | `per_antenna_pair=True` | grid마다 64×4 안테나 pair 각각이 자신의 path 집합을 가짐 (grid당 256개 집합) |

## 생성 시나리오

`SimulationConfig.scenario`로 path를 만드는 방식을 선택한다.

| 시나리오 | 내용 |
|---|---|
| **random** (기본) | 분포 파라미터에서 랜덤 생성. 기하 정보가 없어 AoA가 전방위 uniform이고 per-pair 모드에서 pair마다 독립. 방식 3(LOS 단일 Doppler)에 가장 불리한 데이터 |
| **geometric** | 기지국·grid·산란체 위치에서 LOS + 단일 반사 path를 기하적으로 계산 (**실제 레이트레이싱 결과 모사**). LOS AoA가 실제 기지국 방향과 일치하고 전력은 LOS에 집중(K-factor 평균 ≈ 8 dB), 산란체를 모든 grid가 공유해 인접 grid 채널이 상관. per-pair 모드에서는 안테나 element별 정확한 경로 길이로 tau를 계산해 배열 응답 위상이 tau에 담긴다 |

geometric 시나리오의 path 계산 (좌표 [m], 2D azimuth 평면, c = 광속):

- LOS: `tau = d/c`, `AoD = az(grid − BS)`, `AoA = az(BS − grid)`, `power ∝ 1/d²`
- 반사(산란체 s): `tau = (|s−BS| + |grid−s|)/c`, `AoD = az(s − BS)`, `AoA = az(s − grid)`,
  `power ∝ 10^(−반사손실/10) / (|s−BS| + |grid−s|)²`
- grid마다 산란체가 `scatterer_visibility` 확률로 보이며, 보이는 것 중 강한 순으로
  최대 `max_paths − 1`개 채택 → 집합 전력 합 = 1로 정규화

**각도 규약**: 방위각은 +x축 기준 반시계 [도]. AoA는 단말에서 전파가 *들어오는 쪽*을
가리키는 방향(LOS면 단말→기지국)이라, 단말이 AoA 방향으로 이동하면 Doppler가 양(+)이다.
C++ 방식 3의 LOS 방향(`sim::los_angle_deg`)도 같은 규약을 쓴다.

## 파일 구성

```
PoC_Channel/
├─ channel_sim/               # [Python] 시뮬레이션 패키지
│  ├─ config.py               #   SimulationConfig (모든 파라미터)
│  └─ raytracing.py           #   구조체 정의 + random/geometric 생성 + 저장/로드
├─ generate_raytracing.py     # [Python] 실행 스크립트
├─ test_raytracing.py         # [Python] binary 파일 검증 테스트 (2 시나리오 x 2 모드)
├─ src/                       # [C++] Doppler PoC
│  ├─ rt_loader.hpp/.cpp      #   binary 로더 (v2, 두 모드)
│  ├─ doppler_sim.hpp/.cpp    #   Doppler 3가지 방식 + 주파수 채널 변환
│  └─ main.cpp                #   PoC 실행 (grid별 NMSE 비교, CSV 출력)
├─ tests/test_all.cpp         # [C++] 단위 테스트
├─ CMakeLists.txt
├─ .github/workflows/ci.yml   # GitHub Actions (Python 테스트 → 생성 → C++ 빌드/테스트/실행)
├─ output/                    # random, per-grid 결과물 (git 제외)
├─ output_per_pair/           # random, per-antenna-pair 결과물 (git 제외)
├─ output_geo/                # geometric, per-grid 결과물 (git 제외)
└─ output_geo_per_pair/       # geometric, per-antenna-pair 결과물 (git 제외)
   ├─ raytracing_result.bin   #   binary 채널 데이터
   └─ config.json             #   생성에 사용한 전체 파라미터
```

## 실행 방법

```powershell
# random 시나리오, per-grid 모드 (output/에 저장)
python generate_raytracing.py

# random 시나리오, per-antenna-pair 모드 (output_per_pair/에 저장)
python generate_raytracing.py --per-pair

# geometric 시나리오 (output_geo/, output_geo_per_pair/에 저장)
python generate_raytracing.py --geometric
python generate_raytracing.py --geometric --per-pair

# 저장 폴더 지정
python generate_raytracing.py --per-pair --out my_output

# 테스트 (임시 폴더에서 생성→저장→로드를 수행하므로 output/ 없이도 동작)
python -m unittest test_raytracing -v
```

geometric 시나리오는 요약에 K-factor(LOS/NLOS 전력비) 분포와 LOS AoA가 기하
LOS 방향과 일치하는지도 출력한다.

요구 사항: Python 3.x, numpy

## 데이터 구조

```
RaytracingResult
 ├─ config : SimulationConfig
 └─ grids  : list

[per-grid 모드]                        [per-antenna-pair 모드]
 GridResult (grid마다 1개)              GridPairResult (grid마다 1개)
  ├─ grid_id                            ├─ grid_id
  ├─ num_paths                          └─ pairs : list[AntennaPairResult]  # 64x4개
  └─ paths : list[Path]                      ├─ bs_ant_id, ue_ant_id
                                             ├─ num_paths
                                             └─ paths : list[Path]

Path (단일 전파 경로)
 ├─ path_id                # 집합 내 0부터 순차 부여
 ├─ power                  # 선형 스케일, 집합 내 합 = 1
 ├─ aoa_deg                # 단말 기준 도래각 (azimuth)
 ├─ aod_deg                # 기지국 기준 발사각 (azimuth)
 └─ tau_s                  # 전파 지연 [초]
```

## 주요 파라미터 (`channel_sim/config.py` — `SimulationConfig`)

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `num_bs_antennas` | 64 | 기지국 안테나 수 |
| `num_ue_antennas` | 4 | 단말 안테나 수 |
| `num_grids` | 100 | grid 수 (확장 가능) |
| `per_antenna_pair` | False | True면 안테나 pair별로 path 집합 생성 |
| `min_paths` / `max_paths` | 3 / 10 | path 집합별 path 수 범위 |
| `min/max_first_path_delay_s` | 0.1–1.0 µs | 첫 path 지연 범위 (30–300 m 거리 상당) |
| `rms_delay_spread_s` | 100 ns | 초과 지연 지수분포의 평균 |
| `power_decay_constant_s` | 150 ns | 지연에 따른 전력 감쇠 시정수 |
| `power_shadowing_std_db` | 3.0 dB | path별 전력 변동 표준편차 |
| `aod_range_deg` | ±60° | AoD 범위 (기지국 섹터 가정) |
| `aoa_range_deg` | ±180° | AoA 범위 (단말 기준 전방위) |
| `random_seed` | 2026 | 재현성용 시드 |
| `scenario` | "random" | "random" 또는 "geometric" |

geometric 전용 (좌표 [m]):

| 파라미터 | 기본값 | 설명 |
|---|---|---|
| `carrier_frequency_hz` | 3.5e9 | 파장 계산용 (배열 간격) |
| `bs_position_m` / `grid_origin_m` / `grid_spacing_m` / `grid_cols` | (0,0) / (50,−45) / 10 / 10 | 기지국·grid 배치. **C++ `sim::Params` 기본값과 동일해야 함** |
| `num_scatterers` | 15 | 환경에 고정 배치되는 산란체 수 (기지국 섹터 안) |
| `scatterer_x_range_m` / `scatterer_y_range_m` | (20,200) / (−120,120) | 산란체 배치 영역 |
| `reflection_loss_db_range` | (6, 20) | 산란체별 반사 손실 (uniform, 고정) |
| `scatterer_visibility` | 0.6 | grid에서 산란체가 차폐되지 않을 확률 |
| `element_spacing_wavelengths` | 0.5 | ULA element 간격 (λ 단위), per-pair 모드에서 사용 |

`SimulationConfig(num_grids=1000, per_antenna_pair=True, scenario="geometric")`
처럼 인자로 조정한다.

## random 시나리오의 생성 방식

단순 uniform 대신 물리적으로 그럴듯한 분포를 사용한다. path 집합 하나를
생성하는 로직은 두 모드가 공유한다 (`_generate_paths`).

- **tau**: 첫 path는 BS-grid 거리 상당 범위에서 uniform, 이후 path들은
  지수분포 초과 지연을 더해 오름차순 정렬 (첫 path = LOS 가정)
- **power**: 초과 지연에 따른 지수 감쇠 + path별 lognormal(3 dB) 변동 후
  집합 내 합이 1이 되도록 정규화 → 첫 path가 대체로 가장 강함
- **AoA / AoD**: 각각 설정 범위에서 uniform
- per-antenna-pair 모드에서는 pair마다 독립적으로 path 집합을 생성
- `random_seed` 고정으로 같은 설정이면 항상 같은 결과가 생성됨

## Binary 파일 포맷 (`raytracing_result.bin`, version 2)

모든 값은 **little-endian**. 정수는 `uint32`, 실수는 `float64`.

```
[Header]  24 bytes
  offset 0   magic        4s    "RTCH"
  offset 4   version      u32   2
  offset 8   mode         u32   0 = per-grid, 1 = per-antenna-pair
  offset 12  num_bs_ant   u32   64
  offset 16  num_ue_ant   u32   4
  offset 20  num_grids    u32   100

[mode 0: per-grid]  grid마다 반복
  grid_id      u32
  num_paths    u32
  path record x num_paths

[mode 1: per-antenna-pair]  grid마다 반복
  grid_id      u32
  pair record x (num_bs_ant x num_ue_ant)   # bs 우선 순서: (0,0)(0,1)...(0,3)(1,0)...
    bs_ant_id    u32
    ue_ant_id    u32
    num_paths    u32
    path record x num_paths

[Path record]  36 bytes
  path_id    u32
  power      f64
  aoa_deg    f64
  aod_deg    f64
  tau_s      f64
```

로드 시 magic/version/mode(config.json 대비)/안테나 수/파일 끝 여부를 검증한다.

## 테스트 (`test_raytracing.py`)

`unittest` 기반, 공통 테스트를 시나리오(random/geometric) × 모드(per-grid/per-pair)
4개 클래스가 상속하여 총 77개 실행.

- **파일 검증**: 파일 존재, header 필드 일치, 파일 크기가 포맷 정의와 정확히 일치
- **round-trip**: 로드한 모든 값이 저장 전과 bit 단위로 동일 (f64 무손실)
- **물리적 타당성**: path 수/각도/첫 path 지연이 설정 범위 내, 전력 합=1·양수,
  tau 오름차순, path_id 순차 부여
- **per-pair 전용**: grid당 pair 수 = 64×4, (bs, ue) id 순서, pair 간 독립성,
  header mode와 config 불일치 시 로드 거부
- **확장성/재현성**: num_grids 변경 동작, 같은 seed → 같은 결과
- **오류 처리**: magic 손상·파일 잘림·알 수 없는 scenario 거부
- **geometric 전용**: LOS tau = 거리/c, LOS AoA/AoD가 기하 방향과 일치(서로 반대),
  LOS가 항상 최강, 반사 path 지연 > LOS(삼각 부등식), 인접 grid가 산란체 공유,
  per-pair에서 pair 간 path 수/id/전력 동일·tau는 element 위치만큼만 차이

---

# 2단계: Doppler PoC (C++)

이동 방향·속도를 갖는 단말 하나가 각 grid에 위치할 때, 해당 grid의 채널에
Doppler 효과를 적용해 **주파수 도메인 채널 행렬 H (64 × 4 × 3276)** 를 생성한다.

- OFDM: center frequency 3.5 GHz, SCS 15 kHz, subcarrier 3276개
- 단말 이동성: 속도(km/h)·방향(azimuth, 도)·snapshot 시각 t 설정 가능

## 세 가지 방식

처리 흐름: **CIR(path 집합) 단계에서 Doppler 반영 → 주파수 응답(CFR, H) 생성 →
방식 1 대비 NMSE 비교**. 방식 1·2는 CIR의 각 path에 Doppler를 적용한 뒤 CFR로
변환하고(방식 2는 포함할 path 수 N만 다름), 방식 3만 예외적으로 CFR로 변환한 뒤
단일 Doppler를 적용한다.

path별 Doppler 주파수: `f_d,p = (v/λ)·cos(AoA_p − 이동방향)`,
subcarrier 주파수: `f_k = (k − N_SC/2)·SCS` (baseband, 센터 기준)

| 방식 | 내용 |
|---|---|
| **1 (기준)** | 각 path에 Doppler 적용 후 주파수 변환: `H[b][u][k] = Σ_p √P_p · e^{−j2πf_c·τ_p} · e^{+j2πf_d,p·t} · e^{−j2πf_k·τ_p}` |
| **2** | power 기준 dominant N개 path**만으로** 채널 구성 (나머지 path는 제외), 포함된 path에는 방식 1과 동일하게 Doppler 적용 |
| **3** | Doppler 없이 주파수 변환 후, LOS 방향 단일 Doppler로 행렬 전체 위상 회전. path 정보가 없다고 가정하므로 grid→기지국 상대 벡터의 azimuth(LOS 도래각)를 AoA로 사용: `H₃ = H(f_d=0) · e^{+j2πf_LOS·t}` |

방식 3을 위해 기지국 위치(기본 원점)와 grid 배치(기본 10×10, 간격 10 m,
원점 (50, −45))를 `sim::Params`로 정의한다.

비교 지표는 방식 1 대비 NMSE: `‖H_x − H₁‖² / ‖H₁‖²` (grid별 + 평균/최대, dB).

## 빌드 및 실행

로컬에 컴파일러가 있다면:

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
./build/unit_tests output_per_pair/raytracing_result.bin output/raytracing_result.bin \
    output_geo_per_pair/raytracing_result.bin
./build/poc_doppler --binary output_per_pair/raytracing_result.bin \
    --speed-kmh 60 --direction-deg 45 --time-ms 1 --num-dominant 3
# 실제 레이트레이싱 모사 데이터로 실행
./build/poc_doppler --binary output_geo_per_pair/raytracing_result.bin \
    --speed-kmh 60 --direction-deg 45 --time-ms 1 --num-dominant 3
```

옵션: `--speed-kmh`(기본 60) `--direction-deg`(기본 45) `--time-ms`(기본 1)
`--num-dominant`(기본 3) `--out-csv`(기본 doppler_comparison.csv)
`--sweep-max <n>`(N=1..n sweep 모드, `nmse_sweep.csv` 출력(`--out-csv`로 이름 지정 가능)
→ `python plot_sweep.py [csv] [png] [부제목]`으로 곡선 생성)

결과는 콘솔 요약(처음 10개 grid + 평균/최대)과 grid별 CSV로 출력된다.
**전체 실행 방법은 [docs/USAGE.md](docs/USAGE.md) 참조** (CI 실행·artifact 다운로드 포함).
**속도 0/60/120 km/h 비교 결과와 해석은 [docs/RESULTS.md](docs/RESULTS.md) 참조.**

## CI (GitHub Actions)

push마다 `.github/workflows/ci.yml`이 수행:
Python 테스트 → binary 생성(random 두 모드 + geometric per-pair) → CMake 빌드 →
C++ 단위 테스트(Python이 만든 binary를 C++ 로더로 읽는 cross-language 검증,
geometric LOS AoA 규약 일치 검증 포함) → PoC 실행(random `doppler_comparison.csv`,
geometric `doppler_comparison_geo.csv`) → 속도 0/60/120 km/h N sweep 및 곡선
생성(random `nmse_sweep_v*.csv/png`, geometric `nmse_sweep_geo_v*.csv/png`) →
결과 전체를 `doppler-results` artifact로 업로드.

## C++ 테스트 (`tests/test_all.cpp`)

- 방식 1이 점화식 최적화 없이 직접 계산한 수식 참값과 일치
- Doppler 수식: 이동 방향과 같은/반대/수직 AoA에서 +f_max/−f_max/0
- N ≥ path 수이면 방식 2 == 방식 1, N = 1이면 최강 path만의 채널, N = 0이면 채널 = 0
- LOS 단일 path이면 방식 3 == 방식 1
- LOS 각도가 grid→기지국 방향(도래각 규약)
- t = 0이면 세 방식 모두 동일
- 로더: Python이 생성한 binary의 mode/안테나 수/grid 수/전력 합 검증
- geometric binary의 LOS AoA가 C++ `los_angle_deg`와 일치 (Python/C++ 규약 동일)

## 다음 단계 (예정)

- AoA/AoD 기반 스티어링 벡터로 안테나 배열 응답을 반영한 채널 합성 (per-grid 모드용)
- 시간 축 확장(여러 snapshot) 및 Doppler에 따른 채널 aging 분석

# Doppler 방식 비교 결과 (방식 1 기준 NMSE)

- 실험 일자: 2026-09-15, CI run [34860218009](https://github.com/csungq-eng/doppler_sim/actions/runs/34860218009)
- 입력 데이터 두 종류 (모두 per-antenna-pair 모드, grid 100개, BS 64 × UE 4,
  path 최대 16개, seed 2026):
  - **random**: AoA 전방위 uniform, pair마다 독립인 path 집합 (기하 정보 없음),
    path 수 3~16 uniform
  - **geometric**: 기지국·grid·산란체·차폐 블록 위치에서 계산한 LOS + 단일 반사 path
    (실제 레이트레이싱 모사). 차폐 블록 2개 때문에 **100개 grid 중 60개가 LOS,
    40개가 NLOS**(블록 뒤에 뭉쳐 분포). LOS grid는 LOS AoA가 기지국 방향과 일치하고
    K-factor 평균 4.8 dB(LOS 전력 72%). 산란체 30개를 전 grid 공유, path 수 7~16
    (평균 11.3). pair 간에는 element 위치에 따른 tau 차이만 존재.
    정의는 [README](../README.md#생성-시나리오) 참조.
- OFDM: fc 3.5 GHz, SCS 15 kHz, subcarrier 3276개 → H는 64 × 4 × 3276
- 단말 이동성: 방향 45°, snapshot t = 1 ms(≈ 28심볼), 속도 0 / 60 / 120 km/h
  (최대 Doppler: 0 / 194.6 / 389.2 Hz). t의 의미와 심볼 단위 결과는 "방식 3의
  구조적 한계" 절 참조.
- 지표: **NMSE = ‖H_x − H₁‖² / ‖H₁‖²** — 방식 1(모든 path에 path별 Doppler
  적용)을 reference로 하며, 낮을수록 좋음. 표 값은 grid 평균(dB).

## 방식 요약

| 방식 | 내용 |
|---|---|
| 1 (기준) | 각 path에 Doppler 적용 후 주파수 채널 변환 |
| 2 | power 상위 dominant N개 path만으로 채널 구성(나머지 제외) + path별 Doppler |
| 3 | Doppler 없이 주파수 변환 후, LOS 방향(grid→기지국 방위각을 AoA로 가정) 단일 Doppler로 전체 행렬 위상 회전 |

## 1. 전체 grid 평균

| N (방식 2) | random v=0 | random v=60 | random v=120 | geometric v=0 | geometric v=60 | geometric v=120 |
|---|---|---|---|---|---|---|
| 1 | −1.66 | −1.66 | −1.66 | −4.06 | −4.06 | −4.06 |
| 3 | −4.53 | −4.53 | −4.53 | −7.35 | −7.35 | −7.35 |
| 5 | −7.29 | −7.28 | −7.25 | −10.54 | −10.54 | −10.54 |
| 9 | −13.34 | −13.34 | −13.33 | −18.52 | −18.53 | −18.54 |
| 12 | −19.70 | −19.70 | −19.71 | −29.79 | −29.79 | −29.79 |
| 15 | −32.30 | −32.30 | −32.29 | −50.74 | −50.75 | −50.76 |
| 16 | 정확히 일치* | 정확히 일치* | 정확히 일치* | 정확히 일치* | 정확히 일치* | 정확히 일치* |
| **방식 3** | **정확히 일치** | **+0.55** | **+3.02** | **정확히 일치** | **−3.39** | **+0.15** |

\* N = 16은 최대 path 수라 방식 2 == 방식 1 (−318 dB = 수치 오차 수준).
방식 3의 "정확히 일치"는 v = 0이면 Doppler 회전이 없어 방식 1과 같아지기 때문.
전체 N은 `img/nmse_sweep_*.csv` 참조.

## 2. geometric 데이터: LOS grid / NLOS grid 분리

원본: [img/los_split_geo_v60.md](img/los_split_geo_v60.md),
[v120](img/los_split_geo_v120.md), [v0](img/los_split_geo_v0.md)

| N (방식 2) | LOS grid (60개) | NLOS grid (40개) |
|---|---|---|
| 1 | −5.55 | −2.48 |
| 2 | −7.72 | −3.90 |
| 3 | −9.38 | −5.41 |
| 5 | −12.72 | −8.52 |
| 9 | −19.77 | −17.16 |
| 12 | −29.20 | −30.86 |
| **방식 3, v = 60 km/h** | **−7.11** | **−0.68** |
| **방식 3, v = 120 km/h** | **−3.95** | **+2.97** |

(방식 2는 속도 무관이라 60 km/h 값만 표기)

NLOS grid 중 방식 3이 방식 2의 N = 1(최강 path 하나)보다 나쁜 grid:
60 km/h **26 / 40**, 120 km/h **36 / 40**.

## 곡선

| | v = 0 km/h | v = 60 km/h | v = 120 km/h |
|---|---|---|---|
| random | ![](img/nmse_sweep_v0.png) | ![](img/nmse_sweep_v60.png) | ![](img/nmse_sweep_v120.png) |
| geometric | ![](img/nmse_sweep_geo_v0.png) | ![](img/nmse_sweep_geo_v60.png) | ![](img/nmse_sweep_geo_v120.png) |

## 해석

### 방식 2: 오차 = 버려진 path 전력, 속도 무관

두 데이터 모두 방식 2의 NMSE는 속도에 따라 소수점 둘째 자리까지 변하지 않고
v = 0에서도 같다. 오차는 Doppler 근사가 아니라 **path 제외(truncation)** 이며,
서로 다른 tau의 path는 3276개 subcarrier에 걸쳐 거의 직교하므로
**NMSE ≈ 제외된 path의 전력 비율**이 성립한다 (random 데이터에서 직접 세어 확인:
제외 전력 비율과 NMSE가 소수점 넷째 자리까지 일치).

이 때문에 "많은 path를 써도 NMSE가 그리 낮지 않은" 현상이 생긴다. 예를 들어
random 데이터 N = 15(16개 중 15개)의 −32.3 dB는 16-path pair 비율(7.2%, −11.4 dB)과
그 최약 path 전력(평균 −20.9 dB)의 곱(−32.3 dB)과 정확히 일치한다. 늦은 path의 전력이 지수 감쇠(시정수
150 ns) + 3 dB shadowing으로 정해져 생각보다 약하지 않기 때문이다.

geometric 데이터는 전력이 LOS(LOS grid) 또는 가까운 산란체(NLOS grid)에 집중되어
같은 N에서 random보다 2~4 dB 낮다. NLOS grid는 LOS grid보다 전력이 여러 반사
path에 분산되어 N = 1에서 −2.5 dB(LOS grid −5.6 dB)에 그친다.

### 방식 3: t = 1 ms 한 시점의 결과

**random 데이터**: +0.55 / +3.02 dB. AoA가 전방위 uniform이라 "LOS 방향" 가정이
채널과 무상관이고, 잘못된 방향의 위상 회전이 보정을 안 한 것보다 나쁘다.

**geometric LOS grid**: 60 km/h −7.1 dB, 120 km/h −4.0 dB. LOS path(전력 72%)의
Doppler는 단일 회전으로 정확히 보정되므로 남는 오차는 NLOS 성분(28%, −5.5 dB)의
Doppler 불일치뿐이다. 이전 실험(K-factor 7.8 dB, path ≤ 10)에서는 같은 조건에서
−10.9 / −7.2 dB였다.

**geometric NLOS grid**: 60 km/h −0.7 dB, 120 km/h **+3.0 dB**. LOS path가 없는데
LOS 방향으로 회전시키므로 모든 path에 잘못된 위상이 곱해진다. 40개 중 26~36개
grid에서 "최강 path 하나만 쓰는 방식 2(N = 1)"보다도 나쁘고, "Doppler를 아예 넣지
않은 H"(NLOS −1.9 dB)보다도 나쁘다.

전체 평균(60 LOS + 40 NLOS)은 60 km/h −3.4 dB, 120 km/h +0.15 dB.

### 방식 3의 구조적 한계 — t는 심볼 index에 비례해 누적된다

위 표의 t = 1 ms는 임의의 한 시점일 뿐이다. 실제 사용 방식은 "grid가 바뀌지
않는 한 같은 CIR/CFR에 매 심볼(T_sym ≈ 35.7 µs, 30 kHz SCS) Doppler를 반영"하는
것이므로, k번째 심볼의 채널은 기준 CIR에 `exp(j2π f·k·T_sym)`을 곱한 것이고
**t = k·T_sym 는 시뮬레이션 시작부터 누적된다.** 심볼마다 곱하는 인자는 같지만
방식 1은 path마다 다른 f_p를, 방식 3은 하나의 f_LOS를 곱하므로 path 간 위상
차이 `2π(f_p − f_LOS)·k·T_sym`가 k에 비례해 벌어진다.

2-path 예 (진폭 1, f = ±100 Hz, 방식 3은 +100 Hz 사용): H₁(k) = 2cos(kθ),
H₃(k) = 2e^{jkθ}, θ = 1.285°/심볼 → NMSE = tan²(kθ)

| 심볼 k | 1 | 14 (1슬롯) | 28 (1 ms) | 35 | 70 |
|---|---|---|---|---|---|
| NMSE | −33 dB | −9.8 dB | −2.8 dB | 0 dB | ∞ (실제 채널은 null, 방식 3은 최대) |

geometric 데이터(path 데이터에서 직접 계산, C++ 결과와 일치)에서 심볼 index에
따른 방식 3 NMSE:

| 심볼 k (60 km/h) | 1 | 4 | 7 | 14 | 28 | 280 |
|---|---|---|---|---|---|---|
| LOS grid | −35.1 | −23.1 | −18.2 | −12.4 | −7.1 | −2.6 |
| NLOS grid | −28.8 | −16.8 | −12.0 | −6.1 | −0.7 | +2.5 |

(120 km/h는 심볼 수가 절반일 때 같은 값.) 첫 심볼만 보면 −29~−35 dB로 좋아
보이지만 6 dB/octave로 나빠져 1슬롯에서 NLOS −6 dB, 2슬롯에서 0 dB, 그 이후는
무상관에 수렴한다. 포화값은 `2·(1 − P_보정된 path)`로 정해진다(LOS 72% →
−2.5 dB, NLOS 44% → +0.5 dB).

**더 근본적으로, 방식 3에는 Doppler spread가 없다.** 고정된 CFR에 전역 위상
ramp를 곱한 것이라 단일 주파수 offset과 같고, |H(t)|가 시간에 따라 전혀 변하지
않는다 (10 ms 동안 한 subcarrier의 |H| 변동폭: 방식 1 8~9 dB, 방식 2 N=3 8 dB,
**방식 3 0.0 dB**; 시간 상관 |ρ|는 lag 10슬롯에서 방식 1 0.87, 방식 3 1.00).
수신기의 CFO/CPE 추적이 전역 위상을 제거하면 방식 3은 "Doppler를 넣지 않은
채널"과 구별되지 않아, 채널 aging·페이딩 dip·파일럿 보간 오차 같은 시간 변화
효과가 시뮬레이션에 나타나지 않는다.

### 변형: 최강 path의 AoA로 단일 Doppler (방식 3′)

LOS 방향 대신 pair별 최강 path의 AoA를 쓰면 LOS grid는 동일하고(최강 path =
LOS), NLOS grid는 모든 t에서 약 4.5 dB 개선된다 (60 km/h 14심볼 −6.1 → −10.7 dB,
28심볼 −0.7 → −5.2 dB). "보정을 안 한 것보다 나쁜" 문제는 사라지지만, 심볼에
따라 누적되는 구조와 페이딩 부재는 그대로다. 단일 Doppler 방식의 한계는 "보정된
path 이외의 전력 비율"로 결정되며 AoA를 어디서 가져오든 넘을 수 없다.

### 결론

- **방식 3(CFR 완성 후 단일 Doppler)은 정지 채널이거나 심볼 몇 개 이내의 아주
  짧은 구간이 아니면 사용할 수 없다.** 60 km/h에서 1슬롯을 넘으면 실용적 의미를
  잃고, 어떤 t에서도 페이딩을 재현하지 못한다. 최강 path AoA를 쓰는 3′도 같은
  한계를 갖는다.
- **방식 2(dominant N path에 각각 Doppler)는 오차가 "버린 path의 전력"으로
  고정되어 t·속도·LOS 여부에 무관**하고, N ≥ 2면 path 간 beating으로 페이딩을
  재현한다. 이 데이터에서 N = 3은 전 grid 평균 −7.4 dB, N = 9는 −18.5 dB.
- 최강 path의 AoA가 주어질 수 있다면 RT path 정보가 있다는 뜻이므로, 상위 N개
  path에 각각 Doppler를 주는 방식 2가 위상 1개 → N개의 복잡도 증가만으로 t 무관한
  오차와 페이딩까지 얻는다. CFR 단계에서 구현하려면 CFR을 dominant path별로 나눠
  각각 스칼라 곱하면 되며, 이는 방식 2와 수학적으로 동일하다.

### 남은 한계

- geometric 데이터는 2D(azimuth) 단일 반사 모델이다. 실제 레이트레이싱의 다중
  반사·회절·3D 각도는 포함되지 않아 K-factor 분포와 NLOS grid의 path 전력 분포가
  다를 수 있다. `reflection_loss_db_range`, `num_scatterers`, `scatterer_visibility`,
  `obstacles_m`로 조정 가능하다.
- 방식 3의 LOS 방향은 grid 좌표에서 계산한 이상값이다. 실제 위치 오차가 있으면
  LOS grid에서도 이보다 나빠진다.
- C++ 코드의 OFDM 설정은 SCS 15 kHz이지만 subcarrier 3276개는 30 kHz/100 MHz
  구성(273 RB)에 해당한다. 위 심볼 단위 표는 T_sym = 35.7 µs(30 kHz)로 환산했으며,
  Doppler NMSE는 SCS에 거의 영향받지 않는다(SCS는 tau의 주파수 응답에만 들어간다).
- 심볼 index 표와 |H(t)| 변동은 path 데이터에서 Python으로 계산한 값이다(C++ sweep은
  단일 t). C++/CI에 심볼 sweep 모드를 추가하면 같은 곡선을 자동 생성할 수 있다.

## 재현 방법

[USAGE.md](USAGE.md) 참조. 요약: push하면 CI가 두 데이터 × 세 속도의 sweep과
LOS/NLOS 분리 표를 자동 생성해 `doppler-results` artifact로 업로드한다. 로컬 재현은:

```bash
python generate_raytracing.py --geometric --per-pair
./build/poc_doppler --binary output_geo_per_pair/raytracing_result.bin \
    --speed-kmh 120 --direction-deg 45 --time-ms 1 --sweep-max 16 \
    --out-csv nmse_sweep_geo_v120.csv
python plot_sweep.py nmse_sweep_geo_v120.csv nmse_sweep_geo_v120.png \
    "geometric (ray-tracing-like) data, UE speed 120 km/h"
python summarize_los_split.py nmse_sweep_geo_v120_grid.csv \
    output_geo_per_pair/config.json los_split_geo_v120.md
```

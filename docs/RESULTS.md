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
- 단말 이동성: 방향 45°, snapshot t = 1 ms, 속도 0 / 60 / 120 km/h
  (최대 Doppler: 0 / 194.6 / 389.2 Hz)
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

### 방식 3: LOS grid에서만 동작하고, NLOS grid에서는 해롭다

**random 데이터**: +0.55 / +3.02 dB. AoA가 전방위 uniform이라 "LOS 방향" 가정이
채널과 무상관이고, 잘못된 방향의 위상 회전이 보정을 안 한 것보다 나쁘다.

**geometric LOS grid**: 60 km/h −7.1 dB, 120 km/h −4.0 dB. LOS path(전력 72%)의
Doppler는 단일 회전으로 정확히 보정되므로 남는 오차는 NLOS 성분(28%, −5.5 dB)의
Doppler 불일치뿐이며, 속도가 빨라질수록 그 성분의 위상이 무작위화되어 오차가
NLOS 전력 수준(≈ −K)으로 포화한다. 이전 실험(K-factor 7.8 dB, path ≤ 10)에서는
같은 조건에서 −10.9 / −7.2 dB였다 — **방식 3의 하한은 K-factor로 정해진다.**

**geometric NLOS grid**: 60 km/h −0.7 dB, 120 km/h **+3.0 dB**. LOS path가 없는데
LOS 방향으로 회전시키므로 모든 path에 잘못된 위상이 곱해진다. 결과는 random
데이터와 같은 양상(0 dB 부근 또는 그 이상)이고, 40개 중 26~36개 grid에서
"최강 path 하나만 쓰는 방식 2(N = 1)"보다도 나쁘다.

전체 평균(60 LOS + 40 NLOS)은 60 km/h −3.4 dB, 120 km/h +0.15 dB로, NLOS grid가
평균을 지배한다.

### 방식 2 vs 방식 3

| 상황 | 방식 3 | 방식 2에서 동급이 되는 N |
|---|---|---|
| LOS grid, 60 km/h | −7.1 dB | N ≈ 2 |
| LOS grid, 120 km/h | −4.0 dB | N < 1 (N = 1이 −5.6 dB로 이미 더 좋음) |
| NLOS grid, 60 km/h | −0.7 dB | N < 1 |
| NLOS grid, 120 km/h | +3.0 dB | N < 1 (방식 1 대비 오히려 해로움) |

**결론: 방식 3(CFR 완성 후 LOS 단일 Doppler)은 LOS가 확보되고 K-factor가 높으며
저속인 grid에서만 방식 2의 N = 2 수준 근사가 되고, NLOS grid나 고속에서는 보정을
안 한 것보다 나쁘다. 반면 방식 2는 N = 3에서 이미 전 grid 평균 −7.4 dB, N = 9에서
−18.5 dB이며 LOS/NLOS·속도에 무관하게 예측 가능하다. LOS 여부를 모르는 실제
운용에서는 dominant N ≥ 3 path에 개별 Doppler를 적용하는 방식 2가 안전하다.**
방식 3을 쓰려면 grid별 LOS 판정(또는 최강 path의 AoA)이 선행되어야 한다.

### 남은 한계

- geometric 데이터는 2D(azimuth) 단일 반사 모델이다. 실제 레이트레이싱의 다중
  반사·회절·3D 각도는 포함되지 않아 K-factor 분포와 NLOS grid의 path 전력 분포가
  다를 수 있다. `reflection_loss_db_range`, `num_scatterers`, `scatterer_visibility`,
  `obstacles_m`로 조정 가능하다.
- 방식 3의 LOS 방향은 grid 좌표에서 계산한 이상값이다. 실제 위치 오차가 있으면
  LOS grid에서도 이보다 나빠진다.

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

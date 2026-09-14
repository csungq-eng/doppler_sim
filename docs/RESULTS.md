# Doppler 방식 비교 결과 (방식 1 기준 NMSE)

- 실험 일자: 2026-09-14, CI run [34857068499](https://github.com/csungq-eng/doppler_sim/actions/runs/34857068499)
- 입력 데이터 두 종류 (모두 per-antenna-pair 모드, grid 100개, BS 64 × UE 4,
  path 3~10개, seed 2026):
  - **random**: AoA 전방위 uniform, pair마다 독립인 path 집합 (기하 정보 없음)
  - **geometric**: 기지국·grid·산란체 위치에서 계산한 LOS + 단일 반사 path
    (실제 레이트레이싱 모사). LOS AoA가 기지국 방향과 일치, K-factor 평균 7.8 dB
    (LOS 전력 84%), 산란체 15개를 전 grid 공유, pair 간에는 element 위치에 따른
    tau 차이만 존재. 자세한 정의는 [README](../README.md#생성-시나리오) 참조.
- OFDM: fc 3.5 GHz, SCS 15 kHz, subcarrier 3276개 → H는 64 × 4 × 3276
- 단말 이동성: 방향 45°, snapshot t = 1 ms, 속도 0 / 60 / 120 km/h
  (최대 Doppler: 0 / 194.6 / 389.2 Hz)
- 지표: **NMSE = ‖H_x − H₁‖² / ‖H₁‖²** — 방식 1(모든 path에 path별 Doppler
  적용)을 reference로 하며, 낮을수록 좋음. 표 값은 100개 grid 평균(dB).

## 방식 요약

| 방식 | 내용 |
|---|---|
| 1 (기준) | 각 path에 Doppler 적용 후 주파수 채널 변환 |
| 2 | power 상위 dominant N개 path만으로 채널 구성(나머지 제외) + path별 Doppler |
| 3 | Doppler 없이 주파수 변환 후, LOS 방향(grid→기지국 방위각을 AoA로 가정) 단일 Doppler로 전체 행렬 위상 회전 |

## 결과 표 (평균 NMSE [dB])

| N (방식 2) | random v=0 | random v=60 | random v=120 | geometric v=0 | geometric v=60 | geometric v=120 |
|---|---|---|---|---|---|---|
| 1 | −2.14 | −2.12 | −2.11 | −8.05 | −8.04 | −8.05 |
| 2 | −4.13 | −4.12 | −4.10 | −10.21 | −10.21 | −10.21 |
| 3 | −6.26 | −6.26 | −6.26 | −12.05 | −12.05 | −12.05 |
| 4 | −8.45 | −8.43 | −8.43 | −13.87 | −13.87 | −13.88 |
| 5 | −10.79 | −10.79 | −10.78 | −15.69 | −15.69 | −15.69 |
| 6 | −13.43 | −13.43 | −13.42 | −17.63 | −17.63 | −17.63 |
| 7 | −16.55 | −16.56 | −16.54 | −19.97 | −19.97 | −19.97 |
| 8 | −20.53 | −20.53 | −20.52 | −23.01 | −23.01 | −23.01 |
| 9 | −26.35 | −26.34 | −26.33 | −27.66 | −27.67 | −27.67 |
| 10 | 정확히 일치* | 정확히 일치* | 정확히 일치* | 정확히 일치* | 정확히 일치* | 정확히 일치* |
| **방식 3** | **정확히 일치** | **+0.55** | **+3.02** | **정확히 일치** | **−10.86** | **−7.15** |

\* N = 10은 최대 path 수라 방식 2 == 방식 1 (−318 dB = 수치 오차 수준).
방식 3의 "정확히 일치"는 v = 0이면 Doppler 회전이 없어 방식 1과 같아지기 때문.

최악 grid 기준(최대 NMSE):

| | random v=60 | random v=120 | geometric v=60 | geometric v=120 |
|---|---|---|---|---|
| 방식 2, N=1 | −1.87 | −1.87 | −5.02 | −5.11 |
| 방식 2, N=3 | −5.79 | −5.81 | −7.84 | −7.85 |
| 방식 3 | +2.08 | +3.30 | −5.20 | −1.49 |

## 곡선

| | v = 0 km/h | v = 60 km/h | v = 120 km/h |
|---|---|---|---|
| random | ![](img/nmse_sweep_v0.png) | ![](img/nmse_sweep_v60.png) | ![](img/nmse_sweep_v120.png) |
| geometric | ![](img/nmse_sweep_geo_v0.png) | ![](img/nmse_sweep_geo_v60.png) | ![](img/nmse_sweep_geo_v120.png) |

원본 수치: `img/nmse_sweep_v{0,60,120}.csv`, `img/nmse_sweep_geo_v{0,60,120}.csv`

## 해석

### 방식 2: 오차는 속도와 무관, 버려진 path 전력이 결정

두 데이터 모두 방식 2의 NMSE는 속도에 따라 소수점 둘째 자리까지 거의 변하지
않는다. v = 0(Doppler 없음)에서도 같은 값이므로 오차는 Doppler 근사가 아니라
**path 제외(truncation) 자체**이며, NMSE ≈ 제외된 전력 비율이라는 근사가 전
구간에서 성립한다.

geometric 데이터는 전력이 LOS에 집중되어 있어(LOS 84%) 같은 N에서 random보다
훨씬 낮다: N = 1이면 −8.0 dB(≈ NLOS 전력 16%), N = 3이면 −12.1 dB. random
데이터에서는 N = 1이 −2.1 dB에 불과했다.

### 방식 3: 데이터의 LOS 정합 여부가 결정적

**random 데이터에서 방식 3은 보정을 안 한 것보다 나쁘다** (60 km/h +0.55 dB,
120 km/h +3.02 dB, 100개 grid 전부 −6 dB 이상). AoA가 전방위 uniform이라
"LOS 방향" 가정이 채널과 무상관이고, 잘못된 방향의 위상 회전이 오히려 오차를
키운다.

**geometric 데이터에서는 방식 3이 60 km/h에서 −10.9 dB, 120 km/h에서 −7.2 dB로
크게 개선된다** (최악 grid −5.2 / −1.5 dB, −6 dB보다 나쁜 grid는 100개 중 3개).
LOS path(전력 84%)의 Doppler는 방식 3의 단일 회전으로 정확히 보정되므로 남는
오차는 NLOS 성분(16%)의 Doppler 불일치뿐이다. 이 오차는 회전량에 비례해 속도와
함께 커진다: 60 km/h·1 ms에서 최대 0.19 사이클 → 120 km/h에서 0.39 사이클.
120 km/h의 −7.2 dB는 NLOS 전력(−8 dB)에 근접하는데, 이는 NLOS 성분의 위상이
LOS 기준으로 거의 무작위화되어 오차가 NLOS 전력 수준으로 포화되기 때문이다.
즉 **방식 3의 NMSE 하한은 대략 −(K-factor)이며, 속도가 빨라질수록 거기에
수렴한다.**

### 방식 2 vs 방식 3 (geometric 기준)

- 60 km/h: 방식 3(−10.9 dB)은 방식 2의 N = 2(−10.2)와 N = 3(−12.1) 사이.
  즉 path 정보 없이 LOS 방향만 알면 dominant 2~3개 path를 쓰는 것과 동급.
- 120 km/h: 방식 3(−7.2 dB)은 N = 1(−8.0)보다도 약간 나쁘다.
- 방식 2는 N을 늘리면 계속 좋아지지만(N = 4에서 −13.9 dB, N = 9에서 −27.7 dB),
  방식 3은 K-factor로 정해진 하한 아래로 내려갈 수 없다.

**결론: random 데이터의 "방식 3은 쓸모없다"는 결론은 데이터의 비현실성 때문이었다.
실제 레이트레이싱을 모사한 데이터에서는 방식 3이 저속(≤ 60 km/h)·높은 K-factor
환경에서 실용적인 근사(N = 2~3 수준)이지만, 고속이거나 NLOS 전력이 큰 환경에서는
dominant N ≥ 3개 path에 개별 Doppler를 적용하는 방식 2가 확실히 낫다.**

### 남은 한계

- geometric 데이터는 2D(azimuth) 단일 반사 모델이며 grid별 차폐가 독립 확률이다.
  실제 레이트레이싱은 다중 반사·회절·3D 각도를 포함하므로 K-factor 분포가 다를
  수 있다. `SimulationConfig`의 `reflection_loss_db_range`, `num_scatterers`,
  `scatterer_visibility`로 K-factor를 조정해 민감도를 볼 수 있다.
- 방식 3의 LOS 방향은 grid 좌표에서 계산한 이상값을 쓴다. 실제로는 위치 오차가
  있으므로 방식 3의 성능은 이보다 나빠진다.

## 재현 방법

[USAGE.md](USAGE.md) 참조. 요약: push하면 CI가 두 데이터 × 세 속도의 sweep을
자동 실행하고 `doppler-results` artifact(CSV + PNG)를 업로드한다. 로컬 재현은:

```bash
python generate_raytracing.py --geometric --per-pair
./build/poc_doppler --binary output_geo_per_pair/raytracing_result.bin \
    --speed-kmh 120 --direction-deg 45 --time-ms 1 --sweep-max 10 \
    --out-csv nmse_sweep_geo_v120.csv
python plot_sweep.py nmse_sweep_geo_v120.csv nmse_sweep_geo_v120.png \
    "geometric (ray-tracing-like) data, UE speed 120 km/h"
```

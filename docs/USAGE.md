# 실행 가이드

전체 파이프라인: **① Python으로 가상 레이트레이싱 binary 생성 → ② C++ PoC로
Doppler 적용 및 방식 1/2/3 NMSE·RSRP 오차 비교 → ③ N sweep / 심볼 sweep 곡선 생성**

로컬 PC에 C++ 컴파일러가 없어도 됩니다 — push하면 GitHub Actions가 전 과정을
자동 실행합니다. 아래에 (A) CI로 실행하는 방법과 (B) 로컬에서 직접 실행하는
방법을 모두 정리했습니다.

---

## A. GitHub Actions로 실행 (권장)

### 1. 실행

`main`에 push하면 [.github/workflows/ci.yml](../.github/workflows/ci.yml)이 자동 실행됩니다.
코드 수정 없이 다시 돌리려면 GitHub 리포 → Actions → CI → **Run workflow** 버튼을 누르면 됩니다.

CI 수행 순서:

1. Python 테스트 (`test_raytracing`, 86개)
2. binary 생성 — random 시나리오 per-pair(`output_per_pair/`)·per-grid(`output/`),
   geometric 시나리오(실제 레이트레이싱 모사) per-pair(`output_geo_per_pair/`)
3. CMake 빌드 (Release)
4. C++ 단위 테스트 + Python이 만든 binary 3개를 C++ 로더로 읽는 교차 검증
5. Doppler PoC 실행 (60 km/h, N=3 고정, grid별 NMSE) — random → `doppler_comparison.csv`,
   geometric → `doppler_comparison_geo.csv`
6. N sweep 실행 — 속도 0 / 60 / 120 km/h 각각 N=1..16, 두 데이터 모두
   → `nmse_sweep_v{0,60,120}.csv`(random), `nmse_sweep_geo_v{0,60,120}.csv`(geometric),
   각각 grid별 원자료 `*_grid.csv`. geometric 60 km/h는 방식 2 전력 재정규화 버전도
   실행 → `nmse_sweep_geo_v60_renorm.csv`
7. sweep 곡선 그림 생성 (같은 이름의 `.png`)
8. 심볼 sweep (geometric, 60/120 km/h, k = 0,1,2,4,7,14,28,56,140,280 심볼; 방식 2 N=3,
   재정규화 버전 1회 추가) → `symbol_sweep_geo_v{60,120}.csv/png`, `symbol_sweep_geo_v60_renorm.csv/png`
9. geometric 결과를 LOS grid / NLOS grid로 나눈 표 — NMSE와 RSRP 오차(전대역/협대역)
   (`los_split_geo_v{0,60,120}.md`)
10. 위 결과를 `doppler-results` artifact로 업로드

### 2. 파라미터 변경

[ci.yml](../.github/workflows/ci.yml)의 실행 스텝에서 옵션만 수정해 push합니다.

```yaml
- name: Run Doppler PoC
  run: ./build/poc_doppler --binary output_per_pair/raytracing_result.bin --speed-kmh 60 --direction-deg 45 --time-ms 1 --num-dominant 3
```

### 3. 결과 확인

- 콘솔 요약: Actions run 페이지 → build-and-test → "Run Doppler PoC (random/geometric)" / "Run N sweep ..." 스텝 로그
- 파일: run 페이지 하단 **Artifacts** → `doppler-results` 다운로드, 또는 CLI:

```powershell
gh run list --repo csungq-eng/doppler_sim --limit 3          # run id 확인
gh run download <run-id> --repo csungq-eng/doppler_sim -n doppler-results -D results
```

---

## B. 로컬에서 직접 실행

요구 사항: Python 3.x + numpy (+ 곡선 그림은 matplotlib), C++17 컴파일러 + CMake ≥ 3.16

### 1. binary 생성 (Python)

```powershell
python generate_raytracing.py --per-pair               # random,    mode 1 → output_per_pair/
python generate_raytracing.py                          # random,    mode 0 → output/
python generate_raytracing.py --geometric --per-pair   # geometric, mode 1 → output_geo_per_pair/
python generate_raytracing.py --geometric              # geometric, mode 0 → output_geo/
python -m unittest test_raytracing -v                  # 생성/포맷 검증 (86개)
```

`--geometric`은 기지국/grid/산란체/차폐 블록 위치로부터 LOS + 단일 반사 path를
계산하는 실제 레이트레이싱 모사 데이터다 (README "생성 시나리오" 참조). 블록 뒤
grid는 LOS가 없는 NLOS grid가 되므로 방식 3의 LOS 가정이 맞는 grid와 틀린 grid를
모두 평가할 수 있다.

### 2. C++ 빌드

```bash
cmake -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

### 3. 단위 테스트

```bash
# 수식/로직 테스트만
./build/unit_tests

# binary 로더 교차 검증 포함 (세 번째 인자: geometric per-pair → LOS AoA 규약 검증)
./build/unit_tests output_per_pair/raytracing_result.bin output/raytracing_result.bin \
    output_geo_per_pair/raytracing_result.bin
```

### 4. Doppler PoC 실행 (방식 1/2/3 비교)

```bash
./build/poc_doppler --binary output_per_pair/raytracing_result.bin \
    --speed-kmh 60 --direction-deg 45 --time-ms 1 --num-dominant 3
```

geometric 데이터로 실행하려면 `--binary output_geo_per_pair/raytracing_result.bin`을 준다.

| 옵션 | 기본값 | 의미 |
|---|---|---|
| `--binary <path>` | output_per_pair/raytracing_result.bin | 입력 binary (random 또는 geometric) |
| `--speed-kmh <v>` | 60 | 단말 이동 속도 [km/h] |
| `--direction-deg <d>` | 45 | 단말 이동 방향 azimuth [도] |
| `--time-ms <t>` | 1 | 채널 snapshot 시각 [ms] |
| `--time-symbols <k>` | – | snapshot 시각을 OFDM 심볼 수로 지정 (t = k·T_sym, `--time-ms` 대신) |
| `--scs-khz <s>` | 30 | subcarrier spacing [kHz]. T_sym = (2048+144)/(2048·SCS) = 35.7 µs @ 30 kHz |
| `--num-dominant <n>` | 3 | 방식 2에서 채널에 포함할 dominant path 수 |
| `--renorm-dominant` | off | 방식 2에서 포함한 path 전력 합을 1로 재정규화 (RSRP bias 제거) |
| `--rsrp-band-sc <n>` | 240 | 협대역 RSRP 측정 subcarrier 수 (대역 중앙; 240 = SSB 20 RB @ 30 kHz = 7.2 MHz) |
| `--out-csv <path>` | doppler_comparison.csv | grid별 결과 CSV |
| `--sweep-max <n>` | 0 (off) | N=1..n sweep 모드 (아래 5절) |
| `--symbol-list <a,b,..>` | – | 심볼 index 목록에 대한 시간 진행 sweep 모드 (아래 6절) |

출력: 콘솔에 처음 10개 grid + 평균/최대 NMSE(dB)와 RSRP 오차(전대역/협대역, dB),
전체 grid별 수치는 CSV.

지표 정의:
- **NMSE** = ‖H_x − H₁‖² / ‖H₁‖² — 위상 포함 오차
- **RSRP 오차** = (bs, ue) pair마다 subcarrier 평균 |H|²(= RSRP)의 비 `|10·log10(RSRP_x / RSRP₁)|`를
  pair 평균(`rsrp_*_err*`)·최대(`rsrp_*_max*`)로 요약. `wide` = 전대역 3276 SC, `band` = 대역 중앙
  `--rsrp-band-sc`개 SC

### 5. N sweep + 곡선

```bash
./build/poc_doppler --binary output_per_pair/raytracing_result.bin \
    --speed-kmh 60 --direction-deg 45 --time-ms 1 --sweep-max 16
python plot_sweep.py            # nmse_sweep.csv → nmse_sweep.png
```

sweep 모드는 grid마다 방식 1 채널(기준)을 한 번 만들고, N=1..sweep-max 각각의
방식 2 NMSE와 방식 3 NMSE(참고선)를 계산해 `nmse_sweep.csv`(grid 평균/최대 요약)와
`nmse_sweep_grid.csv`(grid별 원자료)에 저장합니다. `--out-csv`를 지정하면 그 이름으로
저장합니다 (CI는 속도별로 `nmse_sweep_v<속도>.csv` 사용; grid별 파일은 `_grid` 접미사).

geometric 데이터라면 grid별 파일을 LOS grid / NLOS grid로 나눠 볼 수 있습니다:

```bash
python summarize_los_split.py nmse_sweep_geo_v60_grid.csv output_geo_per_pair/config.json [out.md]
```

출력은 표 세 개입니다: N별 NMSE, RSRP 오차 전대역, RSRP 오차 협대역 — 각각
전체 / LOS grid / NLOS grid 열. 방식 3은 N과 무관하므로 마지막 행에 참고로 붙습니다.

방식 2의 RSRP bias를 없앤 버전을 보려면 `--renorm-dominant`를 붙여 sweep을 한 번 더
돌립니다 (CI도 geometric 60 km/h에 대해 같은 실행을 합니다):

```bash
./build/poc_doppler --binary output_geo_per_pair/raytracing_result.bin \
    --speed-kmh 60 --direction-deg 45 --time-ms 1 --sweep-max 16 --renorm-dominant \
    --out-csv nmse_sweep_geo_v60_renorm.csv
```

### 6. 심볼 sweep (시간 진행에 따른 오차)

"grid가 바뀌지 않는 한 같은 CIR에 매 심볼 Doppler를 반영"하는 실제 사용 방식에서
k번째 심볼의 오차를 본다. t = k·T_sym 로 두고 방식 2(N 고정)/방식 3의 NMSE와 RSRP 오차를
심볼 index별로 계산한다.

```bash
./build/poc_doppler --binary output_geo_per_pair/raytracing_result.bin \
    --speed-kmh 60 --direction-deg 45 --num-dominant 3 \
    --symbol-list 0,1,2,4,7,14,28,56,140,280 --out-csv symbol_sweep_geo_v60.csv
python plot_symbol_sweep.py symbol_sweep_geo_v60.csv symbol_sweep_geo_v60.png "geometric, 60 km/h"

# 방식 2 전력 재정규화 버전 (RSRP bias 비교용)
./build/poc_doppler --binary output_geo_per_pair/raytracing_result.bin \
    --speed-kmh 60 --num-dominant 3 --renorm-dominant \
    --symbol-list 0,1,2,4,7,14,28,56,140,280 --out-csv symbol_sweep_geo_v60_renorm.csv
```

그림은 두 패널: 왼쪽 NMSE vs k(로그축), 오른쪽 RSRP |오차| vs k (전대역 실선, 협대역 점선).
k = 0은 세 방식이 정확히 같아 NMSE = −∞이므로 NMSE 패널에서는 빠진다.

`plot_sweep.py` 인자 (모두 선택):

```bash
python plot_sweep.py [csv 경로] [png 경로] [부제목]
# 기본값: nmse_sweep.csv  nmse_sweep.png  (부제목 없음)

# 예: 속도별 sweep (CI와 동일)
./build/poc_doppler --binary output_per_pair/raytracing_result.bin \
    --speed-kmh 120 --direction-deg 45 --time-ms 1 --sweep-max 16 \
    --out-csv nmse_sweep_v120.csv
python plot_sweep.py nmse_sweep_v120.csv nmse_sweep_v120.png "UE speed 120 km/h"
```

---

## 결과 파일 설명

| 파일 | 내용 |
|---|---|
| `doppler_comparison.csv` (CI: geometric은 `doppler_comparison_geo.csv`) | grid별 방식 2/3 NMSE(선형 + dB)와 RSRP 오차. 열: grid_id, nmse_method2, nmse_method2_db, nmse_method3, nmse_method3_db, rsrp_wide_err2_db, rsrp_wide_err3_db, rsrp_band_err2_db, rsrp_band_err3_db, rsrp_wide_max2_db, rsrp_wide_max3_db, rsrp_band_max2_db, rsrp_band_max3_db |
| `nmse_sweep.csv` (CI: `nmse_sweep_v<속도>.csv`, `nmse_sweep_geo_v<속도>.csv`) | N별 방식 2 요약. 열: n_dominant, mean_nmse2, mean_nmse2_db, max_nmse2_db, mean_nmse3_db(참고, N 무관), max_nmse3_db, rsrp_wide_err2_db, rsrp_wide_err3_db, rsrp_band_err2_db, rsrp_band_err3_db |
| `nmse_sweep_grid.csv` (CI: `nmse_sweep_*_grid.csv`) | sweep의 grid별 원자료. 열: grid_id, n_dominant, nmse2, nmse3 (선형), rsrp_wide_err2_db, rsrp_wide_err3_db, rsrp_band_err2_db, rsrp_band_err3_db |
| `nmse_sweep.png` (CI: 위 CSV와 같은 이름의 `.png`) | 방식 2 NMSE vs N 곡선 (평균 실선, 최악 grid 점선, 방식 3 평균 기준선) |
| `los_split_geo_v<속도>.md` (CI) | geometric 데이터의 N별·방식 3 평균 NMSE와 RSRP 오차(전대역/협대역)를 전체/LOS/NLOS grid로 나눈 표 |
| `symbol_sweep.csv` (CI: `symbol_sweep_geo_v<속도>[_renorm].csv`) | 심볼 index별 결과. 열: symbol, t_ms, nmse2_db, nmse3_db, max_nmse2_db, max_nmse3_db, rsrp_wide_err2_db, rsrp_wide_err3_db, rsrp_band_err2_db, rsrp_band_err3_db, rsrp_wide_max2_db, rsrp_wide_max3_db, rsrp_band_max2_db, rsrp_band_max3_db (grid 평균; max는 최악 pair) |
| `symbol_sweep.png` | 위 CSV의 두 패널 곡선 |

NMSE는 항상 방식 1(모든 path에 Doppler 적용)을 reference로 한
`‖H_x − H₁‖² / ‖H₁‖²` 이며, 낮을수록 방식 1에 가깝다는 뜻입니다.

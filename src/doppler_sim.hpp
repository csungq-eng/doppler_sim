// Doppler 효과 적용 + 주파수 도메인 채널 행렬 생성.
//
// 세 가지 방식을 비교한다 (모두 snapshot 시각 t에서의 채널):
//   방식 1: 각 path에 doppler 적용 후 주파수 채널 변환 (기준)
//     H[b][u][k] = sum_p sqrt(P_p) * exp(-j*2pi*fc*tau_p)          .. path 위상
//                        * exp(+j*2pi*fd_p*t)                      .. doppler 회전
//                        * exp(-j*2pi*f_k*tau_p)                   .. 주파수 응답
//     fd_p = (v/lambda) * cos(aoa_p - 이동방향),  f_k = (k - Nsc/2) * SCS
//   방식 2: power 상위 dominant N개 path만으로 채널 구성(나머지 제외),
//           포함된 path에는 방식 1과 동일하게 doppler 적용
//   방식 3: doppler 없이 주파수 채널 변환 후, LOS 방향(단말->기지국 상대
//           벡터의 방위각을 AoA로 가정) 단일 doppler로 행렬 전체를 회전
//
// 각도 규약: 방위각은 +x축 기준 반시계 [도]. AoA는 단말에서 전파가 들어오는
// 쪽을 가리키므로 LOS AoA = 단말->기지국 방향이고, 그쪽으로 이동하면 fd > 0.
#pragma once

#include <complex>
#include <cstdint>
#include <vector>

#include "rt_loader.hpp"

namespace sim {

struct Params {
  // OFDM 파라미터
  double fc_hz = 3.5e9;    // center frequency
  double scs_hz = 30e3;    // subcarrier spacing (3276 SC = 273 RB @ 30 kHz, 100 MHz)
  uint32_t num_sc = 3276;  // subcarrier 수

  // 단말 이동성
  double speed_mps = 60.0 / 3.6;  // 이동 속도 [m/s] (기본 60 km/h)
  double move_dir_deg = 45.0;     // 이동 방향 (azimuth) [도]
  double time_s = 1e-3;           // 채널 snapshot 시각 [초]

  // 방식 2: 채널에 포함할 dominant path 수
  uint32_t num_dominant = 3;
  // 방식 2: 포함한 path의 전력 합이 1이 되도록 재정규화 (RSRP bias 제거용)
  bool renorm_dominant = false;

  // RSRP 측정 대역 (대역 중앙의 subcarrier 수). 기본 240 = SSB 20 RB
  uint32_t rsrp_band_sc = 240;

  // OFDM 심볼 길이 [초] (normal CP, 2048+144 샘플 기준). --time-symbols 환산용
  double symbol_duration_s() const { return (2048.0 + 144.0) / (2048.0 * scs_hz); }

  // 방식 3: 기지국/grid 위치 (grid는 row-major 정사각 배치로 가정).
  // Python SimulationConfig의 geometric 파라미터 기본값과 같아야 한다.
  double bs_x_m = 0.0;
  double bs_y_m = 0.0;
  double grid_origin_x_m = 50.0;   // grid 0의 위치
  double grid_origin_y_m = -45.0;
  double grid_spacing_m = 10.0;
  uint32_t grid_cols = 10;
};

// 주파수 채널 행렬. index = (bs_ant * num_ue_ant + ue_ant) * num_sc + sc
using CMat = std::vector<std::complex<double>>;

// path AoA에 대한 doppler 주파수 [Hz]
double doppler_shift_hz(double aoa_deg, const Params& p);

// grid의 (x, y) 위치
void grid_position(uint32_t grid_id, const Params& p, double* x, double* y);

// grid -> 기지국 상대 벡터의 azimuth [도] = LOS 도래각 (방식 3에서 AoA로 가정)
double los_angle_deg(uint32_t grid_id, const Params& p);

CMat method1_per_path_doppler(const rt::Result& r, const rt::Grid& g,
                              const Params& p);
CMat method2_dominant_doppler(const rt::Result& r, const rt::Grid& g,
                              const Params& p);
CMat method3_post_fd_doppler(const rt::Result& r, const rt::Grid& g,
                             const Params& p);

// NMSE = ||x - ref||^2 / ||ref||^2
double nmse(const CMat& ref, const CMat& x);

// RSRP 오차: (bs, ue) pair마다 subcarrier 구간 [sc_begin, sc_begin + sc_len)의
// 평균 |H|^2를 RSRP로 보고, 10*log10(RSRP_x / RSRP_ref)의 절댓값을 pair 평균/최대로 요약.
struct RsrpError {
  double mean_abs_db;  // pair 평균 |오차| [dB]
  double max_abs_db;   // 최악 pair |오차| [dB]
};
RsrpError rsrp_error(const CMat& ref, const CMat& x, const rt::Result& r,
                     const Params& p, uint32_t sc_begin, uint32_t sc_len);
// 전대역 / 대역 중앙 rsrp_band_sc 구간에 대한 편의 함수
RsrpError rsrp_error_wideband(const CMat& ref, const CMat& x, const rt::Result& r,
                              const Params& p);
RsrpError rsrp_error_band(const CMat& ref, const CMat& x, const rt::Result& r,
                          const Params& p);

}  // namespace sim

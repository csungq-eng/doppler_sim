// Doppler 효과 적용 + 주파수 도메인 채널 행렬 생성.
//
// 세 가지 방식을 비교한다 (모두 snapshot 시각 t에서의 채널):
//   방식 1: 각 path에 doppler 적용 후 주파수 채널 변환 (기준)
//     H[b][u][k] = sum_p sqrt(P_p) * exp(-j*2pi*fc*tau_p)          .. path 위상
//                        * exp(+j*2pi*fd_p*t)                      .. doppler 회전
//                        * exp(-j*2pi*f_k*tau_p)                   .. 주파수 응답
//     fd_p = (v/lambda) * cos(aoa_p - 이동방향),  f_k = (k - Nsc/2) * SCS
//   방식 2: dominant N개 path에만 doppler 적용 (나머지 path는 fd = 0)
//   방식 3: doppler 없이 주파수 채널 변환 후, LOS 방향(기지국->단말 상대
//           벡터를 AoA로 가정) 단일 doppler로 행렬 전체를 회전
#pragma once

#include <complex>
#include <cstdint>
#include <vector>

#include "rt_loader.hpp"

namespace sim {

struct Params {
  // OFDM 파라미터
  double fc_hz = 3.5e9;    // center frequency
  double scs_hz = 15e3;    // subcarrier spacing
  uint32_t num_sc = 3276;  // subcarrier 수

  // 단말 이동성
  double speed_mps = 60.0 / 3.6;  // 이동 속도 [m/s] (기본 60 km/h)
  double move_dir_deg = 45.0;     // 이동 방향 (azimuth) [도]
  double time_s = 1e-3;           // 채널 snapshot 시각 [초]

  // 방식 2: doppler를 적용할 dominant path 수
  uint32_t num_dominant = 3;

  // 방식 3: 기지국/grid 위치 (grid는 row-major 정사각 배치로 가정)
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

// 기지국 -> grid 상대 벡터의 azimuth [도] (방식 3에서 AoA로 가정)
double los_angle_deg(uint32_t grid_id, const Params& p);

CMat method1_per_path_doppler(const rt::Result& r, const rt::Grid& g,
                              const Params& p);
CMat method2_dominant_doppler(const rt::Result& r, const rt::Grid& g,
                              const Params& p);
CMat method3_post_fd_doppler(const rt::Result& r, const rt::Grid& g,
                             const Params& p);

// NMSE = ||x - ref||^2 / ||ref||^2
double nmse(const CMat& ref, const CMat& x);

}  // namespace sim

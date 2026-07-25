#include "doppler_sim.hpp"

#include <algorithm>
#include <cmath>
#include <numeric>

namespace sim {
namespace {

constexpr double kC = 299792458.0;  // 광속 [m/s]
constexpr double kPi = 3.14159265358979323846;

std::complex<double> phasor(double phase_rad) {
  return {std::cos(phase_rad), std::sin(phase_rad)};
}

// 하나의 path 집합을 채널 행렬의 (bs, ue) 위치에 누적한다.
// fd_hz[i]는 paths[i]에 적용할 doppler 주파수.
void accumulate_pair(CMat& h, size_t offset, const std::vector<rt::Path>& paths,
                     const std::vector<double>& fd_hz, const Params& p) {
  for (size_t i = 0; i < paths.size(); ++i) {
    const rt::Path& path = paths[i];
    // path 복소 계수: 진폭 + carrier 위상 + doppler 회전
    std::complex<double> a =
        std::sqrt(path.power) *
        phasor(-2.0 * kPi * p.fc_hz * path.tau_s +
               2.0 * kPi * fd_hz[i] * p.time_s);
    // f_k = (k - Nsc/2) * SCS 에 대해 exp(-j*2pi*f_k*tau)를 점화식으로 계산
    double f0 = -0.5 * static_cast<double>(p.num_sc) * p.scs_hz;
    std::complex<double> cur = phasor(-2.0 * kPi * f0 * path.tau_s);
    std::complex<double> step = phasor(-2.0 * kPi * p.scs_hz * path.tau_s);
    for (uint32_t k = 0; k < p.num_sc; ++k) {
      h[offset + k] += a * cur;
      cur *= step;
    }
  }
}

// doppler 주파수를 path마다 뽑는 함수를 받아 전체 채널 행렬을 생성한다.
template <typename FdSelector>
CMat build_channel(const rt::Result& r, const rt::Grid& g, const Params& p,
                   FdSelector select_fd) {
  CMat h(static_cast<size_t>(r.num_bs_ant) * r.num_ue_ant * p.num_sc,
         {0.0, 0.0});
  for (uint32_t b = 0; b < r.num_bs_ant; ++b) {
    for (uint32_t u = 0; u < r.num_ue_ant; ++u) {
      const std::vector<rt::Path>& paths = r.paths_for(g, b, u);
      std::vector<double> fd = select_fd(paths);
      size_t offset =
          (static_cast<size_t>(b) * r.num_ue_ant + u) * p.num_sc;
      accumulate_pair(h, offset, paths, fd, p);
    }
  }
  return h;
}

// power 기준 상위 num_dominant개 path의 index 집합 여부를 반환
std::vector<bool> dominant_mask(const std::vector<rt::Path>& paths,
                                uint32_t num_dominant) {
  std::vector<size_t> idx(paths.size());
  std::iota(idx.begin(), idx.end(), 0);
  std::sort(idx.begin(), idx.end(), [&](size_t a, size_t b) {
    return paths[a].power > paths[b].power;
  });
  std::vector<bool> mask(paths.size(), false);
  for (size_t i = 0; i < idx.size() && i < num_dominant; ++i) {
    mask[idx[i]] = true;
  }
  return mask;
}

}  // namespace

double doppler_shift_hz(double aoa_deg, const Params& p) {
  double lambda = kC / p.fc_hz;
  double angle_rad = (aoa_deg - p.move_dir_deg) * kPi / 180.0;
  return p.speed_mps / lambda * std::cos(angle_rad);
}

void grid_position(uint32_t grid_id, const Params& p, double* x, double* y) {
  *x = p.grid_origin_x_m + (grid_id % p.grid_cols) * p.grid_spacing_m;
  *y = p.grid_origin_y_m + (grid_id / p.grid_cols) * p.grid_spacing_m;
}

double los_angle_deg(uint32_t grid_id, const Params& p) {
  double x, y;
  grid_position(grid_id, p, &x, &y);
  return std::atan2(y - p.bs_y_m, x - p.bs_x_m) * 180.0 / kPi;
}

CMat method1_per_path_doppler(const rt::Result& r, const rt::Grid& g,
                              const Params& p) {
  return build_channel(r, g, p, [&](const std::vector<rt::Path>& paths) {
    std::vector<double> fd(paths.size());
    for (size_t i = 0; i < paths.size(); ++i) {
      fd[i] = doppler_shift_hz(paths[i].aoa_deg, p);
    }
    return fd;
  });
}

CMat method2_dominant_doppler(const rt::Result& r, const rt::Grid& g,
                              const Params& p) {
  return build_channel(r, g, p, [&](const std::vector<rt::Path>& paths) {
    std::vector<bool> mask = dominant_mask(paths, p.num_dominant);
    std::vector<double> fd(paths.size(), 0.0);
    for (size_t i = 0; i < paths.size(); ++i) {
      if (mask[i]) fd[i] = doppler_shift_hz(paths[i].aoa_deg, p);
    }
    return fd;
  });
}

CMat method3_post_fd_doppler(const rt::Result& r, const rt::Grid& g,
                             const Params& p) {
  // doppler 없이 주파수 채널 변환
  CMat h = build_channel(r, g, p, [](const std::vector<rt::Path>& paths) {
    return std::vector<double>(paths.size(), 0.0);
  });
  // LOS 방향(기지국->grid 상대 벡터) 단일 doppler로 행렬 전체 회전
  double fd = doppler_shift_hz(los_angle_deg(g.grid_id, p), p);
  std::complex<double> rot = phasor(2.0 * kPi * fd * p.time_s);
  for (std::complex<double>& v : h) v *= rot;
  return h;
}

double nmse(const CMat& ref, const CMat& x) {
  double err = 0.0, denom = 0.0;
  for (size_t i = 0; i < ref.size(); ++i) {
    err += std::norm(x[i] - ref[i]);
    denom += std::norm(ref[i]);
  }
  return err / denom;
}

}  // namespace sim

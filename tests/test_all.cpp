// C++ 구현 단위 테스트.
//
// 실행: unit_tests [per_pair.bin] [per_grid.bin]
//   인자로 binary 파일 경로를 주면 로더 검증도 수행한다 (CI에서 사용).
//   인자가 없으면 수식/로직 테스트만 수행한다.

#include <algorithm>
#include <cmath>
#include <complex>
#include <cstdio>
#include <string>
#include <vector>

#include "doppler_sim.hpp"
#include "rt_loader.hpp"

namespace {

int failures = 0;

#define CHECK(cond, msg)                                    \
  do {                                                      \
    if (cond) {                                             \
      std::printf("[PASS] %s\n", msg);                      \
    } else {                                                \
      std::printf("[FAIL] %s (%s:%d)\n", msg, __FILE__, __LINE__); \
      ++failures;                                           \
    }                                                       \
  } while (0)

constexpr double kPi = 3.14159265358979323846;

// 1x1 안테나, path 하나짜리 결과를 만든다 (per-pair mode).
rt::Result make_single_pair_result(const std::vector<rt::Path>& paths,
                                   uint32_t grid_id = 0) {
  rt::Result r;
  r.mode = rt::kPerPair;
  r.num_bs_ant = 1;
  r.num_ue_ant = 1;
  rt::Grid g;
  g.grid_id = grid_id;
  g.pairs.push_back({0, 0, paths});
  r.grids.push_back(g);
  return r;
}

sim::Params small_params() {
  sim::Params p;
  p.num_sc = 16;  // 테스트는 작은 채널로 충분
  return p;
}

// 방식 1 수식을 점화식 없이 직접 계산한 참값과 비교
void test_method1_against_direct_formula() {
  std::vector<rt::Path> paths = {
      {0, 0.7, 30.0, -10.0, 500e-9},
      {1, 0.3, -120.0, 20.0, 800e-9},
  };
  rt::Result r = make_single_pair_result(paths);
  sim::Params p = small_params();

  sim::CMat h = sim::method1_per_path_doppler(r, r.grids[0], p);

  double max_err = 0.0;
  for (uint32_t k = 0; k < p.num_sc; ++k) {
    std::complex<double> expected{0.0, 0.0};
    for (const rt::Path& path : paths) {
      double fd = sim::doppler_shift_hz(path.aoa_deg, p);
      double fk = (static_cast<double>(k) - 0.5 * p.num_sc) * p.scs_hz;
      double phase = -2.0 * kPi * p.fc_hz * path.tau_s +
                     2.0 * kPi * fd * p.time_s - 2.0 * kPi * fk * path.tau_s;
      expected += std::sqrt(path.power) *
                  std::complex<double>(std::cos(phase), std::sin(phase));
    }
    max_err = std::max(max_err, std::abs(h[k] - expected));
  }
  CHECK(max_err < 1e-9, "방식 1이 직접 계산한 수식 참값과 일치");
}

void test_doppler_shift_formula() {
  sim::Params p;
  p.speed_mps = 30.0;
  p.move_dir_deg = 0.0;
  double lambda = 299792458.0 / p.fc_hz;
  double fmax = p.speed_mps / lambda;
  CHECK(std::abs(sim::doppler_shift_hz(0.0, p) - fmax) < 1e-9,
        "이동 방향과 같은 AoA는 +f_max");
  CHECK(std::abs(sim::doppler_shift_hz(180.0, p) + fmax) < 1e-9,
        "이동 방향과 반대 AoA는 -f_max");
  CHECK(std::abs(sim::doppler_shift_hz(90.0, p)) < 1e-9,
        "이동 방향과 수직 AoA는 doppler 0");
}

void test_method2_equals_method1_when_n_large() {
  std::vector<rt::Path> paths = {
      {0, 0.5, 10.0, 0.0, 400e-9},
      {1, 0.3, 100.0, 0.0, 600e-9},
      {2, 0.2, -60.0, 0.0, 900e-9},
  };
  rt::Result r = make_single_pair_result(paths);
  sim::Params p = small_params();
  p.num_dominant = 100;  // 모든 path에 doppler 적용 -> 방식 1과 동일해야 함

  sim::CMat h1 = sim::method1_per_path_doppler(r, r.grids[0], p);
  sim::CMat h2 = sim::method2_dominant_doppler(r, r.grids[0], p);
  CHECK(sim::nmse(h1, h2) < 1e-24, "N >= path 수이면 방식 2 == 방식 1");
}

void test_method2_zero_dominant_equals_no_doppler() {
  std::vector<rt::Path> paths = {
      {0, 0.6, 45.0, 0.0, 300e-9},
      {1, 0.4, -45.0, 0.0, 700e-9},
  };
  rt::Result r = make_single_pair_result(paths);
  sim::Params p = small_params();
  p.num_dominant = 0;

  sim::CMat h2 = sim::method2_dominant_doppler(r, r.grids[0], p);
  sim::Params p0 = p;
  p0.speed_mps = 0.0;  // doppler 자체가 없는 채널
  sim::CMat h_static = sim::method1_per_path_doppler(r, r.grids[0], p0);
  CHECK(sim::nmse(h_static, h2) < 1e-24, "N = 0이면 방식 2는 doppler 없는 채널");
}

void test_method3_equals_method1_for_single_los_path() {
  sim::Params p = small_params();
  uint32_t grid_id = 7;
  // path AoA를 grid의 LOS 방향과 일치시키면 방식 1과 방식 3이 같아야 한다
  std::vector<rt::Path> paths = {
      {0, 1.0, sim::los_angle_deg(grid_id, p), 0.0, 450e-9},
  };
  rt::Result r = make_single_pair_result(paths, grid_id);

  sim::CMat h1 = sim::method1_per_path_doppler(r, r.grids[0], p);
  sim::CMat h3 = sim::method3_post_fd_doppler(r, r.grids[0], p);
  CHECK(sim::nmse(h1, h3) < 1e-24, "LOS 단일 path이면 방식 3 == 방식 1");
}

void test_all_methods_equal_at_t0() {
  std::vector<rt::Path> paths = {
      {0, 0.5, 20.0, 0.0, 350e-9},
      {1, 0.5, 160.0, 0.0, 650e-9},
  };
  rt::Result r = make_single_pair_result(paths);
  sim::Params p = small_params();
  p.time_s = 0.0;  // t = 0이면 doppler 회전이 없어 세 방식 모두 동일

  sim::CMat h1 = sim::method1_per_path_doppler(r, r.grids[0], p);
  sim::CMat h2 = sim::method2_dominant_doppler(r, r.grids[0], p);
  sim::CMat h3 = sim::method3_post_fd_doppler(r, r.grids[0], p);
  CHECK(sim::nmse(h1, h2) < 1e-24 && sim::nmse(h1, h3) < 1e-24,
        "t = 0이면 세 방식 모두 동일");
}

void test_loader(const std::string& path, rt::Mode expected_mode) {
  rt::Result r = rt::load(path);
  CHECK(r.mode == expected_mode, "로더: mode가 기대값과 일치");
  CHECK(r.num_bs_ant == 64 && r.num_ue_ant == 4, "로더: 안테나 수 64 x 4");
  CHECK(r.grids.size() == 100, "로더: grid 100개");

  bool power_ok = true, pairs_ok = true;
  for (const rt::Grid& g : r.grids) {
    if (expected_mode == rt::kPerPair && g.pairs.size() != 64 * 4) {
      pairs_ok = false;
    }
    for (uint32_t b = 0; b < r.num_bs_ant && power_ok; ++b) {
      for (uint32_t u = 0; u < r.num_ue_ant && power_ok; ++u) {
        const std::vector<rt::Path>& paths = r.paths_for(g, b, u);
        double sum = 0.0;
        for (const rt::Path& path : paths) sum += path.power;
        if (std::abs(sum - 1.0) > 1e-9 || paths.empty()) power_ok = false;
      }
    }
  }
  if (expected_mode == rt::kPerPair) {
    CHECK(pairs_ok, "로더: grid마다 pair 64 x 4개");
  }
  CHECK(power_ok, "로더: 모든 path 집합의 전력 합 = 1");
}

}  // namespace

int main(int argc, char** argv) {
  test_method1_against_direct_formula();
  test_doppler_shift_formula();
  test_method2_equals_method1_when_n_large();
  test_method2_zero_dominant_equals_no_doppler();
  test_method3_equals_method1_for_single_los_path();
  test_all_methods_equal_at_t0();

  if (argc > 1) {
    std::printf("-- 로더 검증: %s (per-pair)\n", argv[1]);
    test_loader(argv[1], rt::kPerPair);
  }
  if (argc > 2) {
    std::printf("-- 로더 검증: %s (per-grid)\n", argv[2]);
    test_loader(argv[2], rt::kPerGrid);
  }

  if (failures == 0) {
    std::printf("\n모든 테스트 통과\n");
    return 0;
  }
  std::printf("\n%d개 테스트 실패\n", failures);
  return 1;
}

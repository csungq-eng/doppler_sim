// C++ 구현 단위 테스트.
//
// 실행: unit_tests [per_pair.bin] [per_grid.bin] [geo_per_pair.bin]
//   인자로 binary 파일 경로를 주면 로더 검증도 수행한다 (CI에서 사용).
//   세 번째 인자는 geometric 시나리오 per-pair binary로, 로더 검증에 더해
//   LOS AoA가 C++의 los_angle_deg와 같은 규약인지 확인한다.
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

void test_method2_keeps_only_dominant_paths() {
  // 강한 path 1개 + 약한 path 1개. N = 1이면 강한 path만으로 만든
  // 채널(방식 1)과 정확히 같아야 한다 (약한 path는 완전히 제외).
  rt::Path strong = {0, 0.9, 45.0, 0.0, 300e-9};
  rt::Path weak = {1, 0.1, -45.0, 0.0, 700e-9};
  rt::Result r_both = make_single_pair_result({strong, weak});
  rt::Result r_strong_only = make_single_pair_result({strong});
  sim::Params p = small_params();
  p.num_dominant = 1;

  sim::CMat h2 = sim::method2_dominant_doppler(r_both, r_both.grids[0], p);
  sim::CMat h_ref =
      sim::method1_per_path_doppler(r_strong_only, r_strong_only.grids[0], p);
  CHECK(sim::nmse(h_ref, h2) < 1e-24,
        "방식 2는 dominant path만 포함 (나머지 제외)");

  // N = 0이면 채널이 완전히 비어야 한다
  p.num_dominant = 0;
  sim::CMat h_empty = sim::method2_dominant_doppler(r_both, r_both.grids[0], p);
  double energy = 0.0;
  for (const std::complex<double>& v : h_empty) energy += std::norm(v);
  CHECK(energy == 0.0, "N = 0이면 방식 2 채널은 0");
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

void test_los_angle_points_from_grid_to_bs() {
  // grid 0 = (50, -45), 기지국 = 원점 → 단말->기지국 방향은 제2사분면(180 - 42°)
  sim::Params p;
  double expected = std::atan2(45.0, -50.0) * 180.0 / kPi;
  CHECK(std::abs(sim::los_angle_deg(0, p) - expected) < 1e-9,
        "LOS 각도는 grid->기지국 방향 (도래각 규약)");
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
  test_method2_keeps_only_dominant_paths();
  test_method3_equals_method1_for_single_los_path();
  test_los_angle_points_from_grid_to_bs();
  test_all_methods_equal_at_t0();

  if (argc > 1) {
    std::printf("-- 로더 검증: %s (per-pair)\n", argv[1]);
    test_loader(argv[1], rt::kPerPair);
  }
  if (argc > 2) {
    std::printf("-- 로더 검증: %s (per-grid)\n", argv[2]);
    test_loader(argv[2], rt::kPerGrid);
  }
  if (argc > 3) {
    std::printf("-- 로더 검증: %s (geometric per-pair)\n", argv[3]);
    test_loader(argv[3], rt::kPerPair);
    // Python 생성기의 LOS AoA(첫 path)와 C++ los_angle_deg가 같은 규약인지 확인.
    // 차폐 블록 뒤 NLOS grid에는 LOS path가 없으므로, 첫 path의 tau가 기지국-grid
    // 거리/c와 일치하는 grid(LOS grid)만 검사한다. per-pair binary의 pair (0,0)은
    // 배열 중심에서 최대 ~1.5도, ~10 ns 벗어난다.
    rt::Result r = rt::load(argv[3]);
    sim::Params p;
    double max_err = 0.0;
    size_t n_los = 0, n_nlos = 0;
    for (const rt::Grid& g : r.grids) {
      double x, y;
      sim::grid_position(g.grid_id, p, &x, &y);
      double tau_los = std::hypot(x - p.bs_x_m, y - p.bs_y_m) / 299792458.0;
      const rt::Path& first = r.paths_for(g, 0, 0)[0];
      if (std::abs(first.tau_s - tau_los) < 20e-9) {
        ++n_los;
        max_err = std::max(
            max_err, std::abs(first.aoa_deg - sim::los_angle_deg(g.grid_id, p)));
      } else {
        ++n_nlos;
      }
    }
    CHECK(n_los > 0 && n_nlos > 0,
          "geometric 데이터에 LOS grid와 NLOS grid가 모두 존재");
    CHECK(max_err < 3.0,
          "geometric 데이터의 LOS AoA가 방식 3의 LOS 방향과 일치 (규약 동일)");
  }

  if (failures == 0) {
    std::printf("\n모든 테스트 통과\n");
    return 0;
  }
  std::printf("\n%d개 테스트 실패\n", failures);
  return 1;
}

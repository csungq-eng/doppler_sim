// Doppler PoC 메인.
//
// binary 레이트레이싱 결과를 읽어, grid마다 세 가지 방식으로
// 주파수 도메인 채널 행렬(64 x 4 x 3276)을 생성하고 NMSE로 비교한다.
//   방식 1 (기준): path별 doppler 적용 후 주파수 변환
//   방식 2: dominant N개 path에만 doppler 적용
//   방식 3: 주파수 변환 후 LOS 방향 단일 doppler 적용
//
// 사용 예:
//   poc_doppler --binary output_per_pair/raytracing_result.bin \
//               --speed-kmh 60 --direction-deg 45 --time-ms 1 --num-dominant 3

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

#include "doppler_sim.hpp"
#include "rt_loader.hpp"

namespace {

double to_db(double x) { return 10.0 * std::log10(x); }

void print_usage(const char* prog) {
  std::printf(
      "사용법: %s [옵션]\n"
      "  --binary <path>       입력 binary (기본 output_per_pair/raytracing_result.bin)\n"
      "  --speed-kmh <v>       단말 이동 속도 [km/h] (기본 60)\n"
      "  --direction-deg <d>   단말 이동 방향 azimuth [도] (기본 45)\n"
      "  --time-ms <t>         채널 snapshot 시각 [ms] (기본 1)\n"
      "  --num-dominant <n>    방식 2의 dominant path 수 (기본 3)\n"
      "  --out-csv <path>      grid별 NMSE 결과 CSV (기본 doppler_comparison.csv)\n",
      prog);
}

}  // namespace

int main(int argc, char** argv) {
  std::string binary_path = "output_per_pair/raytracing_result.bin";
  std::string csv_path = "doppler_comparison.csv";
  double speed_kmh = 60.0;
  sim::Params p;

  for (int i = 1; i < argc; ++i) {
    auto next = [&]() -> const char* {
      if (i + 1 >= argc) {
        std::fprintf(stderr, "옵션 %s에 값이 필요합니다\n", argv[i]);
        std::exit(1);
      }
      return argv[++i];
    };
    if (!std::strcmp(argv[i], "--binary")) binary_path = next();
    else if (!std::strcmp(argv[i], "--speed-kmh")) speed_kmh = std::atof(next());
    else if (!std::strcmp(argv[i], "--direction-deg")) p.move_dir_deg = std::atof(next());
    else if (!std::strcmp(argv[i], "--time-ms")) p.time_s = std::atof(next()) * 1e-3;
    else if (!std::strcmp(argv[i], "--num-dominant")) p.num_dominant = std::atoi(next());
    else if (!std::strcmp(argv[i], "--out-csv")) csv_path = next();
    else if (!std::strcmp(argv[i], "--help")) { print_usage(argv[0]); return 0; }
    else {
      std::fprintf(stderr, "알 수 없는 옵션: %s\n", argv[i]);
      print_usage(argv[0]);
      return 1;
    }
  }
  p.speed_mps = speed_kmh / 3.6;

  rt::Result r;
  try {
    r = rt::load(binary_path);
  } catch (const std::exception& e) {
    std::fprintf(stderr, "binary 로드 실패: %s\n", e.what());
    return 1;
  }

  double f_max = p.speed_mps / (299792458.0 / p.fc_hz);
  std::printf("=== Doppler PoC ===\n");
  std::printf("binary          : %s (mode %s, grid %zu개, BS %u x UE %u)\n",
              binary_path.c_str(),
              r.mode == rt::kPerPair ? "per-antenna-pair" : "per-grid",
              r.grids.size(), r.num_bs_ant, r.num_ue_ant);
  std::printf("OFDM            : fc %.2f GHz, SCS %.0f kHz, SC %u개\n",
              p.fc_hz / 1e9, p.scs_hz / 1e3, p.num_sc);
  std::printf("단말 이동성     : %.1f km/h, 방향 %.1f도, snapshot t = %.3f ms\n",
              speed_kmh, p.move_dir_deg, p.time_s * 1e3);
  std::printf("최대 doppler    : %.1f Hz\n", f_max);
  std::printf("방식 2 dominant : N = %u\n\n", p.num_dominant);

  std::ofstream csv(csv_path);
  csv << "grid_id,nmse_method2,nmse_method2_db,nmse_method3,nmse_method3_db\n";

  double sum2 = 0.0, sum3 = 0.0, max2 = 0.0, max3 = 0.0;
  std::printf("grid   NMSE 방식2[dB]   NMSE 방식3[dB]\n");
  for (size_t i = 0; i < r.grids.size(); ++i) {
    const rt::Grid& g = r.grids[i];
    sim::CMat h1 = sim::method1_per_path_doppler(r, g, p);
    sim::CMat h2 = sim::method2_dominant_doppler(r, g, p);
    sim::CMat h3 = sim::method3_post_fd_doppler(r, g, p);
    double n2 = sim::nmse(h1, h2);
    double n3 = sim::nmse(h1, h3);
    sum2 += n2; sum3 += n3;
    if (n2 > max2) max2 = n2;
    if (n3 > max3) max3 = n3;
    csv << g.grid_id << ',' << n2 << ',' << to_db(n2) << ','
        << n3 << ',' << to_db(n3) << '\n';
    if (i < 10) {
      std::printf("%4u   %13.2f   %13.2f\n", g.grid_id, to_db(n2), to_db(n3));
    }
  }
  size_t n = r.grids.size();
  std::printf("...    (전체 %zu개 grid는 %s 참조)\n\n", n, csv_path.c_str());
  std::printf("평균   %13.2f   %13.2f\n",
              to_db(sum2 / n), to_db(sum3 / n));
  std::printf("최대   %13.2f   %13.2f\n", to_db(max2), to_db(max3));
  return 0;
}

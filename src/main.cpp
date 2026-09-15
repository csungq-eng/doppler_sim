// Doppler PoC 메인.
//
// binary 레이트레이싱 결과를 읽어, grid마다 세 가지 방식으로
// 주파수 도메인 채널 행렬(64 x 4 x 3276)을 생성하고 방식 1 대비
// NMSE(위상 포함)와 RSRP 오차(전력만)를 비교한다.
//   방식 1 (기준): path별 doppler 적용 후 주파수 변환
//   방식 2: dominant N개 path만으로 채널 구성 + doppler 적용
//   방식 3: 주파수 변환 후 LOS 방향 단일 doppler 적용
//
// 세 가지 실행 모드:
//   기본            : 단일 t, grid별 NMSE/RSRP 오차 -> doppler_comparison.csv
//   --sweep-max n   : N = 1..n 에 대한 방식 2 곡선 -> nmse_sweep.csv (+ _grid.csv)
//   --symbol-list   : 심볼 index k 목록에 대해 t = k*T_sym 로 시간 진행 곡선
//                     -> symbol_sweep.csv
//
// 사용 예:
//   poc_doppler --binary output_geo_per_pair/raytracing_result.bin \
//               --speed-kmh 60 --direction-deg 45 --time-symbols 14 --num-dominant 3

#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
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
      "  --time-symbols <k>    snapshot 시각을 OFDM 심볼 수로 지정 (t = k * T_sym)\n"
      "  --scs-khz <s>         subcarrier spacing [kHz] (기본 30, T_sym = 35.7 us)\n"
      "  --num-dominant <n>    방식 2의 dominant path 수 (기본 3)\n"
      "  --renorm-dominant     방식 2에서 포함한 path 전력 합을 1로 재정규화\n"
      "  --rsrp-band-sc <n>    협대역 RSRP 측정 subcarrier 수, 대역 중앙 (기본 240 = SSB 20 RB)\n"
      "  --out-csv <path>      결과 CSV (기본 doppler_comparison.csv)\n"
      "  --sweep-max <n>       N = 1..n sweep 모드, nmse_sweep.csv(요약) +\n"
      "                        nmse_sweep_grid.csv(grid별) 출력\n"
      "  --symbol-list <a,b,..> 심볼 index 목록에 대한 시간 진행 sweep, symbol_sweep.csv 출력\n",
      prog);
}

std::vector<uint32_t> parse_list(const char* s) {
  std::vector<uint32_t> out;
  std::stringstream ss(s);
  std::string item;
  while (std::getline(ss, item, ',')) {
    if (!item.empty()) out.push_back(static_cast<uint32_t>(std::atoi(item.c_str())));
  }
  return out;
}

// 방식 x의 채널을 방식 1과 비교한 지표 묶음
struct Metrics {
  double nmse = 0.0;
  sim::RsrpError wide{0.0, 0.0};
  sim::RsrpError band{0.0, 0.0};
};

Metrics compare(const sim::CMat& h1, const sim::CMat& hx, const rt::Result& r,
                const sim::Params& p) {
  Metrics m;
  m.nmse = sim::nmse(h1, hx);
  m.wide = sim::rsrp_error_wideband(h1, hx, r, p);
  m.band = sim::rsrp_error_band(h1, hx, r, p);
  return m;
}

// grid 평균/최대를 누적하는 도우미
struct Accum {
  double sum_nmse = 0.0, max_nmse = 0.0;
  double sum_wide = 0.0, max_wide = 0.0;
  double sum_band = 0.0, max_band = 0.0;
  size_t n = 0;
  void add(const Metrics& m) {
    sum_nmse += m.nmse; if (m.nmse > max_nmse) max_nmse = m.nmse;
    sum_wide += m.wide.mean_abs_db; if (m.wide.max_abs_db > max_wide) max_wide = m.wide.max_abs_db;
    sum_band += m.band.mean_abs_db; if (m.band.max_abs_db > max_band) max_band = m.band.max_abs_db;
    ++n;
  }
  double mean_nmse_db() const { return to_db(sum_nmse / n); }
  double max_nmse_db() const { return to_db(max_nmse); }
  double mean_wide() const { return sum_wide / n; }
  double mean_band() const { return sum_band / n; }
};

}  // namespace

int main(int argc, char** argv) {
  std::string binary_path = "output_per_pair/raytracing_result.bin";
  std::string csv_path = "doppler_comparison.csv";
  double speed_kmh = 60.0;
  uint32_t sweep_max = 0;
  double time_symbols = -1.0;  // >= 0 이면 --time-ms 대신 사용
  std::vector<uint32_t> symbol_list;
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
    else if (!std::strcmp(argv[i], "--time-symbols")) time_symbols = std::atof(next());
    else if (!std::strcmp(argv[i], "--scs-khz")) p.scs_hz = std::atof(next()) * 1e3;
    else if (!std::strcmp(argv[i], "--num-dominant")) p.num_dominant = std::atoi(next());
    else if (!std::strcmp(argv[i], "--renorm-dominant")) p.renorm_dominant = true;
    else if (!std::strcmp(argv[i], "--rsrp-band-sc")) p.rsrp_band_sc = std::atoi(next());
    else if (!std::strcmp(argv[i], "--out-csv")) csv_path = next();
    else if (!std::strcmp(argv[i], "--sweep-max")) sweep_max = std::atoi(next());
    else if (!std::strcmp(argv[i], "--symbol-list")) symbol_list = parse_list(next());
    else if (!std::strcmp(argv[i], "--help")) { print_usage(argv[0]); return 0; }
    else {
      std::fprintf(stderr, "알 수 없는 옵션: %s\n", argv[i]);
      print_usage(argv[0]);
      return 1;
    }
  }
  p.speed_mps = speed_kmh / 3.6;
  if (time_symbols >= 0.0) p.time_s = time_symbols * p.symbol_duration_s();

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
  std::printf("OFDM            : fc %.2f GHz, SCS %.0f kHz, SC %u개, T_sym %.2f us\n",
              p.fc_hz / 1e9, p.scs_hz / 1e3, p.num_sc, p.symbol_duration_s() * 1e6);
  std::printf("단말 이동성     : %.1f km/h, 방향 %.1f도, snapshot t = %.4f ms (%.1f 심볼)\n",
              speed_kmh, p.move_dir_deg, p.time_s * 1e3,
              p.time_s / p.symbol_duration_s());
  std::printf("최대 doppler    : %.1f Hz\n", f_max);
  std::printf("RSRP 협대역     : 중앙 %u SC (%.1f MHz)\n", p.rsrp_band_sc,
              p.rsrp_band_sc * p.scs_hz / 1e6);
  std::printf("방식 2          : dominant N = %u%s\n", p.num_dominant,
              p.renorm_dominant ? ", 전력 재정규화" : "");

  // ---------------------------------------------------------------------
  // 심볼 sweep 모드: k 목록마다 t = k * T_sym 로 방식 2/3 지표를 뽑는다
  // ---------------------------------------------------------------------
  if (!symbol_list.empty()) {
    std::string out = csv_path == "doppler_comparison.csv" ? "symbol_sweep.csv" : csv_path;
    std::ofstream csv(out);
    csv << "symbol,t_ms,nmse2_db,nmse3_db,max_nmse2_db,max_nmse3_db,"
           "rsrp_wide_err2_db,rsrp_wide_err3_db,rsrp_band_err2_db,rsrp_band_err3_db,"
           "rsrp_wide_max2_db,rsrp_wide_max3_db,rsrp_band_max2_db,rsrp_band_max3_db\n";
    std::printf("\n 심볼     t[ms]   NMSE2[dB]  NMSE3[dB]   RSRP전대역 |err| 2 / 3 [dB]   RSRP협대역 |err| 2 / 3 [dB]\n");
    for (uint32_t k : symbol_list) {
      p.time_s = k * p.symbol_duration_s();
      Accum a2, a3;
      for (const rt::Grid& g : r.grids) {
        sim::CMat h1 = sim::method1_per_path_doppler(r, g, p);
        a2.add(compare(h1, sim::method2_dominant_doppler(r, g, p), r, p));
        a3.add(compare(h1, sim::method3_post_fd_doppler(r, g, p), r, p));
      }
      csv << k << ',' << p.time_s * 1e3 << ',' << a2.mean_nmse_db() << ','
          << a3.mean_nmse_db() << ',' << a2.max_nmse_db() << ',' << a3.max_nmse_db() << ','
          << a2.mean_wide() << ',' << a3.mean_wide() << ',' << a2.mean_band() << ','
          << a3.mean_band() << ',' << a2.max_wide << ',' << a3.max_wide << ','
          << a2.max_band << ',' << a3.max_band << '\n';
      std::printf("%5u  %8.3f  %9.2f  %9.2f   %12.2f / %-12.2f  %12.2f / %-12.2f\n",
                  k, p.time_s * 1e3, a2.mean_nmse_db(), a3.mean_nmse_db(),
                  a2.mean_wide(), a3.mean_wide(), a2.mean_band(), a3.mean_band());
    }
    std::printf("결과 저장: %s\n", out.c_str());
    return 0;
  }

  // ---------------------------------------------------------------------
  // N sweep 모드: N = 1..sweep_max에 대해 방식 2 곡선을 뽑는다
  // ---------------------------------------------------------------------
  if (sweep_max > 0) {
    size_t n = r.grids.size();
    std::string sweep_csv =
        csv_path == "doppler_comparison.csv" ? "nmse_sweep.csv" : csv_path;
    // grid별 원자료: <sweep_csv 이름>_grid.csv (LOS/NLOS 분리 분석용)
    std::string grid_csv = sweep_csv;
    size_t dot = grid_csv.rfind(".csv");
    grid_csv.insert(dot == std::string::npos ? grid_csv.size() : dot, "_grid");
    std::ofstream gcsv(grid_csv);
    gcsv << "grid_id,n_dominant,nmse2,nmse3,rsrp_wide_err2_db,rsrp_wide_err3_db,"
            "rsrp_band_err2_db,rsrp_band_err3_db\n";

    std::vector<Accum> acc2(sweep_max + 1);
    Accum acc3;
    for (const rt::Grid& g : r.grids) {
      sim::CMat h1 = sim::method1_per_path_doppler(r, g, p);
      Metrics m3 = compare(h1, sim::method3_post_fd_doppler(r, g, p), r, p);
      acc3.add(m3);
      for (uint32_t nd = 1; nd <= sweep_max; ++nd) {
        p.num_dominant = nd;
        Metrics m2 = compare(h1, sim::method2_dominant_doppler(r, g, p), r, p);
        acc2[nd].add(m2);
        gcsv << g.grid_id << ',' << nd << ',' << m2.nmse << ',' << m3.nmse << ','
             << m2.wide.mean_abs_db << ',' << m3.wide.mean_abs_db << ','
             << m2.band.mean_abs_db << ',' << m3.band.mean_abs_db << '\n';
      }
    }
    std::ofstream csv(sweep_csv);
    csv << "n_dominant,mean_nmse2,mean_nmse2_db,max_nmse2_db,"
           "mean_nmse3_db,max_nmse3_db,"
           "rsrp_wide_err2_db,rsrp_wide_err3_db,rsrp_band_err2_db,rsrp_band_err3_db\n";
    std::printf("\n   N   평균 NMSE 방식2[dB]   최대 NMSE 방식2[dB]   RSRP |err| 전대역/협대역 방식2[dB]\n");
    for (uint32_t nd = 1; nd <= sweep_max; ++nd) {
      const Accum& a = acc2[nd];
      csv << nd << ',' << a.sum_nmse / n << ',' << a.mean_nmse_db() << ','
          << a.max_nmse_db() << ',' << acc3.mean_nmse_db() << ',' << acc3.max_nmse_db()
          << ',' << a.mean_wide() << ',' << acc3.mean_wide() << ',' << a.mean_band()
          << ',' << acc3.mean_band() << '\n';
      std::printf("%4u   %19.2f   %19.2f   %14.2f / %-6.2f\n", nd, a.mean_nmse_db(),
                  a.max_nmse_db(), a.mean_wide(), a.mean_band());
    }
    std::printf("방식3  %19.2f   %19.2f   %14.2f / %-6.2f  (참고)\n",
                acc3.mean_nmse_db(), acc3.max_nmse_db(), acc3.mean_wide(),
                acc3.mean_band());
    std::printf("결과 저장: %s (요약), %s (grid별)\n", sweep_csv.c_str(),
                grid_csv.c_str());
    return 0;
  }

  // ---------------------------------------------------------------------
  // 기본 모드: 단일 t, grid별 NMSE + RSRP 오차
  // ---------------------------------------------------------------------
  std::ofstream csv(csv_path);
  csv << "grid_id,nmse_method2,nmse_method2_db,nmse_method3,nmse_method3_db,"
         "rsrp_wide_err2_db,rsrp_wide_err3_db,rsrp_band_err2_db,rsrp_band_err3_db,"
         "rsrp_wide_max2_db,rsrp_wide_max3_db,rsrp_band_max2_db,rsrp_band_max3_db\n";

  Accum a2, a3;
  std::printf("\ngrid   NMSE 방식2[dB]   NMSE 방식3[dB]   RSRP전대역 |err| 2 / 3   RSRP협대역 |err| 2 / 3\n");
  for (size_t i = 0; i < r.grids.size(); ++i) {
    const rt::Grid& g = r.grids[i];
    sim::CMat h1 = sim::method1_per_path_doppler(r, g, p);
    Metrics m2 = compare(h1, sim::method2_dominant_doppler(r, g, p), r, p);
    Metrics m3 = compare(h1, sim::method3_post_fd_doppler(r, g, p), r, p);
    a2.add(m2); a3.add(m3);
    csv << g.grid_id << ',' << m2.nmse << ',' << to_db(m2.nmse) << ','
        << m3.nmse << ',' << to_db(m3.nmse) << ','
        << m2.wide.mean_abs_db << ',' << m3.wide.mean_abs_db << ','
        << m2.band.mean_abs_db << ',' << m3.band.mean_abs_db << ','
        << m2.wide.max_abs_db << ',' << m3.wide.max_abs_db << ','
        << m2.band.max_abs_db << ',' << m3.band.max_abs_db << '\n';
    if (i < 10) {
      std::printf("%4u   %13.2f   %13.2f   %10.2f / %-10.2f   %10.2f / %-10.2f\n",
                  g.grid_id, to_db(m2.nmse), to_db(m3.nmse), m2.wide.mean_abs_db,
                  m3.wide.mean_abs_db, m2.band.mean_abs_db, m3.band.mean_abs_db);
    }
  }
  std::printf("...    (전체 %zu개 grid는 %s 참조)\n\n", r.grids.size(), csv_path.c_str());
  std::printf("평균   %13.2f   %13.2f   %10.2f / %-10.2f   %10.2f / %-10.2f\n",
              a2.mean_nmse_db(), a3.mean_nmse_db(), a2.mean_wide(), a3.mean_wide(),
              a2.mean_band(), a3.mean_band());
  std::printf("최대   %13.2f   %13.2f   %10.2f / %-10.2f   %10.2f / %-10.2f\n",
              a2.max_nmse_db(), a3.max_nmse_db(), a2.max_wide, a3.max_wide,
              a2.max_band, a3.max_band);
  return 0;
}

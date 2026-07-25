// 레이트레이싱 binary(raytracing_result.bin, version 2) 로더.
//
// 파일 포맷 (little-endian):
//   [header] magic("RTCH") version(u32) mode(u32)
//            num_bs_ant(u32) num_ue_ant(u32) num_grids(u32)
//   mode 0 (per-grid)  : grid_id(u32) num_paths(u32) [path...]        grid마다 반복
//   mode 1 (per-pair)  : grid_id(u32)
//                        { bs_ant_id(u32) ue_ant_id(u32) num_paths(u32) [path...] }
//                        x (num_bs_ant * num_ue_ant), bs 우선 순서      grid마다 반복
//   path record: path_id(u32) power(f64) aoa_deg(f64) aod_deg(f64) tau_s(f64)
#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace rt {

constexpr uint32_t kVersion = 2;

enum Mode : uint32_t {
  kPerGrid = 0,  // grid마다 하나의 path 집합
  kPerPair = 1,  // grid마다 안테나 pair별 path 집합
};

struct Path {
  uint32_t path_id;
  double power;    // 선형 스케일, 집합 내 합 = 1
  double aoa_deg;  // 단말 기준 도래각 (azimuth)
  double aod_deg;  // 기지국 기준 발사각 (azimuth)
  double tau_s;    // 전파 지연 [초]
};

struct PairChannel {
  uint32_t bs_ant_id;
  uint32_t ue_ant_id;
  std::vector<Path> paths;
};

struct Grid {
  uint32_t grid_id;
  std::vector<Path> paths;         // mode 0에서만 사용
  std::vector<PairChannel> pairs;  // mode 1에서만 사용
};

struct Result {
  Mode mode;
  uint32_t num_bs_ant;
  uint32_t num_ue_ant;
  std::vector<Grid> grids;

  // 모드에 관계없이 (grid, bs, ue) pair의 path 집합을 돌려준다.
  // mode 0에서는 모든 pair가 grid의 path 집합을 공유한다.
  const std::vector<Path>& paths_for(const Grid& g, uint32_t bs_ant,
                                     uint32_t ue_ant) const;
};

// 파일을 읽어 검증(magic/version/mode/파일 끝)까지 수행한다.
// 문제가 있으면 std::runtime_error를 던진다.
Result load(const std::string& file_path);

}  // namespace rt

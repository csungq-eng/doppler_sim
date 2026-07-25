#include "rt_loader.hpp"

#include <cstring>
#include <fstream>
#include <stdexcept>

namespace rt {
namespace {

// 파일 버퍼를 순차적으로 읽는 커서. 범위를 벗어나면 예외.
class Reader {
 public:
  Reader(const std::vector<char>& buf) : buf_(buf) {}

  uint32_t u32() {
    uint32_t v;
    copy(&v, sizeof(v));
    return v;
  }

  double f64() {
    double v;
    copy(&v, sizeof(v));
    return v;
  }

  void bytes(char* dst, size_t n) { copy(dst, n); }

  bool at_end() const { return pos_ == buf_.size(); }

 private:
  void copy(void* dst, size_t n) {
    if (pos_ + n > buf_.size()) {
      throw std::runtime_error("binary 파일이 예상보다 짧습니다 (truncated)");
    }
    std::memcpy(dst, buf_.data() + pos_, n);
    pos_ += n;
  }

  const std::vector<char>& buf_;
  size_t pos_ = 0;
};

Path read_path(Reader& r) {
  Path p;
  p.path_id = r.u32();
  p.power = r.f64();
  p.aoa_deg = r.f64();
  p.aod_deg = r.f64();
  p.tau_s = r.f64();
  return p;
}

std::vector<Path> read_paths(Reader& r, uint32_t num_paths) {
  std::vector<Path> paths;
  paths.reserve(num_paths);
  for (uint32_t i = 0; i < num_paths; ++i) paths.push_back(read_path(r));
  return paths;
}

}  // namespace

const std::vector<Path>& Result::paths_for(const Grid& g, uint32_t bs_ant,
                                           uint32_t ue_ant) const {
  if (mode == kPerGrid) return g.paths;
  return g.pairs[bs_ant * num_ue_ant + ue_ant].paths;
}

Result load(const std::string& file_path) {
  std::ifstream f(file_path, std::ios::binary);
  if (!f) throw std::runtime_error("파일을 열 수 없습니다: " + file_path);
  std::vector<char> buf((std::istreambuf_iterator<char>(f)),
                        std::istreambuf_iterator<char>());
  Reader r(buf);

  char magic[4];
  r.bytes(magic, 4);
  if (std::memcmp(magic, "RTCH", 4) != 0) {
    throw std::runtime_error("binary magic 불일치");
  }
  uint32_t version = r.u32();
  if (version != kVersion) {
    throw std::runtime_error("지원하지 않는 binary version: " +
                             std::to_string(version));
  }
  uint32_t mode = r.u32();
  if (mode != kPerGrid && mode != kPerPair) {
    throw std::runtime_error("알 수 없는 mode: " + std::to_string(mode));
  }

  Result result;
  result.mode = static_cast<Mode>(mode);
  result.num_bs_ant = r.u32();
  result.num_ue_ant = r.u32();
  uint32_t num_grids = r.u32();

  result.grids.reserve(num_grids);
  for (uint32_t i = 0; i < num_grids; ++i) {
    Grid g;
    g.grid_id = r.u32();
    if (result.mode == kPerPair) {
      uint32_t num_pairs = result.num_bs_ant * result.num_ue_ant;
      g.pairs.reserve(num_pairs);
      for (uint32_t j = 0; j < num_pairs; ++j) {
        PairChannel pair;
        pair.bs_ant_id = r.u32();
        pair.ue_ant_id = r.u32();
        pair.paths = read_paths(r, r.u32());
        g.pairs.push_back(std::move(pair));
      }
    } else {
      g.paths = read_paths(r, r.u32());
    }
    result.grids.push_back(std::move(g));
  }

  if (!r.at_end()) {
    throw std::runtime_error("binary 파일 끝에 예상치 못한 데이터가 있습니다");
  }
  return result;
}

}  // namespace rt

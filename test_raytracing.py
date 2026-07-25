"""저장된 레이트레이싱 binary 파일 검증 테스트.

실행:
    python -m unittest test_raytracing -v

grid 모드 / per-antenna-pair 모드를 각각 검증한다.
임시 폴더에 생성->저장->로드를 수행하므로 output/ 폴더가 없어도 동작한다.
"""

import struct
import tempfile
import unittest
from pathlib import Path as FilePath

from channel_sim import (
    MODE_PER_GRID,
    MODE_PER_PAIR,
    SimulationConfig,
    generate_raytracing_result,
    save_result,
    load_result,
)
from channel_sim.raytracing import (
    BIN_MAGIC, BIN_VERSION, _HEADER_FMT, _GRID_FMT, _GRID_ID_FMT, _PAIR_FMT, _PATH_FMT,
)


def path_sets(result):
    """모드에 관계없이 결과의 모든 path 집합을 순회한다."""
    for g in result.grids:
        if result.config.per_antenna_pair:
            for pair in g.pairs:
                yield pair.paths
        else:
            yield g.paths


class RaytracingTestBase:
    """두 모드가 공유하는 테스트. 서브클래스에서 config를 지정한다."""

    per_antenna_pair = False

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.out_dir = cls.tmp_dir.name
        cls.config = SimulationConfig(per_antenna_pair=cls.per_antenna_pair)
        cls.result = generate_raytracing_result(cls.config)
        save_result(cls.result, cls.out_dir)
        cls.loaded = load_result(cls.out_dir)

    @classmethod
    def tearDownClass(cls):
        cls.tmp_dir.cleanup()

    # ---------- 파일 자체 검증 ----------

    def test_files_exist(self):
        """binary 파일과 config.json이 생성된다."""
        self.assertTrue((FilePath(self.out_dir) / "raytracing_result.bin").exists())
        self.assertTrue((FilePath(self.out_dir) / "config.json").exists())

    def test_binary_header(self):
        """header의 magic/version/mode/안테나 수/grid 수가 config와 일치한다."""
        raw = (FilePath(self.out_dir) / "raytracing_result.bin").read_bytes()
        magic, version, mode, num_bs, num_ue, num_grids = struct.unpack_from(
            _HEADER_FMT, raw
        )
        self.assertEqual(magic, BIN_MAGIC)
        self.assertEqual(version, BIN_VERSION)
        expected_mode = MODE_PER_PAIR if self.per_antenna_pair else MODE_PER_GRID
        self.assertEqual(mode, expected_mode)
        self.assertEqual(num_bs, self.config.num_bs_antennas)
        self.assertEqual(num_ue, self.config.num_ue_antennas)
        self.assertEqual(num_grids, self.config.num_grids)

    def test_binary_size(self):
        """파일 크기가 포맷 정의(header + 레코드 크기 합)와 정확히 일치한다."""
        total_paths = sum(len(paths) for paths in path_sets(self.result))
        if self.per_antenna_pair:
            n_pairs = self.config.num_bs_antennas * self.config.num_ue_antennas
            record_bytes = self.config.num_grids * (
                struct.calcsize(_GRID_ID_FMT) + n_pairs * struct.calcsize(_PAIR_FMT)
            )
        else:
            record_bytes = self.config.num_grids * struct.calcsize(_GRID_FMT)
        expected = (
            struct.calcsize(_HEADER_FMT)
            + record_bytes
            + total_paths * struct.calcsize(_PATH_FMT)
        )
        actual = (FilePath(self.out_dir) / "raytracing_result.bin").stat().st_size
        self.assertEqual(actual, expected)

    # ---------- round-trip 검증 ----------

    def test_roundtrip_grid_count(self):
        """로드한 grid 수가 원본과 같다."""
        self.assertEqual(len(self.loaded.grids), len(self.result.grids))

    def test_roundtrip_values_exact(self):
        """모든 path 집합의 값이 저장 전과 bit 단위로 동일하다 (f64 무손실)."""
        for orig, load in zip(path_sets(self.result), path_sets(self.loaded)):
            self.assertEqual(len(orig), len(load))
            for p_orig, p_load in zip(orig, load):
                self.assertEqual(p_orig.path_id, p_load.path_id)
                self.assertEqual(p_orig.power, p_load.power)
                self.assertEqual(p_orig.aoa_deg, p_load.aoa_deg)
                self.assertEqual(p_orig.aod_deg, p_load.aod_deg)
                self.assertEqual(p_orig.tau_s, p_load.tau_s)

    # ---------- 물리적 타당성 검증 ----------

    def test_num_paths_in_range(self):
        """path 집합별 path 수가 [min_paths, max_paths] 범위 안이다."""
        for paths in path_sets(self.loaded):
            self.assertGreaterEqual(len(paths), self.config.min_paths)
            self.assertLessEqual(len(paths), self.config.max_paths)

    def test_power_normalized(self):
        """path 집합 내 전력 합이 1이고 각 전력은 양수다."""
        for paths in path_sets(self.loaded):
            self.assertAlmostEqual(sum(p.power for p in paths), 1.0, places=10)
            for p in paths:
                self.assertGreater(p.power, 0.0)

    def test_tau_sorted_and_in_range(self):
        """tau는 오름차순이고 첫 path 지연이 설정 범위 안이다."""
        for paths in path_sets(self.loaded):
            taus = [p.tau_s for p in paths]
            self.assertEqual(taus, sorted(taus))
            self.assertGreaterEqual(taus[0], self.config.min_first_path_delay_s)
            self.assertLessEqual(taus[0], self.config.max_first_path_delay_s)

    def test_angles_in_range(self):
        """AoA/AoD가 설정된 각도 범위 안이다."""
        aoa_lo, aoa_hi = self.config.aoa_range_deg
        aod_lo, aod_hi = self.config.aod_range_deg
        for paths in path_sets(self.loaded):
            for p in paths:
                self.assertTrue(aoa_lo <= p.aoa_deg <= aoa_hi)
                self.assertTrue(aod_lo <= p.aod_deg <= aod_hi)

    def test_path_ids_sequential(self):
        """path_id가 path 집합마다 0부터 순차적으로 부여된다."""
        for paths in path_sets(self.loaded):
            self.assertEqual([p.path_id for p in paths], list(range(len(paths))))

    # ---------- 확장성/재현성 검증 ----------

    def test_reproducible_with_same_seed(self):
        """같은 seed로 다시 생성하면 동일한 결과가 나온다."""
        again = generate_raytracing_result(
            SimulationConfig(per_antenna_pair=self.per_antenna_pair)
        )
        first_orig = next(path_sets(self.result))
        first_again = next(path_sets(again))
        self.assertEqual(len(first_orig), len(first_again))
        self.assertEqual(first_orig[0].power, first_again[0].power)
        self.assertEqual(first_orig[-1].tau_s, first_again[-1].tau_s)

    def test_scalable_num_grids(self):
        """num_grids를 바꿔도 (파라미터화) 정상 동작한다."""
        config = SimulationConfig(
            num_grids=3, per_antenna_pair=self.per_antenna_pair
        )
        result = generate_raytracing_result(config)
        with tempfile.TemporaryDirectory() as tmp:
            save_result(result, tmp)
            loaded = load_result(tmp)
        self.assertEqual(len(loaded.grids), 3)

    def test_corrupt_magic_rejected(self):
        """magic이 깨진 binary 파일은 로드 시 오류를 낸다."""
        with tempfile.TemporaryDirectory() as tmp:
            save_result(self.result, tmp)
            bin_path = FilePath(tmp) / "raytracing_result.bin"
            raw = bytearray(bin_path.read_bytes())
            raw[:4] = b"XXXX"
            bin_path.write_bytes(bytes(raw))
            with self.assertRaises(ValueError):
                load_result(tmp)

    def test_truncated_file_rejected(self):
        """뒤가 잘린 binary 파일은 로드 시 오류를 낸다."""
        with tempfile.TemporaryDirectory() as tmp:
            save_result(self.result, tmp)
            bin_path = FilePath(tmp) / "raytracing_result.bin"
            raw = bin_path.read_bytes()
            bin_path.write_bytes(raw[:-8])
            with self.assertRaises((struct.error, ValueError)):
                load_result(tmp)


class PerGridModeTest(RaytracingTestBase, unittest.TestCase):
    """grid마다 하나의 path 집합을 갖는 기본 모드."""

    per_antenna_pair = False


class PerAntennaPairModeTest(RaytracingTestBase, unittest.TestCase):
    """grid마다 64x4 안테나 pair별 path 집합을 갖는 모드."""

    per_antenna_pair = True

    @classmethod
    def setUpClass(cls):
        # 전체 생성(100 grid x 256 pair)은 느리므로 grid 수를 줄여 검증
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.out_dir = cls.tmp_dir.name
        cls.config = SimulationConfig(num_grids=5, per_antenna_pair=True)
        cls.result = generate_raytracing_result(cls.config)
        save_result(cls.result, cls.out_dir)
        cls.loaded = load_result(cls.out_dir)

    def test_pair_count_and_ids(self):
        """grid마다 pair가 정확히 num_bs x num_ue개이고 (bs, ue) id가 순서대로다."""
        n_bs = self.config.num_bs_antennas
        n_ue = self.config.num_ue_antennas
        expected_ids = [(b, u) for b in range(n_bs) for u in range(n_ue)]
        for g in self.loaded.grids:
            self.assertEqual(len(g.pairs), n_bs * n_ue)
            actual_ids = [(p.bs_ant_id, p.ue_ant_id) for p in g.pairs]
            self.assertEqual(actual_ids, expected_ids)

    def test_pairs_are_independent(self):
        """pair마다 path 집합이 독립적으로 생성된다 (전부 동일하지 않다)."""
        g = self.loaded.grids[0]
        first = g.pairs[0].paths
        identical = all(
            pair.num_paths == len(first)
            and all(a.tau_s == b.tau_s for a, b in zip(pair.paths, first))
            for pair in g.pairs
        )
        self.assertFalse(identical)

    def test_mode_mismatch_rejected(self):
        """binary header의 mode와 config.json의 mode가 다르면 로드를 거부한다."""
        import json
        with tempfile.TemporaryDirectory() as tmp:
            save_result(self.result, tmp)
            cfg_path = FilePath(tmp) / "config.json"
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            cfg["per_antenna_pair"] = False
            cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_result(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""저장된 레이트레이싱 binary 파일 검증 테스트.

실행:
    python -m unittest test_raytracing -v

random / geometric 시나리오 x grid / per-antenna-pair 모드를 각각 검증한다.
임시 폴더에 생성->저장->로드를 수행하므로 output/ 폴더가 없어도 동작한다.
"""

import math
import struct
import tempfile
import unittest
from pathlib import Path as FilePath

from channel_sim import (
    MODE_PER_GRID,
    MODE_PER_PAIR,
    SPEED_OF_LIGHT,
    SimulationConfig,
    azimuth_deg,
    generate_raytracing_result,
    grid_position_m,
    is_los,
    los_aoa_deg,
    segment_hits_rect,
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
    """모든 시나리오/모드가 공유하는 테스트. 서브클래스에서 config를 지정한다."""

    per_antenna_pair = False
    scenario = "random"
    num_grids = 100  # per-pair 모드는 느리므로 서브클래스에서 줄인다

    @classmethod
    def make_config(cls, **overrides):
        kwargs = dict(
            per_antenna_pair=cls.per_antenna_pair,
            scenario=cls.scenario,
            num_grids=cls.num_grids,
        )
        kwargs.update(overrides)
        return SimulationConfig(**kwargs)

    @classmethod
    def setUpClass(cls):
        cls.tmp_dir = tempfile.TemporaryDirectory()
        cls.out_dir = cls.tmp_dir.name
        cls.config = cls.make_config()
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

    def test_unknown_scenario_rejected(self):
        """scenario 값이 잘못되면 생성 시 오류를 낸다."""
        with self.assertRaises(ValueError):
            generate_raytracing_result(self.make_config(scenario="nope"))

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
        again = generate_raytracing_result(self.make_config())
        first_orig = next(path_sets(self.result))
        first_again = next(path_sets(again))
        self.assertEqual(len(first_orig), len(first_again))
        self.assertEqual(first_orig[0].power, first_again[0].power)
        self.assertEqual(first_orig[-1].tau_s, first_again[-1].tau_s)

    def test_scalable_num_grids(self):
        """num_grids를 바꿔도 (파라미터화) 정상 동작한다."""
        result = generate_raytracing_result(self.make_config(num_grids=3))
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


class PerPairTestMixin:
    """per-antenna-pair 모드 공통 테스트 (시나리오 무관)."""

    per_antenna_pair = True
    num_grids = 5  # 전체 생성(100 grid x 256 pair)은 느리므로 grid 수를 줄여 검증

    def test_pair_count_and_ids(self):
        """grid마다 pair가 정확히 num_bs x num_ue개이고 (bs, ue) id가 순서대로다."""
        n_bs = self.config.num_bs_antennas
        n_ue = self.config.num_ue_antennas
        expected_ids = [(b, u) for b in range(n_bs) for u in range(n_ue)]
        for g in self.loaded.grids:
            self.assertEqual(len(g.pairs), n_bs * n_ue)
            actual_ids = [(p.bs_ant_id, p.ue_ant_id) for p in g.pairs]
            self.assertEqual(actual_ids, expected_ids)

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


class PerAntennaPairModeTest(PerPairTestMixin, RaytracingTestBase,
                             unittest.TestCase):
    """random 시나리오, grid마다 64x4 안테나 pair별 path 집합을 갖는 모드."""

    def test_pairs_are_independent(self):
        """random 시나리오는 pair마다 path 집합이 독립적이다 (전부 동일하지 않다)."""
        g = self.loaded.grids[0]
        first = g.pairs[0].paths
        identical = all(
            pair.num_paths == len(first)
            and all(a.tau_s == b.tau_s for a, b in zip(pair.paths, first))
            for pair in g.pairs
        )
        self.assertFalse(identical)


# ---------------------------------------------------------------------------
# geometric 시나리오 (실제 레이트레이싱 모사)
# ---------------------------------------------------------------------------

class GeometricTestMixin:
    """geometric 시나리오 공통 테스트. 기하로부터 계산되는 값을 검증한다."""

    scenario = "geometric"

    def reference_paths(self, g):
        """grid의 대표 path 집합 (per-pair면 pair (0,0))."""
        return g.pairs[0].paths if self.per_antenna_pair else g.paths

    def reflection_paths(self, g):
        """LOS를 제외한 반사 path 목록."""
        paths = self.reference_paths(g)
        return paths[1:] if is_los(g.grid_id, self.config) else paths

    def los_distance(self, g):
        bx, by = self.config.bs_position_m
        gx, gy = grid_position_m(g.grid_id, self.config)
        return math.hypot(gx - bx, gy - by)

    def geometry_tolerance(self):
        """per-pair 모드에서 element 위치 차이로 허용되는 각도/지연 오차."""
        if not self.per_antenna_pair:
            return 1e-9, 1e-15  # 부동소수점 오차만 허용
        lam = SPEED_OF_LIGHT / self.config.carrier_frequency_hz
        half_aperture = 0.5 * (self.config.num_bs_antennas - 1) \
            * self.config.element_spacing_wavelengths * lam
        # 배열 절반 aperture(~1.35 m)가 최소 거리(50 m)에서 만드는 각도/지연 오차
        return math.degrees(math.atan2(half_aperture, 50.0)) * 2, \
            2 * half_aperture / SPEED_OF_LIGHT * 2

    def test_tau_sorted_and_in_range(self):
        """tau는 오름차순이고, LOS grid의 첫 path 지연은 기지국-grid 거리와 일치한다."""
        _, tau_tol = self.geometry_tolerance()
        for g in self.loaded.grids:
            tau_los = self.los_distance(g) / SPEED_OF_LIGHT
            for paths in ([p.paths for p in g.pairs]
                          if self.per_antenna_pair else [g.paths]):
                taus = [p.tau_s for p in paths]
                # element 위치 차이만큼의 역전만 허용
                for a, b in zip(taus, taus[1:]):
                    self.assertLessEqual(a, b + tau_tol)
                if is_los(g.grid_id, self.config):
                    self.assertAlmostEqual(taus[0], tau_los, delta=tau_tol + 1e-15)
                else:
                    self.assertGreater(taus[0], tau_los)  # NLOS: 반사 path뿐

    def test_los_is_first_and_strongest(self):
        """LOS grid에서는 첫 path가 LOS이고 (반사 손실 > 0이므로) 가장 강하다."""
        for g in self.loaded.grids:
            if not is_los(g.grid_id, self.config):
                continue
            paths = self.reference_paths(g)
            self.assertEqual(paths[0].power, max(p.power for p in paths))

    def test_blockage_creates_nlos_grids(self):
        """차폐 블록 때문에 LOS grid와 NLOS grid가 모두 존재하고, 블록이 없으면 전부 LOS다."""
        n_los = sum(is_los(g.grid_id, self.config) for g in self.loaded.grids)
        self.assertGreater(n_los, 0)
        self.assertLess(n_los, len(self.loaded.grids))
        open_cfg = self.make_config(obstacles_m=())
        self.assertTrue(all(is_los(i, open_cfg) for i in range(open_cfg.num_grids)))

    def test_no_grid_inside_obstacle(self):
        """grid 위치가 차폐 블록 내부에 있으면 안 된다 (건물 안의 단말)."""
        for g in self.loaded.grids:
            gx, gy = grid_position_m(g.grid_id, self.config)
            for (x0, y0), (x1, y1) in self.config.obstacles_m:
                inside = (min(x0, x1) <= gx <= max(x0, x1)
                          and min(y0, y1) <= gy <= max(y0, y1))
                self.assertFalse(inside, f"grid {g.grid_id}가 블록 안에 있음")

    def test_nlos_grids_are_clustered(self):
        """블록 뒤 NLOS grid는 뭉쳐 있다: 모든 NLOS grid가 NLOS 이웃(상하좌우)을 갖는다."""
        cols = self.config.grid_cols
        nlos = {g.grid_id for g in self.loaded.grids
                if not is_los(g.grid_id, self.config)}
        for i in nlos:
            r, c = divmod(i, cols)
            neighbors = {(r + dr) * cols + (c + dc)
                         for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1))
                         if 0 <= r + dr and 0 <= c + dc < cols}
            self.assertTrue(neighbors & nlos, f"grid {i}가 고립된 NLOS")

    def test_reflection_legs_not_blocked(self):
        """채택된 반사 path의 두 구간(기지국→산란체, 산란체→grid)이 블록을 지나지 않는다.

        산란체 위치는 저장되지 않으므로 AoD·AoA·tau로 역산한다.
        """
        bx, by = self.config.bs_position_m
        for g in self.loaded.grids:
            gx, gy = grid_position_m(g.grid_id, self.config)
            for p in self.reflection_paths(g):
                # 기지국에서 AoD 방향으로 d1, grid에서 AoA 방향으로 d2 가면 같은 점
                total = p.tau_s * SPEED_OF_LIGHT
                ux, uy = math.cos(math.radians(p.aod_deg)), math.sin(math.radians(p.aod_deg))
                vx, vy = math.cos(math.radians(p.aoa_deg)), math.sin(math.radians(p.aoa_deg))
                # (bx + d1 ux, by + d1 uy) == (gx + d2 vx, gy + d2 vy), d1 + d2 = total
                # → d1 (u + v) = (g - b) + total v ; 2식 1미지수라 최소자승으로 푼다
                ax, ay = ux + vx, uy + vy
                b0, b1 = gx - bx + total * vx, gy - by + total * vy
                d1 = (ax * b0 + ay * b1) / (ax * ax + ay * ay)
                sx, sy = bx + d1 * ux, by + d1 * uy
                for rect in self.config.obstacles_m:
                    self.assertFalse(segment_hits_rect((bx, by), (sx, sy), rect))
                    self.assertFalse(segment_hits_rect((sx, sy), (gx, gy), rect))

    def test_los_angles_match_geometry(self):
        """LOS grid에서 LOS의 AoA는 단말→기지국, AoD는 기지국→단말 방위각이다."""
        ang_tol, _ = self.geometry_tolerance()
        bx, by = self.config.bs_position_m
        for g in self.loaded.grids:
            if not is_los(g.grid_id, self.config):
                continue
            gx, gy = grid_position_m(g.grid_id, self.config)
            los = self.reference_paths(g)[0]
            self.assertAlmostEqual(los.aoa_deg, los_aoa_deg(g.grid_id, self.config),
                                   delta=ang_tol)
            self.assertAlmostEqual(los.aod_deg, azimuth_deg(gx - bx, gy - by),
                                   delta=ang_tol)
            # LOS AoA와 AoD는 서로 반대 방향
            diff = (los.aoa_deg - los.aod_deg + 180.0) % 360.0
            self.assertAlmostEqual(diff, 0.0 if diff < 180 else 360.0,
                                   delta=ang_tol)

    def test_nlos_delay_exceeds_los(self):
        """반사 path의 지연은 삼각 부등식에 의해 LOS 거리/c보다 크다 (element 오차 허용)."""
        _, tau_tol = self.geometry_tolerance()
        for g in self.loaded.grids:
            tau_los = self.los_distance(g) / SPEED_OF_LIGHT
            for p in self.reflection_paths(g):
                self.assertGreater(p.tau_s + tau_tol, tau_los)

    def test_neighbor_grids_share_environment(self):
        """산란체가 공유되므로 인접 grid는 같은 AoD(기지국→산란체)를 갖는 path가 있다."""
        aods = [
            {round(p.aod_deg, 6) for p in self.reflection_paths(g)}
            for g in self.loaded.grids
        ]
        shared = sum(1 for a, b in zip(aods, aods[1:]) if a & b)
        self.assertGreater(shared, 0)

    def test_random_scenario_differs(self):
        """같은 seed라도 random 시나리오와는 다른 결과가 나온다."""
        other = generate_raytracing_result(self.make_config(scenario="random"))
        a = next(path_sets(self.loaded))
        b = next(path_sets(other))
        self.assertNotEqual(a[0].tau_s, b[0].tau_s)


class GeometricPerGridModeTest(GeometricTestMixin, RaytracingTestBase,
                               unittest.TestCase):
    """geometric 시나리오, per-grid 모드."""

    def test_segment_rect_intersection(self):
        """선분-사각형 교차 판정 (차폐 계산의 기초)."""
        rect = ((10.0, 10.0), (20.0, 20.0))
        self.assertTrue(segment_hits_rect((0, 0), (30, 30), rect))    # 대각선 관통
        self.assertTrue(segment_hits_rect((0, 15), (30, 15), rect))   # 수평 관통
        self.assertTrue(segment_hits_rect((15, 0), (15, 30), rect))   # 수직 관통
        self.assertTrue(segment_hits_rect((15, 15), (40, 40), rect))  # 내부에서 시작
        self.assertFalse(segment_hits_rect((0, 0), (30, 5), rect))    # 아래로 지나감
        self.assertFalse(segment_hits_rect((0, 0), (5, 5), rect))     # 닿기 전에 끝남
        self.assertFalse(segment_hits_rect((25, 0), (25, 30), rect))  # 옆으로 지나감
        # 좌표 순서가 뒤집힌 사각형도 동일
        self.assertTrue(segment_hits_rect((0, 0), (30, 30), ((20, 20), (10, 10))))


class GeometricPerAntennaPairModeTest(GeometricTestMixin, PerPairTestMixin,
                                      RaytracingTestBase, unittest.TestCase):
    """geometric 시나리오, per-antenna-pair 모드."""

    num_grids = 8  # grid 0~4는 블록 뒤 NLOS라 LOS grid도 포함되도록 8개 사용

    def test_pairs_share_paths_with_element_offsets(self):
        """pair마다 같은 path 집합(수/id/전력)을 갖고 tau만 element 위치만큼 다르다."""
        _, tau_tol = self.geometry_tolerance()
        for g in self.loaded.grids:
            ref = g.pairs[0].paths
            for pair in g.pairs[1:]:
                self.assertEqual(pair.num_paths, len(ref))
                for a, b in zip(pair.paths, ref):
                    self.assertEqual(a.path_id, b.path_id)
                    self.assertEqual(a.power, b.power)
                    self.assertLessEqual(abs(a.tau_s - b.tau_s), tau_tol)

    def test_pairs_are_not_identical(self):
        """element 위치가 다르므로 tau가 pair마다 실제로 달라진다 (배열 응답)."""
        g = self.loaded.grids[0]
        taus0 = [p.tau_s for p in g.pairs[0].paths]
        taus_last = [p.tau_s for p in g.pairs[-1].paths]
        self.assertNotEqual(taus0, taus_last)


if __name__ == "__main__":
    unittest.main(verbosity=2)

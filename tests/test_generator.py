"""Integration tests for the public map-text API."""

from pathlib import Path
import sys
import tempfile
import unittest

PACKAGE_ROOT = Path(__file__).parents[1]
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
sys.path[:0] = [str(PACKAGE_ROOT / "src"), str(PROJECT_ROOT)]

from flyin_map_generator import (  # noqa: E402
    MapDistribution,
    RandomizationPolicy,
    generate_map_text,
)
from parser import MapParser  # noqa: E402
from solver import Dinic  # noqa: E402


class GeneratorTests(unittest.TestCase):
    """Verify generated text through the finished application's parser."""

    def test_seeded_output_is_stable_and_parseable(self) -> None:
        """A seed produces identical valid Fly-in input."""
        policy = RandomizationPolicy(seed=8128)
        first = generate_map_text(5, 12, 18, policy)
        self.assertEqual(first, generate_map_text(5, 12, 18, policy))
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "generated.txt"
            path.write_text(first, encoding="utf-8")
            data = MapParser().parse_file(path)
        self.assertEqual(data.drone_count, 5)
        self.assertEqual(len(data.zones), 12)
        self.assertEqual(len(data.connections), 18)
        self.assertFalse(Dinic().get_solution(data).failed)

    def test_named_presets_emit_solvable_maps(self) -> None:
        """Each fixed user-facing preset retains the accessible route."""
        for distribution in MapDistribution:
            if distribution == MapDistribution.CUSTOM:
                continue
            with self.subTest(distribution=distribution):
                text = generate_map_text(
                    5,
                    12,
                    18,
                    RandomizationPolicy.for_distribution(distribution, seed=91),
                )
                self.assertIn("start_hub: start", text)
                self.assertIn("end_hub: end", text)

    def test_rejects_impossible_edge_count(self) -> None:
        """The public API rejects requests beyond a simple graph's capacity."""
        with self.assertRaises(ValueError):
            generate_map_text(2, 3, 4)

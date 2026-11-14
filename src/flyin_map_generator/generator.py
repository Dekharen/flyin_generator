"""Seeded generation and serialization of valid Fly-in map files."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import random


class MapShape(str, Enum):
    """Topology styles available to generated maps."""

    CORRIDOR = "corridor"
    BRANCHING = "branching"
    MESH = "mesh"
    SHORTCUT_HEAVY = "shortcut-heavy"
    CHAOTIC = "chaotic"


class MapDistribution(str, Enum):
    """Complete generation presets intended for end users."""

    BALANCED = "balanced"
    HIGH_MOBILITY = "high-mobility"
    SHORTEST_PATH = "shortest-path"
    CYCLIC = "cyclic"
    STRESS = "stress"
    CUSTOM = "custom"


class CapacityScaling(str, Enum):
    """Ways to calculate capacity bounds from the drone count."""

    FLEET_PERCENT = "fleet-percent"
    SQUARE_ROOT = "square-root"
    ABSOLUTE = "absolute"


@dataclass(frozen=True, slots=True)
class CapacityDistribution:
    """Weighted capacity range for zones or connections."""

    scaling: CapacityScaling = CapacityScaling.SQUARE_ROOT
    minimum: int = 1
    minimum_scale: float = 1.0
    maximum_scale: float = 2.0
    probabilities: tuple[float, float, float] = (0.2, 0.5, 0.3)

    def bounds(self, drone_count: int) -> tuple[int, int]:
        """Resolve inclusive capacity bounds for one fleet size."""
        scale = {
            CapacityScaling.FLEET_PERCENT: drone_count,
            CapacityScaling.SQUARE_ROOT: math.sqrt(drone_count),
            CapacityScaling.ABSOLUTE: 1.0,
        }[self.scaling]
        lower = min(drone_count, max(self.minimum, math.ceil(scale * self.minimum_scale)))
        upper = min(drone_count, max(lower, math.ceil(scale * self.maximum_scale)))
        return lower, upper


@dataclass(frozen=True, slots=True)
class RandomizationPolicy:
    """All controls used to construct a generated map."""

    seed: int | None = None
    shape: MapShape = MapShape.BRANCHING
    connected_zone_ratio: float = 0.9
    route_length_ratio: float = 0.35
    minimum_path_ratio: float = 0.5
    cycle_edge_ratio: float = 0.5
    shortcut_edge_ratio: float = 0.2
    branch_spread: float = 0.5
    blocked_probability: float = 0.15
    restricted_probability: float = 0.25
    priority_probability: float = 0.2
    zone_capacity: CapacityDistribution = CapacityDistribution(
        minimum=2, minimum_scale=1.5, maximum_scale=3.0, probabilities=(0.15, 0.45, 0.4)
    )
    edge_capacity: CapacityDistribution = CapacityDistribution(
        minimum=2, minimum_scale=0.4, maximum_scale=1.0, probabilities=(0.5, 0.4, 0.1)
    )

    @classmethod
    def for_shape(cls, shape: MapShape, seed: int | None = None) -> RandomizationPolicy:
        """Return editable defaults for one topology style."""
        values = {
            MapShape.CORRIDOR: (0.7, 0.7, 0.75, 0.1, 0.02, 0.15),
            MapShape.BRANCHING: (0.9, 0.35, 0.5, 0.5, 0.2, 0.5),
            MapShape.MESH: (1.0, 0.25, 0.3, 0.75, 0.05, 0.45),
            MapShape.SHORTCUT_HEAVY: (1.0, 0.3, 0.15, 0.3, 0.45, 0.6),
            MapShape.CHAOTIC: (0.75, 0.3, 0.1, 0.3, 0.2, 1.0),
        }[shape]
        return cls(seed=seed, shape=shape, connected_zone_ratio=values[0], route_length_ratio=values[1], minimum_path_ratio=values[2], cycle_edge_ratio=values[3], shortcut_edge_ratio=values[4], branch_spread=values[5])

    @classmethod
    def for_distribution(cls, distribution: MapDistribution, seed: int | None = None) -> RandomizationPolicy:
        """Return all generation settings for one named preset."""
        if distribution == MapDistribution.BALANCED:
            return cls(seed=seed)
        if distribution == MapDistribution.HIGH_MOBILITY:
            full = CapacityDistribution(CapacityScaling.FLEET_PERCENT, 1, 1.0, 1.0, (0.0, 0.0, 1.0))
            return cls(seed=seed, shape=MapShape.MESH, connected_zone_ratio=1.0, route_length_ratio=0.25, minimum_path_ratio=0.3, cycle_edge_ratio=0.6, shortcut_edge_ratio=0.25, blocked_probability=0.0, restricted_probability=0.0, priority_probability=0.0, zone_capacity=full, edge_capacity=full)
        if distribution == MapDistribution.SHORTEST_PATH:
            return cls(seed=seed, shape=MapShape.SHORTCUT_HEAVY, connected_zone_ratio=1.0, route_length_ratio=0.2, minimum_path_ratio=0.35, cycle_edge_ratio=0.1, shortcut_edge_ratio=0.6, blocked_probability=0.0, restricted_probability=0.0, priority_probability=0.1)
        if distribution == MapDistribution.CYCLIC:
            return cls(seed=seed, shape=MapShape.MESH, connected_zone_ratio=1.0, route_length_ratio=0.25, minimum_path_ratio=0.4, cycle_edge_ratio=0.8, shortcut_edge_ratio=0.0, blocked_probability=0.05, restricted_probability=0.1, priority_probability=0.15)
        if distribution == MapDistribution.STRESS:
            return cls(seed=seed, shape=MapShape.MESH, connected_zone_ratio=1.0, route_length_ratio=0.3, minimum_path_ratio=0.5, cycle_edge_ratio=0.65, shortcut_edge_ratio=0.15, blocked_probability=0.0, restricted_probability=0.1, priority_probability=0.2, zone_capacity=CapacityDistribution(CapacityScaling.ABSOLUTE, 2, 10, 20, (0.3, 0.5, 0.2)), edge_capacity=CapacityDistribution(CapacityScaling.ABSOLUTE, 1, 5, 10, (0.5, 0.4, 0.1)))
        raise ValueError("Custom distribution has no fixed policy")


@dataclass(frozen=True, slots=True)
class _Zone:
    name: str
    x: int
    y: int
    zone_type: str
    capacity: int | None


class _Generator:
    """Build one map without depending on a parser or solver implementation."""

    def __init__(self, drones: int, zones: int, edges: int, policy: RandomizationPolicy) -> None:
        self.drones = drones
        self.zones = zones
        self.edges = edges
        self.policy = policy
        self._validate()
        self.random = random.Random(policy.seed)

    def _validate(self) -> None:
        if any(not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in (self.drones, self.zones, self.edges)):
            raise ValueError("drone_count, zone_count, and edge_count must be positive integers")
        if self.zones < 2:
            raise ValueError("zone_count must include start and end")
        if self.edges > self.zones * (self.zones - 1) // 2:
            raise ValueError("edge_count exceeds the number of unique zone pairs")
        if self.policy.seed is not None and (not isinstance(self.policy.seed, int) or isinstance(self.policy.seed, bool)):
            raise ValueError("seed must be an integer or None")
        for value in (self.policy.connected_zone_ratio, self.policy.route_length_ratio, self.policy.minimum_path_ratio, self.policy.cycle_edge_ratio, self.policy.shortcut_edge_ratio, self.policy.branch_spread, self.policy.blocked_probability, self.policy.restricted_probability, self.policy.priority_probability):
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("policy probabilities and ratios must be between 0 and 1")
        if self.policy.blocked_probability + self.policy.restricted_probability + self.policy.priority_probability > 1:
            raise ValueError("zone type probabilities cannot exceed 100%")
        for distribution in (self.policy.zone_capacity, self.policy.edge_capacity):
            if distribution.minimum <= 0 or distribution.minimum_scale < 0 or distribution.maximum_scale < distribution.minimum_scale:
                raise ValueError("capacity bounds are invalid")
            if len(distribution.probabilities) != 3 or not math.isclose(sum(distribution.probabilities), 1.0) or any(weight < 0 for weight in distribution.probabilities):
                raise ValueError("capacity probabilities must be three nonnegative values totaling 1")

    def build(self) -> str:
        """Generate and serialize the requested map."""
        names = ["start", *(f"zone_{number:03d}" for number in range(1, self.zones - 1)), "end"]
        route_size = min(self.zones, self.edges + 1, max(2, round(self.zones * self.policy.route_length_ratio)))
        route_middle = names[1:-1]
        self.random.shuffle(route_middle)
        route = ["start", *route_middle[:route_size - 2], "end"]
        pairs = {self._pair(left, right) for left, right in zip(route, route[1:])}
        active_target = min(self.zones, self.edges + 1, max(len(route), round(self.zones * self.policy.connected_zone_ratio)))
        active = set(route)
        choices = [name for name in names if name not in active]
        self.random.shuffle(choices)
        active.update(choices[:active_target - len(active)])
        connected = set(route)
        branches = sorted(active - connected)
        self.random.shuffle(branches)
        for branch in branches:
            parent = self.random.choice(sorted(connected))
            pairs.add(self._pair(branch, parent))
            connected.add(branch)
        candidates = [self._pair(left, right) for index, left in enumerate(names) for right in names[index + 1:] if self._pair(left, right) not in pairs]
        self.random.shuffle(candidates)
        pairs.update(candidates[:self.edges - len(pairs)])
        return self._serialize(names, route, pairs)

    def _serialize(self, names: list[str], route: list[str], pairs: set[tuple[str, str]]) -> str:
        route_names = set(route)
        zones: list[_Zone] = []
        for index, name in enumerate(names):
            if name == "start":
                zones.append(_Zone(name, 0, 0, "normal", None))
            elif name == "end":
                zones.append(_Zone(name, max(4, self.zones // 2), 0, "normal", None))
            else:
                zone_type = "normal" if name in route_names else self._zone_type()
                zones.append(_Zone(name, index + 1, self.random.randint(-3, 3), zone_type, self._capacity(self.policy.zone_capacity)))
        lines = [f"nb_drones: {self.drones}", ""]
        for zone in zones:
            prefix = "start_hub" if zone.name == "start" else "end_hub" if zone.name == "end" else "hub"
            metadata = "" if zone.capacity is None else f" [zone={zone.zone_type} max_drones={zone.capacity}]"
            lines.append(f"{prefix}: {zone.name} {zone.x} {zone.y}{metadata}")
        lines.append("")
        for left, right in sorted(pairs):
            lines.append(f"connection: {left}-{right} [max_link_capacity={self._capacity(self.policy.edge_capacity)}]")
        return "\n".join(lines) + "\n"

    def _zone_type(self) -> str:
        roll = self.random.random()
        if roll < self.policy.blocked_probability:
            return "blocked"
        if roll < self.policy.blocked_probability + self.policy.restricted_probability:
            return "restricted"
        if roll < self.policy.blocked_probability + self.policy.restricted_probability + self.policy.priority_probability:
            return "priority"
        return "normal"

    def _capacity(self, distribution: CapacityDistribution) -> int:
        lower, upper = distribution.bounds(self.drones)
        tier = self.random.choices(range(3), weights=distribution.probabilities, k=1)[0]
        count = upper - lower + 1
        base, remainder = divmod(count, 3)
        sizes = [base + int(index < remainder) for index in range(3)]
        available = [index for index, size in enumerate(sizes) if size]
        if tier not in available:
            tier = available[-1]
        band_start = lower + sum(sizes[:tier])
        return self.random.randint(band_start, band_start + sizes[tier] - 1)

    @staticmethod
    def _pair(left: str, right: str) -> tuple[str, str]:
        return (left, right) if left < right else (right, left)


def generate_map_text(drone_count: int, zone_count: int, edge_count: int, policy: RandomizationPolicy | None = None) -> str:
    """Return one valid Fly-in map in the subject's plain-text format."""
    return _Generator(drone_count, zone_count, edge_count, policy or RandomizationPolicy()).build()

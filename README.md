# Fly-in Map Generator

Dependency-free Python library for generating valid Fly-in map text. Generated text is UTF-8-ready and can be written directly to a `.txt` input file.

Requires Python 3.10 or later.

## Installation

Install the published package:

```bash
pip install flyin-map-generator
```

To install from a checked-out source repository instead:

```bash
pip install .
```

For an editable development installation:

```bash
pip install -e .
```

## Quick Start

Create a map with 10 drones, 25 zones, and 35 connections. A seed makes the result repeatable.

```python
from pathlib import Path

from flyin_map_generator import RandomizationPolicy, generate_map_text

policy = RandomizationPolicy(seed=42)
map_text = generate_map_text(
    drone_count=10,
    zone_count=25,
    edge_count=35,
    policy=policy,
)

Path("generated-map.txt").write_text(map_text, encoding="utf-8")
```

## Public API

Import every public type from `flyin_map_generator`:

```python
from flyin_map_generator import (
    CapacityDistribution,
    CapacityScaling,
    MapDistribution,
    MapShape,
    RandomizationPolicy,
    generate_map_text,
)
```

### `generate_map_text`

```python
generate_map_text(drone_count, zone_count, edge_count, policy=None) -> str
```

Generates a newline-terminated string in Fly-in's plain-text map format. When `policy` is omitted, `RandomizationPolicy()` is used.

| Argument | Description |
| --- | --- |
| `drone_count` | Positive number of drones in the generated map. |
| `zone_count` | Positive number of zones, including the start and end hubs. Must be at least `2`. |
| `edge_count` | Positive number of undirected connections. It cannot exceed `zone_count * (zone_count - 1) // 2`. |
| `policy` | Optional `RandomizationPolicy` controlling seeded randomness, connectivity, zone types, and capacities. |

All three count arguments must be integers, not booleans. Invalid counts or policy values raise `ValueError`.

## Randomization Policy

`RandomizationPolicy` is a frozen dataclass. Create it with the settings you need, then pass it to `generate_map_text`. Its default values are suitable for a balanced, branching-style map.

For more visually impressive maps, I'd recommend using the `Cyclic` or `Stress` options.

```python
policy = RandomizationPolicy(
    seed=42,
    connected_zone_ratio=1.0,
    blocked_probability=0.05,
)
```

| Setting | Default | Description |
| --- | --- | --- |
| `seed` | `None` | Integer seed for repeatable output; `None` uses fresh randomness. |
| `shape` | `MapShape.BRANCHING` | Topology label selected directly or through `for_shape()`. See the note below about current behavior. |
| `connected_zone_ratio` | `0.9` | Target fraction of zones attached to the generated route or branches. |
| `route_length_ratio` | `0.35` | Target fraction of zones in the guaranteed route from start to end. |
| `minimum_path_ratio` | `0.5` | Reserved topology setting; currently does not change generation. |
| `cycle_edge_ratio` | `0.5` | Reserved topology setting; currently does not change generation. |
| `shortcut_edge_ratio` | `0.2` | Reserved topology setting; currently does not change generation. |
| `branch_spread` | `0.5` | Reserved topology setting; currently does not change generation. |
| `blocked_probability` | `0.15` | Probability that an eligible zone is blocked. |
| `restricted_probability` | `0.25` | Probability that an eligible zone is restricted. |
| `priority_probability` | `0.2` | Probability that an eligible zone is a priority zone. |
| `zone_capacity` | See below | `CapacityDistribution` used for non-hub zones. |
| `edge_capacity` | See below | `CapacityDistribution` used for connections. |

Ratios and probabilities must be finite values from `0` through `1`. The three zone-type probabilities combined cannot exceed `1`. Start and end hubs, along with zones on the guaranteed route, are always normal; zone-type probabilities apply to other zones.

`shape` records the selected topology style, but it is not itself consumed by the current generator. The four reserved topology settings are also accepted and validated, but do not currently alter the generated map. `for_shape()` remains useful because it sets related active values such as `connected_zone_ratio` and `route_length_ratio`.

### Shape Factories

Use `for_shape(shape, seed=None)` to start with editable settings for a named topology style:

```python
policy = RandomizationPolicy.for_shape(MapShape.CORRIDOR, seed=42)
```

Available `MapShape` values are:

| Value | Meaning |
| --- | --- |
| `MapShape.CORRIDOR` | Corridor-oriented preset. |
| `MapShape.BRANCHING` | Default branching-oriented preset. |
| `MapShape.MESH` | Dense mesh-oriented preset. |
| `MapShape.SHORTCUT_HEAVY` | Shortcut-oriented preset. |
| `MapShape.CHAOTIC` | Widely branching preset. |

### Distribution Factories

Use `for_distribution(distribution, seed=None)` for complete end-user presets:

```python
policy = RandomizationPolicy.for_distribution(
    MapDistribution.HIGH_MOBILITY,
    seed=42,
)
```

| Value | Meaning |
| --- | --- |
| `MapDistribution.BALANCED` | The default policy. |
| `MapDistribution.HIGH_MOBILITY` | All zones are active, with fleet-sized zone and connection capacities. |
| `MapDistribution.SHORTEST_PATH` | Shortcut-oriented policy with no blocked or restricted zones. |
| `MapDistribution.CYCLIC` | Mesh-oriented cyclic policy. |
| `MapDistribution.STRESS` | Mesh-oriented policy with fixed, constrained capacities. |
| `MapDistribution.CUSTOM` | Marker for application-defined settings; passing it to `for_distribution()` raises `ValueError`. |

## Capacity Distributions

`CapacityDistribution` controls the range and weighting of capacities for zones or connections:

```python
from flyin_map_generator import CapacityDistribution, CapacityScaling

zone_capacity = CapacityDistribution(
    scaling=CapacityScaling.FLEET_PERCENT,
    minimum=1,
    minimum_scale=0.25,
    maximum_scale=0.75,
    probabilities=(0.2, 0.5, 0.3),
)

policy = RandomizationPolicy(zone_capacity=zone_capacity)
```

| Setting | Default | Description |
| --- | --- | --- |
| `scaling` | `CapacityScaling.SQUARE_ROOT` | Base used to calculate bounds. |
| `minimum` | `1` | Absolute floor for a capacity. Must be positive. |
| `minimum_scale` | `1.0` | Multiplier for the lower bound. Must be nonnegative. |
| `maximum_scale` | `2.0` | Multiplier for the upper bound. Must be at least `minimum_scale`. |
| `probabilities` | `(0.2, 0.5, 0.3)` | Weights for the lower, middle, and upper thirds of the inclusive capacity range. Values must be nonnegative and total `1`. |

Capacity bounds are capped at `drone_count`. Call `bounds(drone_count)` to inspect the inclusive range that a distribution resolves to:

```python
distribution = CapacityDistribution(CapacityScaling.ABSOLUTE, 2, 5, 10)
lower, upper = distribution.bounds(drone_count=20)
# (5, 10)
```

Available `CapacityScaling` values are:

| Value | Bound-calculation base |
| --- | --- |
| `CapacityScaling.FLEET_PERCENT` | The full drone count. |
| `CapacityScaling.SQUARE_ROOT` | The square root of the drone count. |
| `CapacityScaling.ABSOLUTE` | `1`, so scales act as absolute values. |

The default policy uses these capacity distributions:

```python
RandomizationPolicy(
    zone_capacity=CapacityDistribution(
        minimum=2,
        minimum_scale=1.5,
        maximum_scale=3.0,
        probabilities=(0.15, 0.45, 0.4),
    ),
    edge_capacity=CapacityDistribution(
        minimum=2,
        minimum_scale=0.4,
        maximum_scale=1.0,
        probabilities=(0.5, 0.4, 0.1),
    ),
)
```

"""Public 15-unit synthetic fleet example with independent per-unit histories.

Design pattern: each unit has its own operating-point and degradation draw.
Unlike historical circular-time-shift demonstrations, no base-unit trace is
shifted or replicated. Values are invented for illustration; this module is
NOT a production simulator or a replacement for the private physics model.
No third-party packages required.
"""
import csv
import random
from pathlib import Path

UNITS = 15
STEPS = 48  # illustrative time steps, not plant hours


def simulate_unit(unit_id: int, steps: int = STEPS, seed: int = 2026):
    if not 1 <= unit_id <= UNITS or steps < 1:
        raise ValueError("Invalid unit or step count")
    rng = random.Random(seed + 10_007 * unit_id)
    baseline = rng.uniform(0.88, 1.12)
    degradation_rate = rng.uniform(0.0001, 0.001)
    drift = 0.0
    for tick in range(steps):
        drift += degradation_rate * rng.uniform(0.8, 1.2)
        condition = baseline * (1.0 - drift)
        measurement = condition + rng.gauss(0.0, 0.004)
        yield {
            "unit_id": f"T{unit_id:02d}",
            "step": tick,
            "normalized_condition": round(condition, 6),
            "measurement": round(measurement, 6),
            "synthetic": True,
        }


def generate_fleet(steps: int = STEPS, seed: int = 2026):
    for unit_id in range(1, UNITS + 1):
        yield from simulate_unit(unit_id, steps, seed)


def validate_demo():
    rows = list(generate_fleet())
    assert len(rows) == UNITS * STEPS
    assert len({row["unit_id"] for row in rows}) == UNITS
    assert rows == list(generate_fleet())  # repeatable under fixed seed
    first = [next(iter(simulate_unit(i)))["normalized_condition"]
             for i in range(1, UNITS + 1)]
    assert len(set(first)) == UNITS  # independently parameterized units


if __name__ == "__main__":
    validate_demo()
    output = Path("synthetic_fleet_example.csv")
    with output.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["unit_id", "step", "normalized_condition",
                            "measurement", "synthetic"])
        writer.writeheader()
        writer.writerows(generate_fleet())
    print(f"Created {output}: demo checks PASS, synthetic data only")

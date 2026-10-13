"""Public, deliberately synthetic engineering assumptions.

Educational example informed by a physics/controls Digital Twin architecture.
NOT site data, OEM values, a validated SGT-400 performance map, or safety limits.
"""
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class CompressorStage:
    name: str
    inlet_pressure_bar: float
    pressure_ratio: float
    inlet_temperature_k: float
    efficiency: float

    def __post_init__(self):
        values = (self.inlet_pressure_bar, self.pressure_ratio,
                  self.inlet_temperature_k, self.efficiency)
        if not all(isfinite(v) for v in values):
            raise ValueError("Stage parameters must be finite")
        if self.inlet_pressure_bar <= 0 or self.inlet_temperature_k <= 0:
            raise ValueError("Use positive absolute pressure and temperature")
        if self.pressure_ratio <= 1:
            raise ValueError("Compressor pressure ratio must exceed one")
        if not (0 < self.efficiency <= 1):
            raise ValueError("Efficiency must be in (0, 1]")

    @property
    def discharge_pressure_bar(self) -> float:
        return self.inlet_pressure_bar * self.pressure_ratio


# Illustrative numbers chosen for demonstration, NOT machine specifications.
DEMO_LP = CompressorStage("Illustrative LP", 2.0, 2.0, 295.0, 0.78)
DEMO_HP = CompressorStage("Illustrative HP", 4.0, 2.0, 305.0, 0.80)


def validate_example() -> None:
    assert DEMO_LP.discharge_pressure_bar == DEMO_HP.inlet_pressure_bar
    assert DEMO_HP.discharge_pressure_bar > DEMO_LP.discharge_pressure_bar


if __name__ == "__main__":
    validate_example()
    print("Public example validation: PASS (not an industrial acceptance test)")

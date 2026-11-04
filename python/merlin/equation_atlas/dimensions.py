"""Small SI base-dimension algebra for equation-atlas sanity checks.

Dimension order: length, mass, time, electric current, temperature,
amount of substance, luminous intensity. This checks dimensional
homogeneity; it does not prove a physical model is correct.
"""
from dataclasses import dataclass
from typing import Iterable

@dataclass(frozen=True)
class Dimension:
    powers: tuple[int, int, int, int, int, int, int]

    def __mul__(self, other: "Dimension") -> "Dimension":
        return Dimension(tuple(a + b for a, b in zip(self.powers, other.powers)))

    def __truediv__(self, other: "Dimension") -> "Dimension":
        return Dimension(tuple(a - b for a, b in zip(self.powers, other.powers)))

    def __pow__(self, exponent: int) -> "Dimension":
        return Dimension(tuple(exponent * a for a in self.powers))

    def __str__(self) -> str:
        names = ("L", "M", "T", "I", "Theta", "N", "J")
        terms = [f"{name}^{power}" for name, power in zip(names, self.powers) if power]
        return "1" if not terms else " ".join(terms)

DIMENSIONLESS = Dimension((0, 0, 0, 0, 0, 0, 0))
LENGTH = Dimension((1, 0, 0, 0, 0, 0, 0))
MASS = Dimension((0, 1, 0, 0, 0, 0, 0))
TIME = Dimension((0, 0, 1, 0, 0, 0, 0))
CURRENT = Dimension((0, 0, 0, 1, 0, 0, 0))
TEMPERATURE = Dimension((0, 0, 0, 0, 1, 0, 0))
AMOUNT = Dimension((0, 0, 0, 0, 0, 1, 0))
LUMINOUS_INTENSITY = Dimension((0, 0, 0, 0, 0, 0, 1))

VELOCITY = LENGTH / TIME
ACCELERATION = LENGTH / (TIME ** 2)
FORCE = MASS * ACCELERATION
ENERGY = FORCE * LENGTH
PRESSURE = FORCE / (LENGTH ** 2)
DYNAMIC_VISCOSITY = PRESSURE * TIME
AREA = LENGTH ** 2
VOLUME = LENGTH ** 3
HEAT_DIFFUSIVITY = AREA / TIME
POPULATION_RATE = DIMENSIONLESS / TIME

def require_same(lhs: Dimension, rhs: Dimension, equation: str) -> None:
    if lhs != rhs:
        raise ValueError(f"Dimension mismatch in {equation}: lhs={lhs}, rhs={rhs}")

def core_dimension_checks() -> dict[str, str]:
    """Check representative equation families; raises on first mismatch."""
    checks: dict[str, tuple[Dimension, Dimension]] = {
        "heat_equation": (
            TEMPERATURE / TIME,
            HEAT_DIFFUSIVITY * (TEMPERATURE / AREA),
        ),
        "wave_equation": (
            TEMPERATURE / (TIME ** 2),
            (VELOCITY ** 2) * (TEMPERATURE / AREA),
        ),
        "logistic_growth": (
            AMOUNT / TIME,
            POPULATION_RATE * AMOUNT,
        ),
        "conservation_law": (
            MASS / (VOLUME * TIME),
            (MASS / (AREA * TIME)) / LENGTH,
        ),
        "darcy_flow_rate": (
            VOLUME / TIME,
            (AREA * AREA * PRESSURE) / (DYNAMIC_VISCOSITY * LENGTH),
        ),
        "linear_elasticity": (
            PRESSURE,
            PRESSURE * DIMENSIONLESS,
        ),
        "kinetic_energy": (
            ENERGY,
            MASS * (VELOCITY ** 2),
        ),
        "fourier_transform": (
            DIMENSIONLESS * TIME,
            DIMENSIONLESS * TIME,
        ),
    }
    result = {}
    for name, (lhs, rhs) in checks.items():
        require_same(lhs, rhs, name)
        result[name] = str(lhs)
    return result

if __name__ == "__main__":
    for name, dimension in core_dimension_checks().items():
        print(f"PASS {name}: {dimension}")

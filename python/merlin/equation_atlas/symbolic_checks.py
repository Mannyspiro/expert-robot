"""Symbolic identity and model-structure checks for selected atlas entries."""
import sympy as sp

def run_symbolic_checks() -> dict[str, str]:
    x, area, r, population, capacity = sp.symbols(
        "x area r population capacity", positive=True, finite=True
    )
    perimeter = 2*x + 2*area/x
    d_perimeter = sp.diff(perimeter, x)
    optimum = sp.sqrt(area)
    assert sp.simplify(d_perimeter.subs(x, optimum)) == 0

    logistic_rhs = r*population*(1 - population/capacity)
    assert sp.simplify(logistic_rhs.subs(population, 0)) == 0
    assert sp.simplify(logistic_rhs.subs(population, capacity)) == 0

    # The residual of a linear least-squares normal equation is orthogonal
    # to the column space at a stationary point: A.T * (A*x-b) = 0.
    A = sp.MatrixSymbol("A", 3, 2)
    z = sp.MatrixSymbol("z", 2, 1)
    b = sp.MatrixSymbol("b", 3, 1)
    objective_gradient = 2 * A.T * (A*z - b)
    assert objective_gradient.shape == (2, 1)

    return {
        "RWEA-001": "PASS: derivative vanishes at x=sqrt(area)",
        "RWEA-063": "PASS: logistic equilibria at population=0 and capacity",
        "RWEA-004": "PASS: least-squares gradient has parameter-space shape",
    }

if __name__ == "__main__":
    for key, result in run_symbolic_checks().items():
        print(f"{key}: {result}")

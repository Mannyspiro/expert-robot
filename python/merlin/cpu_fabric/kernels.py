"""Deterministic CPU-native matrix kernel baseline."""

def tiled_matmul(a, b, tile=24):
    if not a or not b or len(a[0]) != len(b) or tile < 1:
        raise ValueError("invalid matrix dimensions or tile")
    m, k, n = len(a), len(b), len(b[0])
    if any(len(r) != k for r in a) or any(len(r) != n for r in b):
        raise ValueError("ragged matrices are unsupported")
    c = [[0.0] * n for _ in range(m)]
    for ii in range(0, m, tile):
        for kk in range(0, k, tile):
            for jj in range(0, n, tile):
                for i in range(ii, min(ii + tile, m)):
                    for p in range(kk, min(kk + tile, k)):
                        ap = a[i][p]
                        for j in range(jj, min(jj + tile, n)):
                            c[i][j] += ap * b[p][j]
    return c

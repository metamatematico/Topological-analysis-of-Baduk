"""
Fase 1 — Pattern representations as metric/combinatorial spaces.

A canonical Go pattern is a tuple[tuple[str,...], ...] of shape (19, 19).
Cell vocabulary: 'b' (current player stone), 'w' (opponent stone),
'+' (empty, interior), '/' (first board line / edge), '.' (off-board).

Two primary representations are provided:

R1 — Point cloud in R²
    Stone positions (row, col) ∈ [0, 18]² for every cell that is 'b' or 'w'.
    Metric: standard Euclidean distance in R².
    This is meaningful for individual-pattern TDA (H₀ = connected stone
    components, H₁ = loops / eyes).

R2 — Feature vector in R^361
    Each of the 361 cells is encoded as a real number and flattened.
    Encoding: +1 (own stone 'b'), -1 (opponent stone 'w'), 0 (empty '+'),
    -0.5 (board edge '/'), -2 (off-board '.').
    Inter-pattern distance: Euclidean on R^361.
    This is meaningful for cross-pattern TDA (topology of the pattern space).

R3 — Weighted graph (NetworkX)
    Nodes = (row, col) for every stone cell.
    Edges = 4-connected neighbours among stone cells; weight = 1.
    Filtration value = edge weight (clique complex filtered by weight).
"""

from __future__ import annotations

import numpy as np
import networkx as nx
from typing import Sequence

# Cell encoding for R2 feature vectors
_CELL_CODE: dict[str, float] = {
    'b': +1.0,
    'w': -1.0,
    '+': 0.0,
    '/': -0.5,
    '.': -2.0,
}

Pattern = tuple  # tuple[tuple[str, ...], ...], shape (19, 19)


# ---------------------------------------------------------------------------
# R1 — Point cloud
# ---------------------------------------------------------------------------

def pattern_to_pointcloud(pattern: Pattern) -> np.ndarray:
    """Return stone positions as a point cloud in R².

    Parameters
    ----------
    pattern:
        Canonical 19×19 Go pattern.

    Returns
    -------
    pts : np.ndarray, shape (n_stones, 2), dtype float64
        Rows are (row, col) coordinates of every cell whose value is 'b' or 'w'.
        Returns shape (0, 2) if the pattern has no stones.
    """
    pts = [
        (r, c)
        for r, row in enumerate(pattern)
        for c, cell in enumerate(row)
        if cell in ('b', 'w')
    ]
    if not pts:
        return np.empty((0, 2), dtype=np.float64)
    return np.array(pts, dtype=np.float64)


def pointcloud_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two points in R².

    Satisfies: non-negativity, symmetry, triangle inequality.
    """
    return float(np.linalg.norm(a - b))


# ---------------------------------------------------------------------------
# R2 — Feature vector
# ---------------------------------------------------------------------------

def pattern_to_feature_vector(pattern: Pattern) -> np.ndarray:
    """Encode a 19×19 pattern as a flat real-valued vector in R^361.

    Encoding (see module docstring for rationale):
        'b' →  1.0,  'w' → -1.0,  '+' → 0.0,  '/' → -0.5,  '.' → -2.0

    Parameters
    ----------
    pattern:
        Canonical 19×19 Go pattern.

    Returns
    -------
    vec : np.ndarray, shape (361,), dtype float64
    """
    vec = np.array(
        [_CELL_CODE.get(cell, 0.0) for row in pattern for cell in row],
        dtype=np.float64,
    )
    return vec


def feature_vector_distance(u: np.ndarray, v: np.ndarray) -> float:
    """Euclidean distance between two feature vectors.

    For binary patterns this equals the Frobenius norm of the difference
    matrix, which is proportional to Hamming distance on the binarised grid.
    """
    return float(np.linalg.norm(u - v))


def pattern_distance_matrix(patterns: Sequence[Pattern]) -> np.ndarray:
    """Compute the N×N inter-pattern Euclidean distance matrix via R2.

    Parameters
    ----------
    patterns:
        Sequence of N canonical Go patterns.

    Returns
    -------
    D : np.ndarray, shape (N, N), dtype float64
        Symmetric matrix with D[i, j] = feature_vector_distance(patterns[i], patterns[j]).
    """
    vecs = np.stack([pattern_to_feature_vector(p) for p in patterns])
    # Gram-matrix trick for Euclidean distances: O(N²·d) but vectorised
    sq = np.sum(vecs ** 2, axis=1, keepdims=True)
    D = np.sqrt(np.maximum(sq + sq.T - 2.0 * vecs @ vecs.T, 0.0))
    return D


# ---------------------------------------------------------------------------
# R3 — Weighted graph
# ---------------------------------------------------------------------------

def pattern_to_graph(pattern: Pattern) -> nx.Graph:
    """Build a weighted graph of stone positions for a single pattern.

    Nodes represent cells containing a stone ('b' or 'w').
    Edges connect 4-connected neighbours (up, down, left, right) among stone
    cells, with weight = 1 (unit grid adjacency).

    The graph is suitable for building a clique complex filtered by edge weight.

    Parameters
    ----------
    pattern:
        Canonical 19×19 Go pattern.

    Returns
    -------
    G : nx.Graph
        Nodes have attribute 'color' ∈ {'b', 'w'}.
        Edges have attribute 'weight' = 1.
    """
    G = nx.Graph()
    for r, row in enumerate(pattern):
        for c, cell in enumerate(row):
            if cell in ('b', 'w'):
                G.add_node((r, c), color=cell)

    neighbours = [(0, 1), (0, -1), (1, 0), (-1, 0)]
    for (r, c) in list(G.nodes):
        for dr, dc in neighbours:
            nb = (r + dr, c + dc)
            if nb in G.nodes and not G.has_edge((r, c), nb):
                G.add_edge((r, c), nb, weight=1)

    return G


# ---------------------------------------------------------------------------
# Synthetic patterns for testing
# ---------------------------------------------------------------------------

def empty_pattern() -> Pattern:
    """Return a canonical pattern with no stones (all '+', interior only)."""
    return tuple(tuple('+' for _ in range(19)) for _ in range(19))


def make_synthetic_pattern(stone_positions: Sequence[tuple[int, int]]) -> Pattern:
    """Create a 19×19 pattern with 'b' stones at given (row, col) positions.

    All other interior cells are '+'. No edge or off-board handling.

    Parameters
    ----------
    stone_positions:
        Iterable of (row, col) pairs, each in [0, 18].

    Returns
    -------
    pattern : Pattern
    """
    grid = [list('+' * 19) for _ in range(19)]
    for r, c in stone_positions:
        grid[r][c] = 'b'
    return tuple(tuple(row) for row in grid)

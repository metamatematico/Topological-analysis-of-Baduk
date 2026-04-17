"""
Fase 2 — Simplicial complexes and filtrations.

Three constructions are provided, all backed by gudhi:

VR  — Vietoris–Rips complex
    Built from an R1 point cloud (stone positions in R²) or from an R2
    distance matrix, filtered by scale ε.  For a set of points X with
    metric d, the Vietoris–Rips complex VR(X, ε) contains simplex σ iff
    d(x_i, x_j) ≤ ε for all x_i, x_j ∈ σ.
    gudhi.RipsComplex implements this via the 1-skeleton + flag complex
    expansion (equivalent to the full VR complex for flag complexes).

Alpha — Alpha complex (replaces Čech for R² / R³)
    The Alpha complex is a sub-complex of the Delaunay triangulation.
    By the nerve lemma, Alpha(X, α) ≃ VR(X, 2√α) topologically when
    X ⊂ Rᵈ, d ≤ 3, making it strictly tighter than VR at equal radius.
    gudhi.AlphaComplex implements this exactly.
    Čech complex is NOT implemented separately: for d=2 the Alpha complex
    computes the same persistent homology as Čech with better performance.

Clique — Clique complex (flag complex) from a weighted graph (R3)
    Given a weighted graph G, the clique complex K(G) contains simplex σ
    iff every pair of nodes in σ is connected by an edge.  Filtered by
    edge weight w (sub-level set: include edges with w ≤ ε).
    gudhi.SimplexTree is populated from the 1-skeleton (edges of G);
    expansion to higher simplices is performed by the flag complex
    (gudhi.SimplexTree.expansion).

All functions return a gudhi.SimplexTree ready for persistence computation.
"""

from __future__ import annotations

import numpy as np
import gudhi
import networkx as nx
from typing import Optional

from candela.tda.representation import (
    pattern_to_pointcloud,
    pattern_to_graph,
    pattern_distance_matrix,
    Pattern,
)


# ---------------------------------------------------------------------------
# Vietoris–Rips complex
# ---------------------------------------------------------------------------

def vietoris_rips_complex(
    points: np.ndarray,
    max_edge_length: float = 10.0,
    max_dimension: int = 2,
) -> gudhi.SimplexTree:
    """Build the Vietoris–Rips simplex tree from a point cloud.

    Parameters
    ----------
    points:
        Point cloud, shape (n, d), dtype float64.
    max_edge_length:
        Maximum filtration radius ε.  All edges with Euclidean length ≤ ε
        are included in the 1-skeleton before expansion.
    max_dimension:
        Maximum homological dimension (simplex dimension = max_dimension).

    Returns
    -------
    st : gudhi.SimplexTree
        Simplex tree with filtration values equal to the length of the
        longest edge in each simplex (VR filtration convention).
    """
    if points.shape[0] == 0:
        return gudhi.SimplexTree()
    rc = gudhi.RipsComplex(points=points, max_edge_length=max_edge_length)
    st = rc.create_simplex_tree(max_dimension=max_dimension)
    return st


def vietoris_rips_from_distance_matrix(
    D: np.ndarray,
    max_edge_length: float = 100.0,
    max_dimension: int = 1,
) -> gudhi.SimplexTree:
    """Build the Vietoris–Rips simplex tree from a precomputed distance matrix.

    Used for cross-pattern TDA where D is the N×N inter-pattern distance matrix.

    Parameters
    ----------
    D:
        Symmetric N×N distance matrix, non-negative, zero diagonal.
    max_edge_length:
        Maximum filtration value.
    max_dimension:
        Maximum simplex dimension.

    Returns
    -------
    st : gudhi.SimplexTree
    """
    rc = gudhi.RipsComplex(distance_matrix=D, max_edge_length=max_edge_length)
    st = rc.create_simplex_tree(max_dimension=max_dimension)
    return st


# ---------------------------------------------------------------------------
# Alpha complex (replaces Čech in R²/R³)
# ---------------------------------------------------------------------------

def alpha_complex(
    points: np.ndarray,
    precision: str = "safe",
) -> gudhi.SimplexTree:
    """Build the Alpha complex simplex tree from a point cloud in Rᵈ, d ≤ 3.

    The Alpha complex is a sub-complex of the Delaunay triangulation.
    For d=2, Alpha(X, α) is topologically equivalent to Čech(X, √α).
    Filtration values are α (squared circumradius), NOT ε.

    Note: gudhi AlphaComplex requires d ≤ 3 and uses CGAL under the hood.
    Čech is not implemented separately: for the dimensionalities occurring
    in this project (d=2), Alpha is the canonical exact Čech substitute.

    Parameters
    ----------
    points:
        Point cloud, shape (n, d), d ≤ 3.
    precision:
        One of "fast", "safe", "exact" — passed to gudhi.AlphaComplex.

    Returns
    -------
    st : gudhi.SimplexTree
        Filtration values are squared circumradii (α parameter).
        To convert to radius: r = √α.
    """
    if points.shape[0] < 2:
        return gudhi.SimplexTree()
    ac = gudhi.AlphaComplex(points=points, precision=precision)
    st = ac.create_simplex_tree()
    return st


# ---------------------------------------------------------------------------
# Clique (flag) complex from weighted graph
# ---------------------------------------------------------------------------

def clique_complex_from_graph(
    G: nx.Graph,
    max_dimension: int = 2,
    filtration_attr: str = "weight",
) -> gudhi.SimplexTree:
    """Build a flag complex from a weighted NetworkX graph.

    The filtration value of edge (u, v) is G[u][v][filtration_attr].
    Higher-dimensional simplices inherit the maximum filtration value
    of their constituent edges (flag / VR convention).

    The sub-level-set filtration: simplex σ enters at filtration value
    equal to the maximum edge weight among all edges of σ.

    Parameters
    ----------
    G:
        Weighted undirected graph.  Nodes can be any hashable (e.g. (row, col)).
    max_dimension:
        Maximum simplex dimension for flag complex expansion.
    filtration_attr:
        Edge attribute name used as filtration value.

    Returns
    -------
    st : gudhi.SimplexTree
    """
    st = gudhi.SimplexTree()
    # Map node labels to consecutive integers (gudhi requires integer vertices)
    nodes = list(G.nodes())
    node_idx = {n: i for i, n in enumerate(nodes)}

    # Insert 0-simplices
    for n in nodes:
        st.insert([node_idx[n]], filtration=0.0)

    # Insert 1-simplices with filtration = edge weight
    for u, v, data in G.edges(data=True):
        w = float(data.get(filtration_attr, 1.0))
        st.insert([node_idx[u], node_idx[v]], filtration=w)

    # Expand to flag complex up to max_dimension
    st.expansion(max_dimension)
    return st


# ---------------------------------------------------------------------------
# Convenience wrapper: pattern → simplex tree
# ---------------------------------------------------------------------------

def pattern_to_rips_tree(
    pattern: Pattern,
    max_edge_length: float = 10.0,
    max_dimension: int = 2,
) -> gudhi.SimplexTree:
    """Shortcut: canonical pattern → VR simplex tree via R1 (stone positions).

    Parameters
    ----------
    pattern:
        Canonical 19×19 Go pattern.
    max_edge_length:
        VR filtration radius.
    max_dimension:
        Maximum simplex dimension.

    Returns
    -------
    st : gudhi.SimplexTree
    """
    pts = pattern_to_pointcloud(pattern)
    return vietoris_rips_complex(pts, max_edge_length=max_edge_length, max_dimension=max_dimension)


def pattern_to_alpha_tree(pattern: Pattern) -> gudhi.SimplexTree:
    """Shortcut: canonical pattern → Alpha simplex tree via R1."""
    pts = pattern_to_pointcloud(pattern)
    return alpha_complex(pts)


def pattern_to_clique_tree(pattern: Pattern, max_dimension: int = 2) -> gudhi.SimplexTree:
    """Shortcut: canonical pattern → clique complex simplex tree via R3."""
    G = pattern_to_graph(pattern)
    return clique_complex_from_graph(G, max_dimension=max_dimension)

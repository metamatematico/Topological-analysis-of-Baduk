"""
Fase 4 — Distances between persistence diagrams and pattern cohorts.

Three families of distances are implemented:

1. Bottleneck distance (d_B)
   d_B(X, Y) = inf_{γ: perfect matching} sup_{x ∈ X} ‖x - γ(x)‖_∞
   where γ ranges over all perfect matchings between X ∪ Δ and Y ∪ Δ
   (diagonal points are added to make matching possible).
   Implemented via gudhi.bottleneck_distance.

2. p-Wasserstein distance (W_p)
   W_p(X, Y) = (inf_{γ} Σ ‖x - γ(x)‖_∞^p)^{1/p}
   Implemented via gudhi.wasserstein.wasserstein_distance.

3. L^q distance between persistence landscapes
   d_q(λ, μ) = ‖λ - μ‖_{L^q} ≈ (Σ_k ∫ |λ_k(t) - μ_k(t)|^q dt)^{1/q}
   Discretised as L^q norm on the stacked landscape arrays.

All diagram inputs are np.ndarray of shape (n, 2) with columns [birth, death].
Infinite bars are handled via gudhi's internal mechanism (they are matched to
diagonal at infinity); finite diagrams are used for landscape distances.

Output matrices are saved to `outputs/tda/distances/` as .npy files.
"""

from __future__ import annotations

import numpy as np
import gudhi
import gudhi.wasserstein
from pathlib import Path
from typing import Sequence

from candela.tda.persistence import persistence_landscape, filter_infinite, Diagram

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs" / "tda" / "distances"


# ---------------------------------------------------------------------------
# Bottleneck distance
# ---------------------------------------------------------------------------

def bottleneck_distance(dgm_a: Diagram, dgm_b: Diagram) -> float:
    """Compute the bottleneck distance between two persistence diagrams.

    d_B(X, Y) = inf_{γ} sup_{x} ‖x - γ(x)‖_∞

    Parameters
    ----------
    dgm_a, dgm_b:
        Persistence diagrams, shape (n, 2) and (m, 2).
        Infinite bars are forwarded to gudhi (handled internally).
        Empty diagrams are represented as np.empty((0, 2)).

    Returns
    -------
    dist : float ≥ 0
    """
    a = np.asarray(dgm_a, dtype=np.float64)
    b = np.asarray(dgm_b, dtype=np.float64)
    if a.size == 0 and b.size == 0:
        return 0.0
    return float(gudhi.bottleneck_distance(a, b))


def wasserstein_distance(dgm_a: Diagram, dgm_b: Diagram, order: float = 1.0) -> float:
    """Compute the p-Wasserstein distance between two persistence diagrams.

    W_p(X, Y) = (inf_{γ} Σ ‖x - γ(x)‖_∞^p)^{1/p}

    Parameters
    ----------
    dgm_a, dgm_b:
        Persistence diagrams, shape (n, 2) and (m, 2).
    order:
        p in W_p (p=1 = standard Wasserstein, p=2 = squared Wasserstein).

    Returns
    -------
    dist : float ≥ 0
    """
    a = np.asarray(dgm_a, dtype=np.float64)
    b = np.asarray(dgm_b, dtype=np.float64)
    if a.size == 0 and b.size == 0:
        return 0.0
    return float(
        gudhi.wasserstein.wasserstein_distance(a, b, order=order, internal_p=np.inf)
    )


# ---------------------------------------------------------------------------
# L^q landscape distance
# ---------------------------------------------------------------------------

def landscape_distance(
    dgm_a: Diagram,
    dgm_b: Diagram,
    q: float = 2.0,
    num_landscapes: int = 5,
    resolution: int = 100,
) -> float:
    """Compute the L^q distance between the persistence landscapes of two diagrams.

    d_q(λ_a, λ_b) = (Σ_k ‖λ_a_k - λ_b_k‖_{L^q})^{1/q}
    discretised as the L^q norm on flattened landscape arrays.

    Parameters
    ----------
    dgm_a, dgm_b:
        Persistence diagrams (infinite bars stripped internally).
    q:
        Exponent for the L^q norm (q=2 is standard).
    num_landscapes:
        Number of landscape functions to compare.
    resolution:
        Discretisation resolution.

    Returns
    -------
    dist : float ≥ 0
    """
    la = persistence_landscape(dgm_a, num_landscapes=num_landscapes, resolution=resolution)
    lb = persistence_landscape(dgm_b, num_landscapes=num_landscapes, resolution=resolution)
    diff = np.abs(la - lb)
    if q == np.inf:
        return float(diff.max())
    return float(np.sum(diff ** q) ** (1.0 / q))


# ---------------------------------------------------------------------------
# N×N distance matrices
# ---------------------------------------------------------------------------

def bottleneck_distance_matrix(diagrams: Sequence[Diagram]) -> np.ndarray:
    """Compute the N×N bottleneck distance matrix for a collection of diagrams.

    Parameters
    ----------
    diagrams:
        Length-N sequence of persistence diagrams (each shape (n_i, 2)).

    Returns
    -------
    D : np.ndarray, shape (N, N), dtype float64, symmetric, zero diagonal.
    """
    N = len(diagrams)
    D = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(i + 1, N):
            d = bottleneck_distance(diagrams[i], diagrams[j])
            D[i, j] = d
            D[j, i] = d
    return D


def wasserstein_distance_matrix(
    diagrams: Sequence[Diagram], order: float = 1.0
) -> np.ndarray:
    """Compute the N×N Wasserstein distance matrix for a collection of diagrams.

    Parameters
    ----------
    diagrams:
        Length-N sequence of persistence diagrams.
    order:
        Wasserstein order p.

    Returns
    -------
    D : np.ndarray, shape (N, N), dtype float64, symmetric, zero diagonal.
    """
    N = len(diagrams)
    D = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(i + 1, N):
            d = wasserstein_distance(diagrams[i], diagrams[j], order=order)
            D[i, j] = d
            D[j, i] = d
    return D


def landscape_distance_matrix(
    diagrams: Sequence[Diagram],
    q: float = 2.0,
    num_landscapes: int = 5,
    resolution: int = 100,
) -> np.ndarray:
    """Compute the N×N L^q landscape distance matrix.

    Parameters
    ----------
    diagrams:
        Length-N sequence of persistence diagrams.
    q:
        L^q exponent.
    num_landscapes:
        Number of landscape functions.
    resolution:
        Discretisation resolution.

    Returns
    -------
    D : np.ndarray, shape (N, N), dtype float64, symmetric, zero diagonal.
    """
    N = len(diagrams)
    landscapes = [
        persistence_landscape(d, num_landscapes=num_landscapes, resolution=resolution)
        for d in diagrams
    ]
    D = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(i + 1, N):
            diff = np.abs(landscapes[i] - landscapes[j])
            d = float(np.sum(diff ** q) ** (1.0 / q)) if q < np.inf else float(diff.max())
            D[i, j] = d
            D[j, i] = d
    return D


# ---------------------------------------------------------------------------
# Persistence to disk
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Sliced Wasserstein distance (Carrière et al., 2017)
# ---------------------------------------------------------------------------

def sliced_wasserstein_distance(
    dgm_a: Diagram,
    dgm_b: Diagram,
    n_directions: int = 50,
    seed: int = 0,
) -> float:
    """Approximate Wasserstein distance via random slicing (Carrière et al., 2017).

    Projects both diagrams onto n_directions random lines and averages the
    1-Wasserstein distance between sorted projections. Runs in O(n log n)
    per direction vs O(n³) for the exact transport problem.

    Parameters
    ----------
    dgm_a, dgm_b : np.ndarray, shape (n, 2)
    n_directions : int
    seed : int

    Returns
    -------
    dist : float ≥ 0
    """
    rng = np.random.default_rng(seed)
    a = filter_infinite(np.asarray(dgm_a, dtype=np.float64)) if dgm_a.size > 0 else np.empty((0, 2))
    b = filter_infinite(np.asarray(dgm_b, dtype=np.float64)) if dgm_b.size > 0 else np.empty((0, 2))

    def _with_diag(dgm):
        if dgm.size == 0:
            return dgm
        mid = (dgm[:, 0] + dgm[:, 1]) / 2
        return np.vstack([dgm, np.column_stack([mid, mid])])

    a_ext, b_ext = _with_diag(a), _with_diag(b)
    if a_ext.size == 0 and b_ext.size == 0:
        return 0.0
    if a_ext.size == 0:
        mid = (b_ext[:, 0] + b_ext[:, 1]) / 2
        a_ext = np.column_stack([mid, mid])
    if b_ext.size == 0:
        mid = (a_ext[:, 0] + a_ext[:, 1]) / 2
        b_ext = np.column_stack([mid, mid])

    na, nb = len(a_ext), len(b_ext)
    if na < nb:
        mid = (a_ext[:, 0] + a_ext[:, 1]) / 2
        a_ext = np.vstack([a_ext, np.column_stack([mid, mid])[:nb - na]])
    elif nb < na:
        mid = (b_ext[:, 0] + b_ext[:, 1]) / 2
        b_ext = np.vstack([b_ext, np.column_stack([mid, mid])[:na - nb]])

    total = 0.0
    for _ in range(n_directions):
        theta = rng.uniform(0, np.pi)
        d = np.array([np.cos(theta), np.sin(theta)])
        total += np.mean(np.abs(np.sort(a_ext @ d) - np.sort(b_ext @ d)))
    return float(total / n_directions)


def sliced_wasserstein_distance_matrix(
    diagrams: Sequence[Diagram],
    n_directions: int = 50,
    seed: int = 0,
) -> np.ndarray:
    """N×N sliced Wasserstein distance matrix."""
    N = len(diagrams)
    D = np.zeros((N, N), dtype=np.float64)
    for i in range(N):
        for j in range(i + 1, N):
            d = sliced_wasserstein_distance(diagrams[i], diagrams[j], n_directions, seed)
            D[i, j] = d
            D[j, i] = d
    return D


# ---------------------------------------------------------------------------
# Persistence image barycenter (approximate Fréchet mean)
# ---------------------------------------------------------------------------

def persistence_image_barycenter(
    diagrams: Sequence[Diagram],
    sigma: float = 1.0,
    pixel_size: float = 0.1,
) -> np.ndarray:
    """Approximate Fréchet mean of persistence diagrams via persistence images.

    Computes all images with a shared PersistenceImager (same coordinate
    system for all) and returns their mean. This is the L² Fréchet mean in
    image space — an approximation to the true Wasserstein–Fréchet mean
    (Turner et al., 2014). The result is the player's topological fingerprint
    across multiple moves or multiple games.

    Parameters
    ----------
    diagrams : sequence of np.ndarray
    sigma : float
    pixel_size : float

    Returns
    -------
    barycenter : np.ndarray, shape (H, W)
    """
    from candela.tda.persistence import persistence_images_cohort
    images = persistence_images_cohort(list(diagrams), sigma=sigma, pixel_size=pixel_size)
    return images.mean(axis=0)


def save_distance_matrix(D: np.ndarray, name: str, output_dir: Path = _OUTPUT_DIR) -> Path:
    """Save a distance matrix as a .npy file.

    Parameters
    ----------
    D:
        Distance matrix array.
    name:
        Base filename (without extension).
    output_dir:
        Directory to write to (created if absent).

    Returns
    -------
    path : Path to the saved file.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{name}.npy"
    np.save(path, D)
    return path

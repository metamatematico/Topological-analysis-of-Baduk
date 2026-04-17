"""
Fase 3 — Persistent homology and topological descriptors.

Definitions
-----------
Persistence diagram (dim k):
    Set of points (b_i, d_i) ∈ R² ∪ {∞} where b_i is the filtration value
    at which homology class i is born and d_i is the value at which it dies.
    Points on the diagonal (b=d) represent noise / numerical artifacts and
    are present in gudhi output; they are filtered out before descriptor
    computation.

Barcode:
    The same information as a persistence diagram displayed as a collection
    of intervals [b_i, d_i).

Persistence landscape (Bubenik, 2015):
    Sequence of functions λ_k : R → R, k=1,2,..., defined from the diagram.
    Implemented via persim.landscapes.PersistenceLandscaper.

Persistence image (Adams et al., 2017):
    Pixelated representation of the weighted persistence diagram in birth-
    persistence coordinates.  Implemented via persim.PersistenceImager.

Persistent entropy (Atienza et al., 2020):
    H = -Σ (ℓ_i / L) log(ℓ_i / L)
    where ℓ_i = d_i - b_i is the lifetime of bar i and L = Σ ℓ_i.
    Returns 0 if the diagram is empty.

Betti curve:
    β_k(ε) = number of bars [b,d) with b ≤ ε < d, sampled at given scales.
"""

from __future__ import annotations

import numpy as np
import gudhi
import gudhi.representations
from typing import Optional

try:
    from persim import PersistenceImager
    from persim.landscapes import PersistenceLandscaper
    _PERSIM_OK = True
except ImportError:
    _PERSIM_OK = False

# Diagram type: np.ndarray of shape (n, 2) with columns [birth, death]
Diagram = np.ndarray


# ---------------------------------------------------------------------------
# Compute persistence from a SimplexTree
# ---------------------------------------------------------------------------

def compute_persistence(
    st: gudhi.SimplexTree,
    min_persistence: float = 0.0,
) -> dict[int, Diagram]:
    """Compute persistent homology from a gudhi SimplexTree.

    Parameters
    ----------
    st:
        SimplexTree with filtration values set.
    min_persistence:
        Bars with lifetime < min_persistence are discarded (noise filter).

    Returns
    -------
    diagrams : dict[dim, np.ndarray]
        Keys are homological dimensions (0, 1, 2, …).
        Values are arrays of shape (n, 2) with columns [birth, death].
        Infinite death values (essential classes) are represented as np.inf.
        Points with birth == death are removed.
    """
    st.compute_persistence(min_persistence=min_persistence)
    raw = st.persistence()

    diagrams: dict[int, list] = {}
    for dim, (b, d) in raw:
        if b == d:
            continue  # diagonal point — artifact
        diagrams.setdefault(dim, []).append((b, d))

    result: dict[int, Diagram] = {}
    for dim, pairs in diagrams.items():
        arr = np.array(pairs, dtype=np.float64)
        # Replace +inf with np.inf for consistency
        arr[arr == float('inf')] = np.inf
        result[dim] = arr

    # Ensure all encountered dimensions have an entry (even if empty)
    for dim in list(result.keys()):
        pass  # already populated

    return result


def filter_infinite(diagram: Diagram) -> Diagram:
    """Remove bars with infinite death value from a diagram.

    Infinite bars correspond to essential homology classes (connected
    components / cycles that never die).  Many descriptors require finite
    diagrams.
    """
    if diagram.size == 0:
        return diagram
    finite_mask = np.isfinite(diagram[:, 1])
    return diagram[finite_mask]


# ---------------------------------------------------------------------------
# Betti numbers and Betti curve
# ---------------------------------------------------------------------------

def betti_numbers(diagrams: dict[int, Diagram], epsilon: float) -> dict[int, int]:
    """Compute Betti numbers β_k at a given filtration value ε.

    β_k(ε) = #{bars [b,d) in diagram_k : b ≤ ε and d > ε}

    Parameters
    ----------
    diagrams:
        Output of compute_persistence.
    epsilon:
        Filtration scale at which to evaluate Betti numbers.

    Returns
    -------
    betti : dict[dim, int]
    """
    betti: dict[int, int] = {}
    for dim, dgm in diagrams.items():
        if dgm.size == 0:
            betti[dim] = 0
            continue
        births = dgm[:, 0]
        deaths = dgm[:, 1]
        count = int(np.sum((births <= epsilon) & (deaths > epsilon)))
        betti[dim] = count
    return betti


def betti_curve(diagram: Diagram, scales: np.ndarray) -> np.ndarray:
    """Evaluate the Betti curve β(ε) for a single-dimension diagram.

    Parameters
    ----------
    diagram:
        Array of shape (n, 2), columns [birth, death].
    scales:
        1-D array of ε values at which to evaluate β.

    Returns
    -------
    curve : np.ndarray, shape (len(scales),), dtype int
    """
    if diagram.size == 0:
        return np.zeros(len(scales), dtype=int)
    births = diagram[:, 0]
    deaths = diagram[:, 1]
    curve = np.array(
        [int(np.sum((births <= e) & (deaths > e))) for e in scales],
        dtype=int,
    )
    return curve


# ---------------------------------------------------------------------------
# Persistent entropy
# ---------------------------------------------------------------------------

def persistent_entropy(diagram: Diagram) -> float:
    """Compute persistent entropy of a persistence diagram.

    H = -Σ (ℓ_i / L) log(ℓ_i / L)
    where ℓ_i = d_i - b_i, L = Σ ℓ_i.

    Infinite bars are excluded.  Returns 0.0 for empty or all-infinite diagrams.

    Parameters
    ----------
    diagram:
        Array of shape (n, 2), columns [birth, death].

    Returns
    -------
    entropy : float ≥ 0
    """
    dgm = filter_infinite(diagram)
    if dgm.size == 0:
        return 0.0
    lifetimes = dgm[:, 1] - dgm[:, 0]
    lifetimes = lifetimes[lifetimes > 0]
    if len(lifetimes) == 0:
        return 0.0
    L = lifetimes.sum()
    p = lifetimes / L
    return float(-np.sum(p * np.log(p)))


# ---------------------------------------------------------------------------
# Persistence landscape
# ---------------------------------------------------------------------------

def persistence_landscape(
    diagram: Diagram,
    num_landscapes: int = 5,
    resolution: int = 100,
    filtration_range: Optional[tuple[float, float]] = None,
) -> np.ndarray:
    """Compute persistence landscapes from a finite-bar persistence diagram.

    Uses persim.landscapes.PersistenceLandscaper.
    API: PersistenceLandscaper(hom_deg=0, num_steps=resolution)
         .fit_transform([dgm]) → np.ndarray of shape (num_landscapes, resolution)
    where num_landscapes is determined by the number of bars in the diagram.

    Parameters
    ----------
    diagram:
        Array of shape (n, 2), finite values only (infinite bars stripped).
    num_landscapes:
        Maximum number of landscape functions to return.
    resolution:
        Number of discretisation points per landscape function (num_steps).
    filtration_range:
        (t_min, t_max) interval passed as start/stop to PersistenceLandscaper.
        If None, the landscaper infers it from the diagram.

    Returns
    -------
    landscapes : np.ndarray, shape (num_landscapes, resolution)
        landscapes[k-1] is the k-th landscape function λ_k sampled at
        `resolution` equally-spaced points.  Rows padded with zeros if the
        diagram has fewer than num_landscapes bars.
    """
    if not _PERSIM_OK:
        raise ImportError("persim is required for persistence landscapes.")

    dgm = filter_infinite(diagram)
    if dgm.size == 0:
        return np.zeros((num_landscapes, resolution), dtype=np.float64)

    kwargs: dict = {"hom_deg": 0, "num_steps": resolution}
    if filtration_range is not None:
        kwargs["start"], kwargs["stop"] = filtration_range

    landscaper = PersistenceLandscaper(**kwargs)
    # fit_transform([dgm]) → shape (actual_num_landscapes, resolution)
    ls = landscaper.fit_transform([dgm])  # type: np.ndarray

    actual = ls.shape[0]
    if actual >= num_landscapes:
        return ls[:num_landscapes].astype(np.float64)
    # Pad with zero rows if fewer landscapes than requested
    pad = np.zeros((num_landscapes - actual, resolution), dtype=np.float64)
    return np.vstack([ls, pad]).astype(np.float64)


# ---------------------------------------------------------------------------
# Persistence image
# ---------------------------------------------------------------------------

def persistence_image(
    diagram: Diagram,
    sigma: float = 1.0,
    pixel_size: float = 0.1,
) -> np.ndarray:
    """Compute a persistence image from a finite-bar persistence diagram.

    The diagram is transformed to birth-persistence coordinates:
        (b, p) = (b, d - b)
    A Gaussian kernel of standard deviation `sigma` is placed at each point,
    weighted by persistence.  The image is pixelated with `pixel_size`-wide pixels.

    Parameters
    ----------
    diagram:
        Array of shape (n, 2), columns [birth, death].  Infinite bars stripped.
    sigma:
        Standard deviation of the Gaussian kernel.
    pixel_size:
        Side length of each pixel in filtration units.

    Returns
    -------
    image : np.ndarray, shape (H, W), dtype float64
        H, W depend on the birth-persistence range of the diagram and pixel_size.
    """
    if not _PERSIM_OK:
        raise ImportError("persim is required for persistence images.")

    dgm = filter_infinite(diagram)
    if dgm.size == 0:
        return np.zeros((1, 1), dtype=np.float64)

    pimgr = PersistenceImager(
        pixel_size=pixel_size,
        kernel_params={"sigma": sigma},
    )
    pimgr.fit([dgm])
    img = pimgr.transform([dgm])[0]
    return np.array(img, dtype=np.float64)


def persistence_images_cohort(
    diagrams: list[Diagram],
    sigma: float = 1.0,
    pixel_size: float = 0.1,
) -> np.ndarray:
    """Compute persistence images for a cohort, using a shared imager.

    Fitting the PersistenceImager on all diagrams simultaneously ensures
    all images have the same shape (birth_range and pers_range are fixed
    to the cohort's global range).

    Parameters
    ----------
    diagrams:
        List of persistence diagrams (finite bars only — see filter_infinite).
    sigma:
        Gaussian kernel standard deviation.
    pixel_size:
        Pixel side length in filtration units.

    Returns
    -------
    images : np.ndarray, shape (N, H, W), dtype float64
    """
    if not _PERSIM_OK:
        raise ImportError("persim is required for persistence images.")

    finite_dgms = [filter_infinite(d) for d in diagrams]
    non_empty = [d for d in finite_dgms if d.size > 0]

    if not non_empty:
        return np.zeros((len(diagrams), 1, 1), dtype=np.float64)

    pimgr = PersistenceImager(
        pixel_size=pixel_size,
        kernel_params={"sigma": sigma},
    )
    pimgr.fit(non_empty)  # sets shared birth_range and pers_range

    # Get reference shape from first non-empty transform
    ref_img = np.array(pimgr.transform([non_empty[0]])[0], dtype=np.float64)
    h, w = max(ref_img.shape[0], 1), max(ref_img.shape[1], 1)

    results = []
    for d in finite_dgms:
        if d.size == 0:
            results.append(np.zeros((h, w), dtype=np.float64))
        else:
            img = np.array(pimgr.transform([d])[0], dtype=np.float64)
            if img.shape[0] == 0 or img.shape[1] == 0:
                img = np.zeros((h, w), dtype=np.float64)
            results.append(img)

    return np.array(results, dtype=np.float64)

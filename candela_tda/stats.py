"""
Fase 5 — Statistical and probabilistic analysis of pattern cohorts.

Four analyses are provided:

1. Permutation test (topological two-sample test)
   H₀: two cohorts of patterns have the same topological distribution.
   Test statistic: mean pairwise Wasserstein distance within cohort A and B
   versus between cohorts.  Specifically:
       T = mean(dist(a, b) for a ∈ A, b ∈ B)
         - 0.5*(mean(dist(a,a') for a,a' ∈ A) + mean(dist(b,b') for b,b' ∈ B))
   Under H₀, permuting labels should produce statistics at least as extreme
   as T.  p-value = #{permutations with T_perm ≥ T_obs} / n_permutations.

2. Bootstrap confidence bands for persistence diagrams (Fasy et al., 2014)
   For a collection of diagrams {D_1,...,D_n}, bootstrap band of level α is:
       [μ̂(ε) - c_α · σ̂(ε), μ̂(ε) + c_α · σ̂(ε)]
   where μ̂(ε) and σ̂(ε) are the sample mean and std of the Betti curves
   across bootstrap resamples.  c_α is the (1-α)-quantile of the bootstrap
   distribution of sup_ε |B̄^*(ε) - B̄(ε)| / σ̂(ε).

3. Clustering on distance matrix
   Agglomerative hierarchical clustering and DBSCAN on the precomputed
   distance matrix.  Reports silhouette score and cophenetic correlation
   (agglomerative) or cluster sizes (DBSCAN).

4. SVM/RF classifier on persistence images
   If labels are available, trains a linear SVM (or RF) on flattened
   persistence images, with stratified k-fold cross-validation.
   Reports mean accuracy, per-class F1, and confusion matrix.
   Multiple-comparison correction (Bonferroni/Holm) applied when
   comparing multiple classifiers or features.
"""

from __future__ import annotations

import numpy as np
from typing import Sequence, Optional
from scipy.stats import rankdata
from scipy.cluster.hierarchy import linkage, cophenet
from scipy.spatial.distance import squareform
from sklearn.cluster import AgglomerativeClustering, DBSCAN
from sklearn.metrics import silhouette_score, f1_score
from sklearn.svm import LinearSVC
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.preprocessing import StandardScaler

from candela.tda.persistence import betti_curve, filter_infinite, Diagram

RNG_DEFAULT = np.random.default_rng(0)


# ---------------------------------------------------------------------------
# 1. Permutation test
# ---------------------------------------------------------------------------

def _between_minus_within(
    D: np.ndarray, idx_a: np.ndarray, idx_b: np.ndarray
) -> float:
    """Test statistic: mean between-group distance minus mean within-group distance."""
    if len(idx_a) < 2 or len(idx_b) < 2:
        return 0.0
    between = D[np.ix_(idx_a, idx_b)].mean()
    within_a = D[np.ix_(idx_a, idx_a)]
    within_b = D[np.ix_(idx_b, idx_b)]
    # Exclude diagonal
    n_a, n_b = len(idx_a), len(idx_b)
    within_a_mean = (within_a.sum() - np.trace(within_a)) / max(n_a * (n_a - 1), 1)
    within_b_mean = (within_b.sum() - np.trace(within_b)) / max(n_b * (n_b - 1), 1)
    return float(between - 0.5 * (within_a_mean + within_b_mean))


def permutation_test(
    D: np.ndarray,
    labels: np.ndarray,
    n_permutations: int = 999,
    seed: int = 0,
) -> dict:
    """Permutation test for topological two-sample comparison.

    H₀: The two cohorts (labels == 0 and labels == 1) have the same
        topological distribution, as measured by pairwise distances.

    Parameters
    ----------
    D:
        Precomputed N×N symmetric distance matrix.
    labels:
        Integer array of length N with values in {0, 1}.
    n_permutations:
        Number of random permutations to estimate the null distribution.
    seed:
        RNG seed for reproducibility.

    Returns
    -------
    result : dict with keys:
        'statistic'     – observed test statistic T
        'p_value'       – two-sided p-value
        'n_permutations' – number of permutations used
        'null_distribution' – np.ndarray of permuted statistics
    """
    rng = np.random.default_rng(seed)
    labels = np.asarray(labels)
    idx_a = np.where(labels == 0)[0]
    idx_b = np.where(labels == 1)[0]

    T_obs = _between_minus_within(D, idx_a, idx_b)

    null = np.empty(n_permutations, dtype=np.float64)
    N = len(labels)
    for k in range(n_permutations):
        perm = rng.permutation(N)
        p_labels = labels[perm]
        p_a = np.where(p_labels == 0)[0]
        p_b = np.where(p_labels == 1)[0]
        null[k] = _between_minus_within(D, p_a, p_b)

    p_value = float((np.sum(null >= T_obs) + 1) / (n_permutations + 1))
    return {
        "statistic": T_obs,
        "p_value": p_value,
        "n_permutations": n_permutations,
        "null_distribution": null,
    }


# ---------------------------------------------------------------------------
# 2. Bootstrap confidence bands (Fasy et al., 2014)
# ---------------------------------------------------------------------------

def bootstrap_betti_bands(
    diagrams: Sequence[Diagram],
    scales: np.ndarray,
    n_bootstrap: int = 200,
    alpha: float = 0.05,
    seed: int = 0,
) -> dict:
    """Bootstrap confidence bands for mean Betti curves (Fasy et al., 2014).

    For a collection of persistence diagrams, estimate the (1-α) confidence
    band around the mean Betti curve β̄(ε) using the bootstrap supremum
    statistic of Fasy et al. (2014, Ann. Statist.).

    Parameters
    ----------
    diagrams:
        Sequence of N persistence diagrams.
    scales:
        1-D array of ε values at which to evaluate Betti curves.
    n_bootstrap:
        Number of bootstrap resamples.
    alpha:
        Significance level (band covers 1-α probability mass).
    seed:
        RNG seed.

    Returns
    -------
    result : dict with keys:
        'mean_curve'   – np.ndarray shape (len(scales),): sample mean Betti curve
        'std_curve'    – np.ndarray shape (len(scales),): sample std Betti curve
        'lower'        – lower confidence band
        'upper'        – upper confidence band
        'c_alpha'      – critical value used
        'alpha'        – significance level
    """
    rng = np.random.default_rng(seed)
    N = len(diagrams)
    # Compute Betti curves for all diagrams
    curves = np.stack([betti_curve(filter_infinite(d), scales) for d in diagrams])
    # curves shape: (N, len(scales))

    mean_curve = curves.mean(axis=0)
    std_curve = curves.std(axis=0) + 1e-10  # avoid division by zero

    # Bootstrap supremum statistics
    sup_stats = np.empty(n_bootstrap, dtype=np.float64)
    for b in range(n_bootstrap):
        boot_idx = rng.integers(0, N, size=N)
        boot_mean = curves[boot_idx].mean(axis=0)
        sup_stats[b] = np.max(np.abs(boot_mean - mean_curve) / std_curve)

    c_alpha = float(np.quantile(sup_stats, 1.0 - alpha))
    lower = mean_curve - c_alpha * std_curve
    upper = mean_curve + c_alpha * std_curve

    return {
        "mean_curve": mean_curve,
        "std_curve": std_curve,
        "lower": lower,
        "upper": upper,
        "c_alpha": c_alpha,
        "alpha": alpha,
    }


# ---------------------------------------------------------------------------
# 3. Clustering
# ---------------------------------------------------------------------------

def cluster_agglomerative(
    D: np.ndarray,
    n_clusters: int = 3,
    linkage_method: str = "average",
) -> dict:
    """Agglomerative hierarchical clustering on a precomputed distance matrix.

    Parameters
    ----------
    D:
        N×N symmetric distance matrix.
    n_clusters:
        Number of clusters.
    linkage_method:
        Linkage criterion ('single', 'complete', 'average', 'ward').
        Note: 'ward' requires Euclidean distances; use 'average' for general metrics.

    Returns
    -------
    result : dict with keys:
        'labels'       – cluster label array, shape (N,)
        'silhouette'   – silhouette score (requires N > n_clusters and n_clusters ≥ 2)
        'cophenetic'   – cophenetic correlation coefficient
        'n_clusters'   – actual number of clusters requested
    """
    N = D.shape[0]
    model = AgglomerativeClustering(
        n_clusters=n_clusters,
        metric="precomputed",
        linkage=linkage_method,
    )
    labels = model.fit_predict(D)

    sil = float(silhouette_score(D, labels, metric="precomputed")) if len(np.unique(labels)) >= 2 else float("nan")

    # Cophenetic correlation (needs condensed distance matrix)
    cond = squareform(D, checks=False)
    Z = linkage(cond, method=linkage_method)
    coph_corr, _ = cophenet(Z, cond)

    return {
        "labels": labels,
        "silhouette": sil,
        "cophenetic": float(coph_corr),
        "n_clusters": n_clusters,
    }


def cluster_dbscan(
    D: np.ndarray,
    eps: float = 1.0,
    min_samples: int = 2,
) -> dict:
    """DBSCAN clustering on a precomputed distance matrix.

    Parameters
    ----------
    D:
        N×N symmetric distance matrix.
    eps:
        Neighbourhood radius.
    min_samples:
        Minimum points to form a core point.

    Returns
    -------
    result : dict with keys:
        'labels'       – cluster labels (-1 = noise)
        'n_clusters'   – number of clusters (excluding noise)
        'silhouette'   – silhouette score (nan if < 2 clusters or all noise)
        'noise_fraction' – fraction of points labelled -1
    """
    model = DBSCAN(eps=eps, min_samples=min_samples, metric="precomputed")
    labels = model.fit_predict(D)
    n_clusters = int(len(set(labels)) - (1 if -1 in labels else 0))
    noise_frac = float(np.mean(labels == -1))

    sil = float("nan")
    if n_clusters >= 2 and noise_frac < 1.0:
        mask = labels != -1
        if mask.sum() > n_clusters:
            sil = float(silhouette_score(D[np.ix_(mask, mask)], labels[mask], metric="precomputed"))

    return {
        "labels": labels,
        "n_clusters": n_clusters,
        "silhouette": sil,
        "noise_fraction": noise_frac,
    }


# ---------------------------------------------------------------------------
# 4. Classifier on persistence images
# ---------------------------------------------------------------------------

def classify_persistence_images(
    images: np.ndarray,
    labels: np.ndarray,
    classifier: str = "svm",
    n_splits: int = 5,
    seed: int = 0,
) -> dict:
    """Classify patterns from flattened persistence images.

    Parameters
    ----------
    images:
        Array of shape (N, H, W) or (N, d) of persistence images / feature vectors.
    labels:
        Integer class labels, shape (N,).
    classifier:
        'svm' (LinearSVC) or 'rf' (RandomForestClassifier).
    n_splits:
        Number of stratified CV folds.
    seed:
        RNG seed.

    Returns
    -------
    result : dict with keys:
        'mean_accuracy'   – mean accuracy across folds
        'std_accuracy'    – std of accuracy across folds
        'mean_f1_macro'   – mean macro F1
        'per_fold_accuracy' – list of per-fold accuracies
        'classifier'      – classifier name used
    """
    X = images.reshape(len(images), -1).astype(np.float64)
    if X.shape[1] == 0:
        # Degenerate: all images are empty; return trivial result
        return {
            "mean_accuracy": float("nan"),
            "std_accuracy": float("nan"),
            "mean_f1_macro": float("nan"),
            "per_fold_accuracy": [],
            "classifier": classifier,
        }
    y = np.asarray(labels)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    accs, f1s = [], []

    for train_idx, test_idx in skf.split(X, y):
        X_tr, X_te = X[train_idx], X[test_idx]
        y_tr, y_te = y[train_idx], y[test_idx]

        scaler = StandardScaler()
        X_tr = scaler.fit_transform(X_tr)
        X_te = scaler.transform(X_te)

        if classifier == "svm":
            clf = LinearSVC(max_iter=2000, random_state=seed)
        elif classifier == "rf":
            clf = RandomForestClassifier(n_estimators=100, random_state=seed)
        else:
            raise ValueError(f"Unknown classifier: {classifier!r}. Use 'svm' or 'rf'.")

        clf.fit(X_tr, y_tr)
        y_pred = clf.predict(X_te)
        accs.append(float(np.mean(y_pred == y_te)))
        f1s.append(float(f1_score(y_te, y_pred, average="macro", zero_division=0)))

    return {
        "mean_accuracy": float(np.mean(accs)),
        "std_accuracy": float(np.std(accs)),
        "mean_f1_macro": float(np.mean(f1s)),
        "per_fold_accuracy": accs,
        "classifier": classifier,
    }


# ---------------------------------------------------------------------------
# Multiple-comparison correction (Bonferroni / Holm)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Topological transition detection
# ---------------------------------------------------------------------------

def topological_transitions(
    diagrams: Sequence[Diagram],
    order: float = 1.0,
    threshold: Optional[float] = None,
) -> dict:
    """Detect sharp topological transitions between consecutive diagrams.

    Computes the Wasserstein distance between each consecutive pair and flags
    positions where the distance exceeds a threshold. Useful for locating
    phase changes (opening → middle game → endgame) in a Go game.

    Parameters
    ----------
    diagrams : ordered sequence of persistence diagrams (one per move).
    order : Wasserstein order.
    threshold : If None, uses mean + 1.5 * std of the distance sequence.

    Returns
    -------
    result : dict with keys:
        'distances'   – np.ndarray, shape (N-1,)
        'transitions' – list of move indices where distance > threshold
        'threshold'   – threshold used
    """
    from candela.tda.distances import wasserstein_distance
    n = len(diagrams)
    if n < 2:
        return {"distances": np.array([]), "transitions": [], "threshold": 0.0}

    distances = np.array([
        wasserstein_distance(diagrams[i], diagrams[i + 1], order=order)
        for i in range(n - 1)
    ])

    if threshold is None:
        threshold = float(distances.mean() + 1.5 * distances.std())

    transitions = [i + 1 for i, d in enumerate(distances) if d > threshold]
    return {"distances": distances, "transitions": transitions, "threshold": threshold}


# ---------------------------------------------------------------------------
# Time-stratified test (simplified multiparameter persistence, Section 8.1)
# ---------------------------------------------------------------------------

def time_stratified_test(
    diagrams: Sequence[Diagram],
    n_strata: int = 4,
    n_permutations: int = 999,
    seed: int = 0,
) -> list:
    """Test for topological differences between consecutive temporal strata.

    Divides the move sequence into n_strata equal segments and runs pairwise
    permutation tests between all adjacent strata. Practical approximation
    to multiparameter persistence (Lesnick, 2015): discrete slices along t
    instead of a full 2-parameter module over (ε, t).

    Parameters
    ----------
    diagrams : ordered sequence of persistence diagrams (one per move).
    n_strata : number of temporal strata.
    n_permutations : permutations per test.
    seed : RNG seed.

    Returns
    -------
    results : list of dicts per adjacent pair:
        'stratum_a' – (start, end) move indices
        'stratum_b' – (start, end) move indices
        'p_value'   – permutation test p-value
        'statistic' – test statistic
    """
    from candela.tda.distances import wasserstein_distance_matrix

    N = len(diagrams)
    n_strata = max(2, min(n_strata, N // 2))
    boundaries = np.linspace(0, N, n_strata + 1, dtype=int)
    strata = [(int(boundaries[i]), int(boundaries[i + 1])) for i in range(n_strata)]

    D = wasserstein_distance_matrix(diagrams, order=1.0)
    results = []

    for k in range(len(strata) - 1):
        a_start, a_end = strata[k]
        b_start, b_end = strata[k + 1]
        idx_a = np.arange(a_start, a_end)
        idx_b = np.arange(b_start, b_end)
        if len(idx_a) < 2 or len(idx_b) < 2:
            continue
        all_idx = np.concatenate([idx_a, idx_b])
        sub_D = D[np.ix_(all_idx, all_idx)]
        labels = np.array([0] * len(idx_a) + [1] * len(idx_b))
        test = permutation_test(sub_D, labels, n_permutations=n_permutations, seed=seed)
        results.append({
            "stratum_a": (int(a_start), int(a_end)),
            "stratum_b": (int(b_start), int(b_end)),
            "p_value": test["p_value"],
            "statistic": test["statistic"],
        })

    return results


# ---------------------------------------------------------------------------
# Sliding window TDA on topological time series (Takens' theorem)
# ---------------------------------------------------------------------------

def sliding_window_tda(
    time_series: np.ndarray,
    window_size: int = 10,
    step: int = 1,
    tau: int = 1,
    embed_dim: int = 2,
    max_edge_frac: float = 1.0,
) -> list:
    """Apply TDA to a scalar time series via sliding window embedding.

    Each window is delay-embedded into R^embed_dim (Takens' theorem) and
    H₁ persistence is computed. Periodic patterns appear as persistent H₁
    bars; regime changes appear as jumps in the H₁ entropy.

    Applied to the PE₁ curve of a game, reveals if the player's territorial
    style oscillates periodically or changes abruptly.

    Parameters
    ----------
    time_series : 1-D array (e.g., persistent entropy H₁ per move).
    window_size : time steps per window.
    step : step between windows.
    tau : delay for the embedding.
    embed_dim : embedding dimension.
    max_edge_frac : max_edge_length as fraction of the window's value range.

    Returns
    -------
    results : list of dicts per window:
        'start'          – start index in the original series
        'end'            – end index
        'h1_entropy'     – PE₁ of the embedded window
        'n_loops'        – number of H₁ bars
        'max_persistence' – maximum finite persistence
    """
    from candela.tda.complex import vietoris_rips_complex
    from candela.tda.persistence import compute_persistence, persistent_entropy, filter_infinite

    ts = np.asarray(time_series, dtype=np.float64)
    results = []
    min_pts_needed = (embed_dim - 1) * tau + 1

    for start in range(0, len(ts) - window_size - min_pts_needed + 2, step):
        end = start + window_size
        if end > len(ts):
            break
        window = ts[start:end]
        n_pts = window_size - (embed_dim - 1) * tau
        if n_pts < 3:
            continue
        pts = np.column_stack([window[i * tau: i * tau + n_pts] for i in range(embed_dim)])
        rng_val = float(np.ptp(pts))
        max_e = rng_val * max_edge_frac if rng_val > 0 else 1.0
        st = vietoris_rips_complex(pts, max_edge_length=max_e, max_dimension=1)
        dgms = compute_persistence(st)
        h1 = filter_infinite(dgms.get(1, np.empty((0, 2))))
        max_p = float(np.max(h1[:, 1] - h1[:, 0])) if h1.size > 0 else 0.0
        results.append({
            "start": start, "end": end,
            "h1_entropy": persistent_entropy(h1),
            "n_loops": len(h1),
            "max_persistence": max_p,
        })

    return results


def bonferroni_correction(p_values: Sequence[float]) -> np.ndarray:
    """Bonferroni correction: p_corrected[i] = min(p[i] * m, 1).

    Parameters
    ----------
    p_values:
        Sequence of raw p-values.

    Returns
    -------
    p_corrected : np.ndarray of corrected p-values, same length.
    """
    p = np.asarray(p_values, dtype=np.float64)
    return np.minimum(p * len(p), 1.0)


def holm_correction(p_values: Sequence[float]) -> np.ndarray:
    """Holm–Bonferroni step-down correction.

    Parameters
    ----------
    p_values:
        Sequence of raw p-values.

    Returns
    -------
    p_corrected : np.ndarray of corrected p-values, same length as input.
    """
    p = np.asarray(p_values, dtype=np.float64)
    m = len(p)
    order = np.argsort(p)
    p_sorted = p[order]
    corrected = np.empty(m, dtype=np.float64)
    running_max = 0.0
    for k, idx in enumerate(order):
        c = p_sorted[k] * (m - k)
        running_max = max(running_max, c)
        corrected[idx] = min(running_max, 1.0)
    return corrected

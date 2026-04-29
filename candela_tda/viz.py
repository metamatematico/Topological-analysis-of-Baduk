"""
Simplicial complex and topological space visualizations.

draw_simplicial_complex(pts, epsilon, ax, **kwargs)
    Draw a Vietoris-Rips simplicial complex at scale epsilon on a matplotlib Axes.
    0-simplices: scatter dots
    1-simplices: line segments between points within epsilon
    2-simplices: filled triangles (all triplets within epsilon)

draw_topological_space(feature_vecs, labels, ax, **kwargs)
    MDS embedding of a sequence of feature vectors in R^2, colored by label
    (time index), with the trajectory drawn as a path.

draw_board_complex(board_stones, epsilon, ax, player_color, **kwargs)
    Draw the VR complex of one player's stones overlaid on a 19x19 Go board grid.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.collections import LineCollection, PolyCollection
from matplotlib.colors import Normalize
from mpl_toolkits.mplot3d import Axes3D          # noqa: F401 — registers 3d projection
from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection
from itertools import combinations
from typing import Sequence

from sklearn.manifold import MDS

# umap-learn is optional — imported lazily inside draw_umap_space
try:
    import umap as _umap_lib
    _HAS_UMAP = True
except ImportError:
    _HAS_UMAP = False


# ---------------------------------------------------------------------------
# Core: draw a VR simplicial complex on an axes
# ---------------------------------------------------------------------------

def draw_simplicial_complex(
    pts: np.ndarray,
    epsilon: float,
    ax: plt.Axes,
    node_color: str = "#2166ac",
    edge_color: str = "#4393c3",
    face_color: str = "#92c5de",
    node_size: float = 40.0,
    alpha_face: float = 0.35,
    alpha_edge: float = 0.75,
    linewidth: float = 1.2,
    title: str = "",
) -> None:
    """Draw VR simplicial complex at scale epsilon.

    Parameters
    ----------
    pts : np.ndarray, shape (n, 2)
        2D point cloud (e.g. stone positions in row-col coordinates).
    epsilon : float
        Filtration radius. Edges drawn between points at distance <= epsilon.
    ax : matplotlib Axes
    """
    if pts.shape[0] == 0:
        ax.set_title(title + "\n(sin piedras)")
        return

    n = pts.shape[0]

    # --- 2-simplices (triangles) ---
    triangles = []
    for i, j, k in combinations(range(n), 3):
        d_ij = np.sum(np.abs(pts[i] - pts[j]))
        d_ik = np.sum(np.abs(pts[i] - pts[k]))
        d_jk = np.sum(np.abs(pts[j] - pts[k]))
        if max(d_ij, d_ik, d_jk) <= epsilon:
            triangles.append([pts[i], pts[j], pts[k]])

    if triangles:
        poly = PolyCollection(
            triangles, facecolor=face_color, edgecolor="none", alpha=alpha_face, zorder=1
        )
        ax.add_collection(poly)

    # --- 1-simplices (edges) ---
    edges = []
    for i, j in combinations(range(n), 2):
        if np.sum(np.abs(pts[i] - pts[j])) <= epsilon:
            edges.append([pts[i], pts[j]])

    if edges:
        lc = LineCollection(
            edges, colors=edge_color, linewidths=linewidth, alpha=alpha_edge, zorder=2
        )
        ax.add_collection(lc)

    # --- 0-simplices (nodes) ---
    ax.scatter(pts[:, 1], pts[:, 0], s=node_size, c=node_color, zorder=3, linewidths=0.5, edgecolors="white")

    ax.set_title(title, fontsize=9)
    ax.set_aspect("equal")


# ---------------------------------------------------------------------------
# Board overlay: VR complex on a Go board grid
# ---------------------------------------------------------------------------

def draw_board_complex(
    stone_positions: list[tuple[int, int]],
    epsilon: float,
    ax: plt.Axes,
    player_label: str = "Negro",
    node_color: str = "#1a1a1a",
    edge_color: str = "#4393c3",
    face_color: str = "#92c5de",
    board_size: int = 19,
    title: str = "",
    move_number: int | None = None,
) -> None:
    """Draw the VR complex of one player's stones on a Go board grid.

    Parameters
    ----------
    stone_positions : list of (row, col) tuples, 0-indexed
    epsilon : filtration radius in board units
    """
    # Board grid background
    for i in range(board_size):
        ax.axhline(i, color="#c8a96e", lw=0.5, zorder=0)
        ax.axvline(i, color="#c8a96e", lw=0.5, zorder=0)
    ax.set_facecolor("#f0c870")

    # Star points (hoshi)
    hoshi = [(3,3),(3,9),(3,15),(9,3),(9,9),(9,15),(15,3),(15,9),(15,15)]
    for r, c in hoshi:
        ax.scatter(c, r, s=12, c="black", zorder=1, linewidths=0)

    ax.set_xlim(-0.5, board_size - 0.5)
    ax.set_ylim(-0.5, board_size - 0.5)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_aspect("equal")

    if not stone_positions:
        t = title or f"{player_label} — sin piedras"
        if move_number is not None:
            t += f"\nmov {move_number}"
        ax.set_title(t, fontsize=8)
        return

    pts = np.array(stone_positions, dtype=float)
    n = len(pts)

    # 2-simplices
    triangles = []
    for i, j, k in combinations(range(n), 3):
        dij = np.sum(np.abs(pts[i] - pts[j]))
        dik = np.sum(np.abs(pts[i] - pts[k]))
        djk = np.sum(np.abs(pts[j] - pts[k]))
        if max(dij, dik, djk) <= epsilon:
            tri = [[pts[i,1], pts[i,0]], [pts[j,1], pts[j,0]], [pts[k,1], pts[k,0]]]
            triangles.append(tri)
    if triangles:
        poly = PolyCollection(triangles, facecolor=face_color, edgecolor="none", alpha=0.35, zorder=2)
        ax.add_collection(poly)

    # 1-simplices
    edges = []
    for i, j in combinations(range(n), 2):
        if np.sum(np.abs(pts[i] - pts[j])) <= epsilon:
            edges.append([[pts[i,1], pts[i,0]], [pts[j,1], pts[j,0]]])
    if edges:
        lc = LineCollection(edges, colors=edge_color, linewidths=1.0, alpha=0.7, zorder=3)
        ax.add_collection(lc)

    # 0-simplices (stones)
    ax.scatter(pts[:, 1], pts[:, 0], s=55, c=node_color,
               zorder=4, linewidths=0.8, edgecolors="white" if node_color != "white" else "black")

    t = title or f"{player_label}  (n={n} piedras, ε={epsilon:.1f})"
    if move_number is not None:
        t += f"  |  mov {move_number}"
    ax.set_title(t, fontsize=8)


# ---------------------------------------------------------------------------
# Topological space: MDS trajectory
# ---------------------------------------------------------------------------

def draw_topological_space(
    feature_vecs: np.ndarray,
    ax: plt.Axes,
    player_label: str = "Jugador",
    cmap: str = "plasma",
    title: str = "",
    show_trajectory: bool = True,
    seed: int = 0,
) -> np.ndarray:
    """Embed feature vectors in 2D via MDS and draw the temporal trajectory.

    Each point is a move of one player, colored from early (dark) to late (bright).
    A path connects consecutive moves to show how the player's topological
    position evolves during the game.

    Parameters
    ----------
    feature_vecs : np.ndarray, shape (n_moves, d)
    ax : matplotlib Axes

    Returns
    -------
    embedding : np.ndarray, shape (n_moves, 2)
    """
    n = len(feature_vecs)
    if n < 3:
        ax.set_title(title or f"{player_label}\n(insuf. datos)")
        return np.zeros((n, 2))

    mds = MDS(n_components=2, dissimilarity="euclidean", random_state=seed, normalized_stress="auto")
    emb = mds.fit_transform(feature_vecs)

    colors = plt.cm.get_cmap(cmap)(np.linspace(0.1, 0.95, n))

    # Trajectory path
    if show_trajectory:
        for i in range(n - 1):
            ax.plot(
                [emb[i, 0], emb[i+1, 0]],
                [emb[i, 1], emb[i+1, 1]],
                color=colors[i], lw=0.8, alpha=0.5, zorder=1,
            )

    # Points
    sc = ax.scatter(emb[:, 0], emb[:, 1], c=np.arange(n), cmap=cmap,
                    s=35, zorder=2, linewidths=0.5, edgecolors="white",
                    vmin=0, vmax=n-1)

    # Start / end markers
    ax.scatter(*emb[0], s=120, c="green", marker="*", zorder=5, label="Inicio")
    ax.scatter(*emb[-1], s=120, c="red",   marker="X", zorder=5, label="Final")

    ax.set_title(title or f"Espacio topologico — {player_label}\n(MDS sobre {n} movimientos)", fontsize=9)
    ax.set_xlabel("MDS dim 1"); ax.set_ylabel("MDS dim 2")
    ax.legend(fontsize=7, loc="upper right")
    return emb


# ---------------------------------------------------------------------------
# UMAP: topological space via manifold learning
# ---------------------------------------------------------------------------

def draw_umap_space(
    feature_vecs: np.ndarray,
    ax: plt.Axes,
    player_label: str = "Jugador",
    cmap: str = "plasma",
    title: str = "",
    show_trajectory: bool = True,
    n_neighbors: int = 15,
    min_dist: float = 0.1,
    seed: int = 0,
    color_by: np.ndarray | None = None,
    metric: str = "euclidean",
    colorbar_label: str = "Movimiento",
    show_endpoints: bool = True,
) -> np.ndarray:
    """UMAP embedding of feature vectors drawn as a temporal trajectory.

    Behaves like draw_topological_space but uses UMAP instead of MDS.
    UMAP preserves both local clusters and global manifold structure,
    revealing non-linear patterns that MDS (a linear method) flattens.

    Parameters
    ----------
    feature_vecs : np.ndarray, shape (n, d) or (n, n) if metric='precomputed'
    n_neighbors : int — controls local vs global balance (higher = more global)
    min_dist : float — minimum distance in embedding (lower = tighter clusters)
    color_by : optional array of length n overriding the default time-index colors
    metric : 'euclidean' (default) or 'precomputed' for distance matrices

    Returns
    -------
    embedding : np.ndarray, shape (n, 2)
    """
    if not _HAS_UMAP:
        ax.set_title(f"{player_label}\n(instala umap-learn para UMAP)", fontsize=9)
        ax.text(0.5, 0.5, "pip install umap-learn", transform=ax.transAxes,
                ha="center", va="center", fontsize=9, color="gray")
        return np.zeros((len(feature_vecs), 2))

    n = len(feature_vecs)
    if n < 4:
        ax.set_title(title or f"{player_label}\n(insuf. datos para UMAP)", fontsize=9)
        return np.zeros((n, 2))

    nn = min(n_neighbors, n - 1)
    reducer = _umap_lib.UMAP(
        n_components=2, n_neighbors=nn, min_dist=min_dist,
        metric=metric, random_state=seed, low_memory=False,
    )
    emb = reducer.fit_transform(feature_vecs)

    c = color_by if color_by is not None else np.arange(n, dtype=float)

    if show_trajectory:
        cmap_obj = plt.cm.get_cmap(cmap)
        for i in range(n - 1):
            frac = i / max(n - 1, 1)
            col = cmap_obj(0.1 + 0.85 * frac)
            ax.plot([emb[i, 0], emb[i+1, 0]], [emb[i, 1], emb[i+1, 1]],
                    color=col, lw=0.7, alpha=0.45, zorder=1)

    sc = ax.scatter(emb[:, 0], emb[:, 1], c=c, cmap=cmap,
                    s=35, zorder=2, linewidths=0.5, edgecolors="white",
                    vmin=float(c.min()), vmax=float(c.max()))
    plt.colorbar(sc, ax=ax, label=colorbar_label, shrink=0.8)

    if show_endpoints and n >= 1:
        ax.scatter(*emb[0],  s=120, c="green", marker="*", zorder=5, label="Inicio")
        ax.scatter(*emb[-1], s=120, c="red",   marker="X", zorder=5, label="Final")
        ax.legend(fontsize=7, loc="upper right")

    ax.set_title(
        title or f"UMAP — {player_label}\n(n_neighbors={nn}, min_dist={min_dist})",
        fontsize=9,
    )
    ax.set_xlabel("UMAP 1"); ax.set_ylabel("UMAP 2")
    return emb


# ---------------------------------------------------------------------------
# Cohomology: draw H¹ representative cocycle on a Go board
# ---------------------------------------------------------------------------

def draw_cohomology_on_board(
    stone_positions: list[tuple[int, int]],
    cocycle_edges: np.ndarray | None,
    ax: plt.Axes,
    birth: float | None = None,
    death: float | None = None,
    player_label: str = "",
    node_color: str = "#1a1a1a",
    board_size: int = 19,
    title: str = "",
) -> None:
    """Draw the most persistent H¹ cohomology cocycle on a Go board.

    The cocycle is a set of edges (pairs of stones) that together form a
    representative 1-cocycle for the most persistent H¹ class. In Go terms,
    these are the connections between stones that define the boundary of a
    loop or enclosed territory.

    All stones are shown faintly. The stones and edges that belong to the
    cocycle are highlighted in red.

    Parameters
    ----------
    stone_positions : list of (row, col) tuples
    cocycle_edges : np.ndarray of shape (k, 3) with columns [i, j, coeff],
                   or None if no H¹ class was found.
    birth, death : float — filtration values of the H¹ bar (shown in title).
    """
    for i in range(board_size):
        ax.axhline(i, color="#c8a96e", lw=0.5, zorder=0)
        ax.axvline(i, color="#c8a96e", lw=0.5, zorder=0)
    ax.set_facecolor("#f0c870")

    hoshi = [(3,3),(3,9),(3,15),(9,3),(9,9),(9,15),(15,3),(15,9),(15,15)]
    for r, c in hoshi:
        ax.scatter(c, r, s=12, c="black", zorder=1, linewidths=0)

    ax.set_xlim(-0.5, board_size - 0.5)
    ax.set_ylim(-0.5, board_size - 0.5)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_aspect("equal")

    if not stone_positions:
        ax.set_title(title or f"{player_label}\n(sin piedras)", fontsize=8)
        return

    pts = np.array(stone_positions, dtype=float)
    n = len(pts)

    # All stones — faint background
    ax.scatter(pts[:, 1], pts[:, 0], s=40, c=node_color, alpha=0.25,
               zorder=3, linewidths=0.4,
               edgecolors="white" if node_color != "white" else "black")

    cycle_node_ids: set[int] = set()

    if cocycle_edges is not None and len(cocycle_edges) > 0:
        cycle_lines = []
        for row in cocycle_edges:
            i, j = int(row[0]), int(row[1])
            if i < n and j < n:
                cycle_lines.append([[pts[i, 1], pts[i, 0]], [pts[j, 1], pts[j, 0]]])
                cycle_node_ids.add(i)
                cycle_node_ids.add(j)

        if cycle_lines:
            lc = LineCollection(cycle_lines, colors="#e31a1c", linewidths=2.2,
                                alpha=0.9, zorder=4)
            ax.add_collection(lc)

        if cycle_node_ids:
            cp = pts[list(cycle_node_ids)]
            ax.scatter(cp[:, 1], cp[:, 0], s=70, c="#e31a1c", zorder=5,
                       linewidths=0.8, edgecolors="white")

    # Title
    if title:
        t = title
    elif cocycle_edges is None or len(cocycle_edges) == 0:
        t = f"{player_label}\n(sin H₁ significativo)"
    else:
        if birth is not None and death is not None and np.isfinite(death):
            t = (f"{player_label} — cociclo H₁\n"
                 f"birth={birth:.2f}  death={death:.2f}  "
                 f"persist={death-birth:.2f}")
        else:
            t = f"{player_label} — cociclo H₁ más persistente"
    ax.set_title(t, fontsize=8)


# ---------------------------------------------------------------------------
# Duality panel: homology diagram + cohomology cocycle + cup product
# ---------------------------------------------------------------------------

def draw_homology_cohomology_duality(
    h1_diagram: np.ndarray,
    stone_positions: list[tuple[int, int]],
    cocycle1: np.ndarray | None,
    cocycle2: np.ndarray | None,
    cup_triangles: list[tuple[int, int, int]],
    ax_diag: plt.Axes,
    ax_board: plt.Axes,
    player_label: str = "",
    node_color: str = "#1a1a1a",
    board_size: int = 19,
) -> None:
    """Show the homology-cohomology duality for H¹ classes.

    Left panel (ax_diag): persistence diagram of H₁ (the homology view).
      Each point (birth, death) represents a loop that appears at ε=birth
      and disappears at ε=death. Points far from the diagonal are significant.

    Right panel (ax_board): the two most persistent H¹ cocycles drawn on the
      board in red and blue. Triangles where their cup product is non-zero
      are filled in purple — these are the 2-simplices where the two loops
      interact, the algebraic signature of a two-eye group.

    Parameters
    ----------
    h1_diagram : np.ndarray, shape (n, 2) — H₁ persistence diagram (finite bars)
    stone_positions : list of (row, col)
    cocycle1, cocycle2 : cocycle edge arrays (k, 3) or None
    cup_triangles : list of (i, j, k) — 2-simplices with non-zero cup product
    """
    # ── Left: persistence diagram (homology view) ──────────────────────────────
    ax_diag.set_facecolor("#f8f8f8")
    if h1_diagram is not None and len(h1_diagram) > 0:
        dgm = h1_diagram[np.isfinite(h1_diagram[:, 1])]
        if len(dgm):
            max_val = dgm.max() * 1.1
            ax_diag.plot([0, max_val], [0, max_val], "k--", lw=0.8, alpha=0.4)
            persist = dgm[:, 1] - dgm[:, 0]
            sc = ax_diag.scatter(dgm[:, 0], dgm[:, 1],
                                 c=persist, cmap="Reds", s=60,
                                 zorder=3, edgecolors="gray", linewidths=0.5,
                                 vmin=0, vmax=persist.max() or 1)
            plt.colorbar(sc, ax=ax_diag, label="Persistencia", shrink=0.8)
    ax_diag.set_xlabel("Nacimiento ε (birth)")
    ax_diag.set_ylabel("Muerte ε (death)")
    ax_diag.set_title(f"{player_label}\nDiagrama H₁ (homología)", fontsize=8)

    # ── Right: cocycles + cup product on board (cohomology view) ───────────────
    for i in range(board_size):
        ax_board.axhline(i, color="#c8a96e", lw=0.5, zorder=0)
        ax_board.axvline(i, color="#c8a96e", lw=0.5, zorder=0)
    ax_board.set_facecolor("#f0c870")
    hoshi = [(3,3),(3,9),(3,15),(9,3),(9,9),(9,15),(15,3),(15,9),(15,15)]
    for r, c in hoshi:
        ax_board.scatter(c, r, s=12, c="black", zorder=1, linewidths=0)
    ax_board.set_xlim(-0.5, board_size - 0.5)
    ax_board.set_ylim(-0.5, board_size - 0.5)
    ax_board.set_xticks([]); ax_board.set_yticks([])
    ax_board.set_aspect("equal")

    if not stone_positions:
        ax_board.set_title(f"{player_label}\n(sin piedras)", fontsize=8)
        return

    pts = np.array(stone_positions, dtype=float)
    n = len(pts)

    # All stones — background
    ax_board.scatter(pts[:, 1], pts[:, 0], s=40, c=node_color, alpha=0.2,
                     zorder=2, linewidths=0.4,
                     edgecolors="white" if node_color != "white" else "black")

    colors_cocycle = ["#e31a1c", "#1f78b4"]  # red for cocycle1, blue for cocycle2
    for coc, col in zip([cocycle1, cocycle2], colors_cocycle):
        if coc is None or len(coc) == 0:
            continue
        lines, nodes = [], set()
        for row in coc:
            i, j = int(row[0]), int(row[1])
            if i < n and j < n:
                lines.append([[pts[i,1], pts[i,0]], [pts[j,1], pts[j,0]]])
                nodes.update([i, j])
        if lines:
            ax_board.add_collection(
                LineCollection(lines, colors=col, linewidths=1.8, alpha=0.8, zorder=3))
        if nodes:
            cp = pts[list(nodes)]
            ax_board.scatter(cp[:, 1], cp[:, 0], s=55, c=col, zorder=4,
                             linewidths=0.6, edgecolors="white")

    # Cup product triangles — purple fill (the H² interaction)
    if cup_triangles:
        tris = [[[pts[i,1], pts[i,0]], [pts[j,1], pts[j,0]], [pts[k,1], pts[k,0]]]
                for i, j, k in cup_triangles if max(i,j,k) < n]
        if tris:
            ax_board.add_collection(
                PolyCollection(tris, facecolor="#6a3d9a", edgecolor="none",
                               alpha=0.45, zorder=5))

    has_cup = len(cup_triangles) > 0
    cup_note = " | φ₁∪φ₂ ≠ 0 (dos ojos)" if has_cup else " | φ₁∪φ₂ = 0"
    ax_board.set_title(
        f"{player_label} — cociclos H₁ (cohomología)\n"
        f"Rojo=φ₁  Azul=φ₂  Púrpura=cup product{cup_note}",
        fontsize=7.5
    )


# ---------------------------------------------------------------------------
# Birth-colored VR complex: dimension = hue family, age = shade
# ---------------------------------------------------------------------------

def _simplex_births(
    stone_moments: list[list[tuple[int, int]]],
    epsilon: float,
) -> tuple[dict, dict, dict]:
    """Compute birth-moment index for every simplex across n game snapshots.

    Birth of a simplex = first snapshot at which ALL its constituent stones
    are present AND all pairwise Manhattan distances ≤ epsilon.

    Because stone sets are cumulative, the birth of an edge (i, j) equals
    max(birth_i, birth_j) — the moment the later stone was placed.
    Similarly for triangles: max(birth_i, birth_j, birth_k).

    Returns
    -------
    node_birth : {(r, c): moment_index}
    edge_birth : {frozenset({(r1,c1),(r2,c2)}): moment_index}
    face_birth : {frozenset({(r1,c1),(r2,c2),(r3,c3)}): moment_index}
    """
    node_birth: dict = {}
    for m_idx, stones in enumerate(stone_moments):
        for s in stones:
            key = (int(s[0]), int(s[1]))
            if key not in node_birth:
                node_birth[key] = m_idx

    # Enumerate simplices once using the final (largest) stone set
    final = [(int(s[0]), int(s[1])) for s in stone_moments[-1]]
    pts = np.array(final, dtype=float)
    n = len(pts)

    edge_birth: dict = {}
    face_birth: dict = {}

    for i, j in combinations(range(n), 2):
        if np.sum(np.abs(pts[i] - pts[j])) <= epsilon:
            ki = (int(pts[i, 0]), int(pts[i, 1]))
            kj = (int(pts[j, 0]), int(pts[j, 1]))
            edge_birth[frozenset([ki, kj])] = max(
                node_birth.get(ki, 0), node_birth.get(kj, 0)
            )

    for i, j, k in combinations(range(n), 3):
        dij = np.sum(np.abs(pts[i] - pts[j]))
        dik = np.sum(np.abs(pts[i] - pts[k]))
        djk = np.sum(np.abs(pts[j] - pts[k]))
        if max(dij, dik, djk) <= epsilon:
            ki = (int(pts[i, 0]), int(pts[i, 1]))
            kj = (int(pts[j, 0]), int(pts[j, 1]))
            kk = (int(pts[k, 0]), int(pts[k, 1]))
            face_birth[frozenset([ki, kj, kk])] = max(
                node_birth.get(ki, 0),
                node_birth.get(kj, 0),
                node_birth.get(kk, 0),
            )

    return node_birth, edge_birth, face_birth


def draw_board_complex_dim_colored(
    stone_moments: list[list[tuple[int, int]]],
    epsilon: float,
    axes,
    moment_labels: list[str],
    player_label: str = "",
    node_cmap: str = "Blues_r",
    edge_cmap: str = "Greens_r",
    face_cmap: str = "Oranges_r",
    board_size: int = 19,
) -> None:
    """Draw the VR complex at each game snapshot with persistence-colored simplices.

    Coloring scheme
    ---------------
    Dimension → hue family:
      - 0-simplices (nodes / stones) : Blues
      - 1-simplices (edges)          : Greens
      - 2-simplices (triangles)      : Oranges

    Age within each family (birth-moment index → shade):
      - Older  (low birth index) → darker / more saturated
      - Newer  (high birth index) → lighter

    A simplex retains its birth-color in all subsequent panels, so you can
    visually track which territory was established early and which appeared later.

    Parameters
    ----------
    stone_moments : list of n stone-position lists, one per snapshot
    epsilon       : Manhattan distance threshold for the VR complex
    axes          : sequence of n Axes (one per snapshot)
    moment_labels : n strings (e.g. ["20%", "40%", ...])
    """
    n_moments = len(stone_moments)
    if n_moments == 0:
        return

    node_birth, edge_birth, face_birth = _simplex_births(stone_moments, epsilon)

    # Colormaps: darker for older (lower birth index)
    # Blues_r goes dark→light as value 0→1, so birth_index/n_moments gives darker for older
    node_cm = plt.cm.get_cmap(node_cmap)
    edge_cm = plt.cm.get_cmap(edge_cmap)
    face_cm = plt.cm.get_cmap(face_cmap)

    # Map birth_index → [0.15, 0.85] so we avoid the extreme (white/invisible) ends
    def _shade(birth_idx: int) -> float:
        return 0.15 + 0.70 * (birth_idx / max(n_moments - 1, 1))

    for m_idx, (stones, ax, label) in enumerate(zip(stone_moments, axes, moment_labels)):
        # Board grid
        for i in range(board_size):
            ax.axhline(i, color="#c8a96e", lw=0.5, zorder=0)
            ax.axvline(i, color="#c8a96e", lw=0.5, zorder=0)
        ax.set_facecolor("#f0c870")
        hoshi = [(3,3),(3,9),(3,15),(9,3),(9,9),(9,15),(15,3),(15,9),(15,15)]
        for r, c in hoshi:
            ax.scatter(c, r, s=12, c="black", zorder=1, linewidths=0)
        ax.set_xlim(-0.5, board_size - 0.5)
        ax.set_ylim(-0.5, board_size - 0.5)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_aspect("equal")

        if not stones:
            ax.set_title(f"{label}\n(sin piedras)", fontsize=8)
            continue

        pts_cur = np.array([(int(s[0]), int(s[1])) for s in stones], dtype=float)
        n = len(pts_cur)

        # ── 2-simplices (triangles) ──────────────────────────────────────────
        tri_groups: dict[int, list] = {}   # birth_idx → list of triangle coords
        for i, j, k in combinations(range(n), 3):
            dij = np.sum(np.abs(pts_cur[i] - pts_cur[j]))
            dik = np.sum(np.abs(pts_cur[i] - pts_cur[k]))
            djk = np.sum(np.abs(pts_cur[j] - pts_cur[k]))
            if max(dij, dik, djk) <= epsilon:
                ki = (int(pts_cur[i, 0]), int(pts_cur[i, 1]))
                kj = (int(pts_cur[j, 0]), int(pts_cur[j, 1]))
                kk = (int(pts_cur[k, 0]), int(pts_cur[k, 1]))
                b = face_birth.get(frozenset([ki, kj, kk]), m_idx)
                tri_groups.setdefault(b, []).append([
                    [pts_cur[i,1], pts_cur[i,0]],
                    [pts_cur[j,1], pts_cur[j,0]],
                    [pts_cur[k,1], pts_cur[k,0]],
                ])

        for b_idx, tris in tri_groups.items():
            color = face_cm(_shade(b_idx))
            ax.add_collection(PolyCollection(
                tris, facecolor=color, edgecolor="none", alpha=0.40, zorder=2
            ))

        # ── 1-simplices (edges) ──────────────────────────────────────────────
        edge_groups: dict[int, list] = {}
        for i, j in combinations(range(n), 2):
            if np.sum(np.abs(pts_cur[i] - pts_cur[j])) <= epsilon:
                ki = (int(pts_cur[i, 0]), int(pts_cur[i, 1]))
                kj = (int(pts_cur[j, 0]), int(pts_cur[j, 1]))
                b = edge_birth.get(frozenset([ki, kj]), m_idx)
                edge_groups.setdefault(b, []).append([
                    [pts_cur[i,1], pts_cur[i,0]],
                    [pts_cur[j,1], pts_cur[j,0]],
                ])

        for b_idx, segs in edge_groups.items():
            color = edge_cm(_shade(b_idx))
            ax.add_collection(LineCollection(
                segs, colors=color, linewidths=1.1, alpha=0.80, zorder=3
            ))

        # ── 0-simplices (nodes) ──────────────────────────────────────────────
        for i in range(n):
            ki = (int(pts_cur[i, 0]), int(pts_cur[i, 1]))
            b = node_birth.get(ki, m_idx)
            color = node_cm(_shade(b))
            ax.scatter(pts_cur[i, 1], pts_cur[i, 0],
                       s=55, color=color, zorder=4,
                       linewidths=0.6, edgecolors="white")

        n_nodes = n
        n_edges = sum(len(v) for v in edge_groups.values())
        n_faces = sum(len(v) for v in tri_groups.values())
        ax.set_title(
            f"{player_label}  {label}\n"
            f"n={n_nodes} | aristas={n_edges} | Δ={n_faces}",
            fontsize=8,
        )

    # ── Legend: one patch per (dimension × age-extreme) ─────────────────────
    # Attach to the last axis
    last_ax = axes[-1] if hasattr(axes, '__len__') else axes
    legend_items = [
        mpatches.Patch(color=node_cm(0.15), label="Nodo (antiguo)"),
        mpatches.Patch(color=node_cm(0.85), label="Nodo (nuevo)"),
        mpatches.Patch(color=edge_cm(0.15), label="Arista (antigua)"),
        mpatches.Patch(color=edge_cm(0.85), label="Arista (nueva)"),
        mpatches.Patch(color=face_cm(0.15), label="Triángulo (antiguo)"),
        mpatches.Patch(color=face_cm(0.85), label="Triángulo (nuevo)"),
    ]
    last_ax.legend(handles=legend_items, fontsize=6, loc="upper right",
                   framealpha=0.85, title="Dim / Edad", title_fontsize=6)


# ---------------------------------------------------------------------------
# Single-frame renderer for video generation
# ---------------------------------------------------------------------------

# Per-dimension colormaps — translucent-friendly palette
_VIDEO_NODE_CMAP = plt.cm.get_cmap("plasma")     # purple → yellow  (nodes)
_VIDEO_EDGE_CMAP = plt.cm.get_cmap("cool")       # cyan → magenta   (edges, softer)
_VIDEO_FACE_CMAP = plt.cm.get_cmap("YlOrRd")     # yellow → orange → red (triangles, lighter)

# GPU via PyTorch if available (RTX 3050+)
try:
    import torch as _torch
    _CUDA = _torch.device("cuda") if _torch.cuda.is_available() else None
except ImportError:
    _CUDA = None


def _connected_components(n: int, edge_idx: np.ndarray) -> int:
    """Count connected components via path-compressed union-find. O(n α(n))."""
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for ei, ej in edge_idx:
        pi, pj = find(int(ei)), find(int(ej))
        if pi != pj:
            parent[pi] = pj
    return len({find(i) for i in range(n)})


def _find_simplices(pts: np.ndarray, epsilon: float):
    """Return edge_idx (M,2) and tri_idx (T,3) as numpy int arrays.

    The combinatorial problem — finding all pairs and triples within distance
    epsilon — is reduced to matrix operations:

      D[i,j]        = Manhattan distance matrix          O(n²) — 2D tensor
      A[i,j]        = D[i,j] <= epsilon                  boolean adjacency
      T[i,j,k]      = A[i,j] & A[i,k] & A[j,k]          O(n³) — 3D boolean tensor

    All three operations are elementwise and map directly to GPU kernels.
    For n=150 the tensors are 150²=22 KB and 150³=3.4 MB — trivial for VRAM.
    """
    if _CUDA is not None and len(pts) >= 10:
        p = _torch.tensor(pts, dtype=_torch.float32, device=_CUDA)
        # Manhattan distance matrix: |Δrow| + |Δcol|
        D = (p[:, None, :] - p[None, :, :]).abs().sum(-1)          # (n,n)
        A = D <= epsilon                                             # boolean (n,n)

        # Triangle tensor: T[i,j,k] = A[i,j] & A[i,k] & A[j,k]
        T = A[:, :, None] & A[:, None, :] & A[None, :, :]          # (n,n,n)

        ii, jj, kk = _torch.where(T)
        tri_mask = (ii < jj) & (jj < kk)
        tri_idx = _torch.stack([ii[tri_mask], jj[tri_mask], kk[tri_mask]], dim=1).cpu().numpy()

        ei, ej = _torch.where(_torch.triu(A, diagonal=1))
        edge_idx = _torch.stack([ei, ej], dim=1).cpu().numpy()
    else:
        # Vectorized numpy fallback (still much faster than Python loops)
        D = np.abs(pts[:, None, :] - pts[None, :, :]).sum(-1)
        A = D <= epsilon

        T = A[:, :, None] & A[:, None, :] & A[None, :, :]
        ii, jj, kk = np.where(T)
        tri_mask = (ii < jj) & (jj < kk)
        tri_idx = np.stack([ii[tri_mask], jj[tri_mask], kk[tri_mask]], axis=1) if tri_mask.any() else np.empty((0, 3), int)

        ei, ej = np.where(np.triu(A, k=1))
        edge_idx = np.stack([ei, ej], axis=1) if len(ei) > 0 else np.empty((0, 2), int)

    return edge_idx, tri_idx


def draw_board_frame(
    stones: list[tuple[int, int]],
    birth_dict: dict[tuple[int, int], int],
    current_move: int,
    epsilon: float,
    ax,
    last_move: tuple[int, int] | None = None,
    player_label: str = "",
    board_size: int = 19,
    node_cmap=None,
    edge_cmap=None,
    face_cmap=None,
) -> None:
    """Render one video frame: VR complex with per-dimension vivid coloring.

    Dimension → color family:
      - 0-simplices  (nodes)    : plasma   (purple/blue → yellow)
      - 1-simplices  (edges)    : spring   (cyan → magenta)
      - 2-simplices  (triangles): hot      (black → red → bright yellow)

    Birth time → shade within each family (newest = vivid, oldest = dark).
    Simplex computation delegated to _find_simplices() which uses GPU when
    available, reducing O(n³) Python loops to a single 3D tensor operation.
    Rendering uses one PolyCollection + one LineCollection (batch draw calls).
    """
    node_cm = node_cmap or _VIDEO_NODE_CMAP
    edge_cm = edge_cmap or _VIDEO_EDGE_CMAP
    face_cm = face_cmap or _VIDEO_FACE_CMAP

    # Board background
    ax.set_facecolor("#1a1108")
    for i in range(board_size):
        ax.axhline(i, color="#8B6914", lw=0.4, zorder=0, alpha=0.6)
        ax.axvline(i, color="#8B6914", lw=0.4, zorder=0, alpha=0.6)
    hoshi = [(3,3),(3,9),(3,15),(9,3),(9,9),(9,15),(15,3),(15,9),(15,15)]
    for r, c in hoshi:
        ax.scatter(c, r, s=18, c="#8B6914", zorder=1, linewidths=0)

    ax.set_xlim(-0.5, board_size - 0.5)
    ax.set_ylim(-0.5, board_size - 0.5)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_aspect("equal")

    if not stones:
        ax.set_title(f"{player_label}\n(sin piedras)", fontsize=9, color="white")
        return

    pts = np.array([(int(s[0]), int(s[1])) for s in stones], dtype=float)
    n = len(pts)
    denom = max(current_move, 1)

    # Per-stone birth array indexed by position in pts
    birth_arr = np.array(
        [birth_dict.get((int(pts[i, 0]), int(pts[i, 1])), current_move) for i in range(n)],
        dtype=float,
    )

    # ── Compute all simplices in one GPU/vectorized call ─────────────────────
    edge_idx, tri_idx = _find_simplices(pts, epsilon)

    # ── 2-simplices: single batched PolyCollection ───────────────────────────
    if len(tri_idx) > 0:
        ii, jj, kk = tri_idx[:, 0], tri_idx[:, 1], tri_idx[:, 2]
        b_tri = np.maximum(birth_arr[ii], np.maximum(birth_arr[jj], birth_arr[kk]))
        shades_t = 0.15 + 0.70 * (b_tri / denom)
        colors_t = face_cm(shades_t)                    # (T, 4) RGBA
        colors_t[:, 3] = 0.18                           # low alpha — don't bury edges/nodes
        verts = pts[tri_idx[:, :]][:, :, [1, 0]]       # (T, 3, 2) — x=col, y=row
        ax.add_collection(PolyCollection(
            verts, facecolors=colors_t, edgecolor="none", zorder=2
        ))

    # ── 1-simplices: single batched LineCollection ───────────────────────────
    if len(edge_idx) > 0:
        ei, ej = edge_idx[:, 0], edge_idx[:, 1]
        b_edge = np.maximum(birth_arr[ei], birth_arr[ej])
        shades_e = 0.10 + 0.80 * (b_edge / denom)
        colors_e = edge_cm(shades_e)                    # (M, 4) RGBA
        colors_e[:, 3] = 0.55                           # semi-transparent edges
        segs = np.stack([pts[ei][:, [1, 0]], pts[ej][:, [1, 0]]], axis=1)
        ax.add_collection(LineCollection(
            segs, colors=colors_e, linewidths=1.0, zorder=3
        ))

    # ── 0-simplices: single scatter call ─────────────────────────────────────
    shades_n = 0.05 + 0.87 * (birth_arr / denom)
    colors_n = node_cm(shades_n)                        # (n, 4) RGBA
    sizes = np.full(n, 45.0)
    ec = np.zeros((n, 4))

    if last_move is not None:
        for idx in range(n):
            if (int(pts[idx, 0]), int(pts[idx, 1])) == last_move:
                sizes[idx] = 85.0
                ec[idx] = [1, 1, 1, 1]
                break

    ax.scatter(pts[:, 1], pts[:, 0], c=colors_n, s=sizes,
               edgecolors=ec, linewidths=1.2, zorder=5)

    if last_move is not None:
        r_lm, c_lm = last_move
        ax.scatter(c_lm, r_lm, s=170, facecolor="none",
                   edgecolors="white", linewidths=2.0, zorder=6)

    # ── Contador topológico ──────────────────────────────────────────────────
    n_comp  = _connected_components(n, edge_idx) if len(edge_idx) > 0 else n
    n_edges = len(edge_idx)
    n_tris  = len(tri_idx)
    # Ciclo rank de la 1-cadena: aristas - vértices + componentes
    h1_rank = max(0, n_edges - n + n_comp)

    counter = (
        f"Grupos  H\u2080 : {n_comp}\n"
        f"Lazos   H\u2081 : {h1_rank}\n"
        f"Tri\u00e1ngulos : {n_tris}\n"
        f"Aristas    : {n_edges}\n"
        f"Piedras    : {n}"
    )
    ax.text(
        0.02, 0.98, counter,
        transform=ax.transAxes, fontsize=7, color="white",
        va="top", ha="left", family="monospace",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#000000", alpha=0.65),
        zorder=10,
    )

    ax.set_title(
        f"{player_label}   ε={epsilon}",
        fontsize=8, color="white", pad=4,
    )


# ---------------------------------------------------------------------------
# 3D: VR complex on a 3-component embedding (MDS or UMAP)
# ---------------------------------------------------------------------------

def draw_simplicial_complex_3d(
    pts: np.ndarray,
    epsilon: float,
    ax,
    node_color: str = "#2166ac",
    edge_color: str = "#4393c3",
    face_color: str = "#92c5de",
    node_size: float = 30.0,
    alpha_face: float = 0.08,
    alpha_edge: float = 0.50,
    linewidth: float = 0.7,
    title: str = "",
    show_faces: bool = False,
    color_by: np.ndarray | None = None,
    cmap: str = "plasma",
) -> None:
    """Draw a VR simplicial complex in 3D on an Axes3D instance.

    Uses Euclidean distance in the embedding space (not Manhattan, which is
    reserved for Go board coordinates). 2-simplices (triangles) are off by
    default — with many points they are expensive and visually cluttered in 3D.
    """
    if pts.shape[0] == 0:
        ax.set_title(title + "\n(sin puntos)")
        return

    n = pts.shape[0]

    # 2-simplices — skip when n is large (>200 triangles becomes slow)
    if show_faces:
        tris = []
        for i, j, k in combinations(range(n), 3):
            if (np.linalg.norm(pts[i] - pts[j]) <= epsilon and
                np.linalg.norm(pts[i] - pts[k]) <= epsilon and
                np.linalg.norm(pts[j] - pts[k]) <= epsilon):
                tris.append([pts[i], pts[j], pts[k]])
                if len(tris) > 600:      # safety cap
                    break
        if tris:
            poly3d = Poly3DCollection(tris, facecolor=face_color,
                                      edgecolor="none", alpha=alpha_face)
            ax.add_collection3d(poly3d)

    # 1-simplices
    edges = []
    for i, j in combinations(range(n), 2):
        if np.linalg.norm(pts[i] - pts[j]) <= epsilon:
            edges.append([pts[i], pts[j]])
    if edges:
        lc3d = Line3DCollection(edges, colors=edge_color,
                                linewidths=linewidth, alpha=alpha_edge)
        ax.add_collection3d(lc3d)

    # 0-simplices
    xs, ys, zs = pts[:, 0], pts[:, 1], pts[:, 2]
    if color_by is not None:
        sc = ax.scatter(xs, ys, zs, c=color_by, cmap=cmap,
                        s=node_size, linewidths=0.4, edgecolors="white",
                        vmin=color_by.min(), vmax=color_by.max(), depthshade=True)
    else:
        ax.scatter(xs, ys, zs, c=node_color, s=node_size,
                   linewidths=0.4, edgecolors="white", depthshade=True)

    ax.set_title(title, fontsize=9)
    ax.set_xlabel("dim 1", fontsize=7); ax.set_ylabel("dim 2", fontsize=7)
    ax.set_zlabel("dim 3", fontsize=7)
    ax.tick_params(labelsize=6)


# ---------------------------------------------------------------------------
# Multi-epsilon panel: how complex changes with epsilon
# ---------------------------------------------------------------------------

def draw_epsilon_progression(
    pts: np.ndarray,
    epsilons: Sequence[float],
    axes: Sequence[plt.Axes],
    node_color: str = "#1a1a1a",
    edge_color: str = "#4393c3",
    face_color: str = "#92c5de",
    player_label: str = "",
    board_mode: bool = True,
    board_size: int = 19,
) -> None:
    """Draw the same point cloud at multiple epsilon values side by side."""
    stone_positions = [(int(r), int(c)) for r, c in pts]
    for ax, eps in zip(axes, epsilons):
        if board_mode:
            draw_board_complex(
                stone_positions, eps, ax,
                player_label=player_label,
                node_color=node_color,
                edge_color=edge_color,
                face_color=face_color,
                title=f"{player_label}  ε={eps:.1f}",
            )
        else:
            draw_simplicial_complex(
                pts, eps, ax,
                node_color=node_color,
                edge_color=edge_color,
                face_color=face_color,
                title=f"{player_label}  ε={eps:.1f}",
            )

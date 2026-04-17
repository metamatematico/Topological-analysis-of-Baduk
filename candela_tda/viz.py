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
from itertools import combinations
from typing import Sequence

from sklearn.manifold import MDS


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

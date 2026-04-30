"""
Mapper algorithm — topological summary of a point cloud.

The Mapper algorithm (Singh, Mémoli & Carlsson, 2007) summarises a
high-dimensional dataset as a graph that captures its topological shape:

  - Loops  → recurring stylistic cycles in the pattern space
  - Branches → distinct strategy families
  - Flares   → isolated extreme positions

Applied to Candela feature vectors (361 dims), Mapper reveals clusters
of stylistically similar moves, connected when they share members.
Applied to persistence images, it reveals topological strategy types.

A node = cluster of similar moves.
An edge = the two clusters share at least one move (overlap in the cover).
Node size = cluster size (number of moves).
Node color = mean move time (early → dark, late → bright).
"""

from __future__ import annotations

import numpy as np
from typing import Optional

try:
    import kmapper as km
    from sklearn.cluster import DBSCAN as _DBSCAN
    from sklearn.decomposition import PCA as _PCA
    _KMAPPER_OK = True
except ImportError:
    _KMAPPER_OK = False


def compute_mapper(
    vectors: np.ndarray,
    lens: Optional[np.ndarray] = None,
    n_cubes: int = 10,
    overlap: float = 0.5,
    eps: float = 0.5,
    min_samples: int = 2,
) -> dict:
    """Apply the Mapper algorithm to a point cloud.

    Parameters
    ----------
    vectors : np.ndarray, shape (N, d)
        Feature vectors (e.g., 361-dim Candela patterns or flattened
        persistence images).
    lens : np.ndarray, shape (N, k), optional
        Lens (filter) function values. If None, uses PCA(2) on the vectors.
    n_cubes : int
        Number of cover intervals per lens dimension.
    overlap : float
        Fractional overlap between consecutive intervals (0 < overlap < 1).
    eps : float
        DBSCAN ε for clustering within each cover patch.
    min_samples : int
        DBSCAN min_samples.

    Returns
    -------
    dict with keys:
        'graph'  – KeplerMapper simplicial complex (nodes + links)
        'mapper' – KeplerMapper instance (for HTML export)
        'lens'   – lens values used, shape (N, k)
    """
    if not _KMAPPER_OK:
        raise ImportError(
            "kmapper is required: pip install kmapper"
        )

    mapper = km.KeplerMapper(verbose=0)

    if lens is None:
        pca = _PCA(n_components=min(2, vectors.shape[1]), random_state=0)
        lens = pca.fit_transform(vectors)

    graph = mapper.map(
        lens,
        vectors,
        clusterer=_DBSCAN(eps=eps, min_samples=min_samples),
        cover=km.Cover(n_cubes=n_cubes, perc_overlap=overlap),
    )

    return {"graph": graph, "mapper": mapper, "lens": lens}


def mapper_node_stats(
    graph: dict,
    vectors: np.ndarray,
    move_times: Optional[np.ndarray] = None,
) -> dict:
    """Compute per-node statistics for a Mapper graph.

    Parameters
    ----------
    graph : dict
        Output of compute_mapper['graph'].
    vectors : np.ndarray, shape (N, d)
        Original feature vectors.
    move_times : np.ndarray, shape (N,), optional
        Move index (0..N-1) for temporal analysis.

    Returns
    -------
    stats : dict[node_id → {'size', 'mean_vector', 'member_ids', 'mean_time'}]
    """
    stats = {}
    for node_id, member_ids in graph["nodes"].items():
        arr = np.array(member_ids)
        stats[node_id] = {
            "size": len(arr),
            "mean_vector": vectors[arr].mean(axis=0),
            "member_ids": arr,
            "mean_time": float(np.mean(move_times[arr])) if move_times is not None else float("nan"),
        }
    return stats


def draw_mapper_graph(
    graph: dict,
    node_stats: dict,
    ax,
    cmap: str = "plasma",
    title: str = "Mapper",
) -> None:
    """Draw a Mapper graph on a matplotlib axes.

    Nodes are drawn as circles sized by cluster size and colored by mean
    move time. Edges connect overlapping clusters. Uses a spring layout.

    Parameters
    ----------
    graph : dict
        Output of compute_mapper['graph'].
    node_stats : dict
        Output of mapper_node_stats.
    ax : matplotlib.axes.Axes
    cmap : str
        Colormap for node coloring (maps mean_time to color).
    title : str
    """
    try:
        import networkx as nx
    except ImportError:
        ax.text(0.5, 0.5, "networkx required for Mapper viz",
                ha="center", va="center", transform=ax.transAxes)
        return

    G = nx.Graph()
    for node_id in graph["nodes"]:
        G.add_node(node_id)
    for node_id, neighbors in graph["links"].items():
        for nb in neighbors:
            G.add_edge(node_id, nb)

    if G.number_of_nodes() == 0:
        ax.text(0.5, 0.5, "Mapper: sin nodos (ajustar eps/n_cubes)",
                ha="center", va="center", transform=ax.transAxes, fontsize=9)
        ax.axis("off")
        return

    pos = nx.spring_layout(G, seed=0)

    times = np.array([node_stats.get(n, {}).get("mean_time", 0.0) for n in G.nodes()])
    sizes = np.array([node_stats.get(n, {}).get("size", 1) for n in G.nodes()])
    t_min, t_max = times.min(), times.max()
    norm_times = (times - t_min) / max(t_max - t_min, 1e-6)

    cmap_obj = __import__("matplotlib.pyplot", fromlist=["cm"]).cm.get_cmap(cmap)
    colors = [cmap_obj(t) for t in norm_times]

    nx.draw_networkx_edges(G, pos, ax=ax, alpha=0.4, width=1.2, edge_color="#888888")
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_size=40 * np.clip(sizes, 1, 20),
        node_color=colors,
        alpha=0.85,
    )

    n_nodes = G.number_of_nodes()
    n_edges = G.number_of_edges()
    ax.set_title(
        f"{title}\n{n_nodes} nodos · {n_edges} aristas\n"
        f"(color = tiempo medio del movimiento)",
        fontsize=8,
    )
    ax.axis("off")

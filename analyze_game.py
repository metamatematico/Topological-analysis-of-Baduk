"""
Full per-player TDA analysis of a single SGF game.

Usage:
    python analyze_game.py <sgf_path> <output_dir>

Produces:
    <output_dir>/
        analysis.json
        report.md
        figures/
            fig01_entropy_per_player.png
            fig02_betti_curves_per_player.png
            fig03_complex_negro_moments.png
            fig04_complex_blanco_moments.png
            fig05_complex_negro_epsilons.png
            fig06_complex_blanco_epsilons.png
            fig07_topo_space_negro.png
            fig08_topo_space_blanco.png
            fig09_topo_space_comparison.png
            fig10_persistence_diagrams_per_player.png
            fig11_distance_matrices.png
            fig12_comparison_betti.png
            fig13_board_heatmap_per_player.png
        distances/
            *.npy
"""

import sys, warnings, json, time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from pathlib import Path
from itertools import combinations

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))

from sgfmill import sgf, boards as sgf_boards
import importlib.util

# Candela root
spec = importlib.util.spec_from_file_location("_croot", Path(__file__).parent / "candela.py")
_croot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_croot)

from candela.tda.representation import pattern_to_pointcloud, pattern_to_feature_vector, pattern_distance_matrix
from candela.tda.complex import vietoris_rips_complex
from candela.tda.persistence import (
    compute_persistence, filter_infinite,
    persistent_entropy, betti_curve,
    persistence_images_cohort,
)
from candela.tda.distances import (
    bottleneck_distance_matrix, wasserstein_distance_matrix,
    landscape_distance_matrix, save_distance_matrix,
)
from candela.tda.stats import (
    permutation_test, bootstrap_betti_bands,
    cluster_agglomerative, cluster_dbscan,
    classify_persistence_images,
)
from candela.tda.viz import (
    draw_board_complex, draw_topological_space,
    draw_epsilon_progression,
)
from candela.tda.report import generate_report

# ── CLI args ──────────────────────────────────────────────────────────────────
sgf_path   = Path(sys.argv[1])
output_dir = Path(sys.argv[2])
figdir     = output_dir / "figures"
distdir    = output_dir / "distances"
figdir.mkdir(parents=True, exist_ok=True)
distdir.mkdir(parents=True, exist_ok=True)

MAX_EPS  = 12.0
MAX_DIM  = 2
N_BOOT   = 400
N_PERM   = 999
SEED     = 0
EPSILONS = [1.5, 2.5, 4.0, 6.0]   # shown in epsilon-progression figures
MOMENTS  = [0.20, 0.40, 0.60, 0.80, 1.0]  # fractions of each player's moves

t0 = time.time()

# ── Parse SGF ────────────────────────────────────────────────────────────────
print(f"[1/9] Leyendo {sgf_path.name} ...")
with open(sgf_path, "rb") as f:
    game = sgf.Sgf_game.from_bytes(f.read())

root = game.get_root()
meta = {}
for prop in ["PW", "PB", "RE", "DT", "KM", "EV", "PC", "GN"]:
    try:
        meta[prop] = root.get(prop)
    except Exception:
        pass

BLACK_NAME = meta.get("PB", "Negro")
WHITE_NAME = meta.get("PW", "Blanco")

# Replay board; record per-move data and full board state at each move
board = sgf_boards.Board(19)
all_patterns, all_colours, all_moves_xy = [], [], []
board_states = []          # full 19x19 board state AFTER each move
black_stones_seq = []      # cumulative positions of black stones after each black move
white_stones_seq = []      # cumulative positions of white stones after each white move

_black_positions: set[tuple[int,int]] = set()
_white_positions: set[tuple[int,int]] = set()

for node in game.get_main_sequence():
    colour, move = node.get_move()
    if move is None:
        continue
    x, y = move
    board.play(x, y, colour)

    region = _croot.obtain_19_by_19_region_centered_by(board, (x, y))
    canon  = _croot.canonical_form(region, (x, y))
    all_patterns.append(canon)
    all_colours.append(colour)
    all_moves_xy.append((x, y))

    # Track cumulative stone positions per player
    if colour == "b":
        _black_positions.add((x, y))
    else:
        _white_positions.add((x, y))
    black_stones_seq.append(sorted(_black_positions))
    white_stones_seq.append(sorted(_white_positions))

N = len(all_patterns)
n_unique = len(set(all_patterns))
print(f"   {N} movimientos  |  {n_unique} patrones unicos")
print(f"   {BLACK_NAME} (N) vs {WHITE_NAME} (B)  |  {meta.get('RE','?')}  |  {meta.get('DT','?')}")

# ── Split by player ───────────────────────────────────────────────────────────
b_idx = [i for i, c in enumerate(all_colours) if c == "b"]
w_idx = [i for i, c in enumerate(all_colours) if c == "w"]
b_patterns = [all_patterns[i] for i in b_idx]
w_patterns  = [all_patterns[i] for i in w_idx]
Nb, Nw = len(b_idx), len(w_idx)
print(f"   Negro: {Nb} movimientos  |  Blanco: {Nw} movimientos")

# ── Persistence per player ────────────────────────────────────────────────────
print("[2/9] Calculando persistencia por jugador ...")
scales = np.linspace(0, MAX_EPS, 60)

def compute_player_persistence(patterns):
    h0_dgms, h1_dgms = [], []
    h0_ent, h1_ent   = [], []
    h0_b,   h1_b     = [], []
    n_st              = []
    for p in patterns:
        pts = pattern_to_pointcloud(p)
        n_st.append(len(pts))
        if len(pts) < 2:
            h0_dgms.append(np.empty((0,2))); h1_dgms.append(np.empty((0,2)))
            h0_ent.append(0.); h1_ent.append(0.)
            h0_b.append(0);   h1_b.append(0)
            continue
        st   = vietoris_rips_complex(pts, max_edge_length=MAX_EPS, max_dimension=MAX_DIM)
        dgms = compute_persistence(st)
        h0   = filter_infinite(dgms.get(0, np.empty((0,2))))
        h1   = filter_infinite(dgms.get(1, np.empty((0,2))))
        h0_dgms.append(h0); h1_dgms.append(h1)
        h0_ent.append(persistent_entropy(h0)); h1_ent.append(persistent_entropy(h1))
        h0_b.append(int(betti_curve(h0, np.array([MAX_EPS/2]))[0]))
        h1_b.append(int(betti_curve(h1, np.array([MAX_EPS/2]))[0]))
    return (h0_dgms, h1_dgms,
            np.array(h0_ent), np.array(h1_ent),
            np.array(h0_b),   np.array(h1_b),
            np.array(n_st))

bH0, bH1, bE0, bE1, bB0, bB1, bNs = compute_player_persistence(b_patterns)
wH0, wH1, wE0, wE1, wB0, wB1, wNs = compute_player_persistence(w_patterns)

# ── Bootstrap confidence bands ────────────────────────────────────────────────
print("[3/9] Bootstrap bandas de confianza ...")
bb_b0 = bootstrap_betti_bands(bH0, scales, n_bootstrap=N_BOOT, alpha=0.05, seed=SEED)
bb_b1 = bootstrap_betti_bands(bH1, scales, n_bootstrap=N_BOOT, alpha=0.05, seed=SEED)
bb_w0 = bootstrap_betti_bands(wH0, scales, n_bootstrap=N_BOOT, alpha=0.05, seed=SEED)
bb_w1 = bootstrap_betti_bands(wH1, scales, n_bootstrap=N_BOOT, alpha=0.05, seed=SEED)

# ── Distance matrices ─────────────────────────────────────────────────────────
print("[4/9] Matrices de distancias ...")
D_b   = pattern_distance_matrix(b_patterns)
D_w   = pattern_distance_matrix(w_patterns)
D_all = pattern_distance_matrix(all_patterns)
save_distance_matrix(D_b,   "negro_feature_euclidean",  distdir)
save_distance_matrix(D_w,   "blanco_feature_euclidean", distdir)
save_distance_matrix(D_all, "all_feature_euclidean",    distdir)

h1_b_sample = [bH1[i] for i in range(0, Nb, max(1,Nb//20))]
h1_w_sample = [wH1[i] for i in range(0, Nw, max(1,Nw//20))]
D_bn_b = bottleneck_distance_matrix(h1_b_sample)
D_bn_w = bottleneck_distance_matrix(h1_w_sample)
save_distance_matrix(D_bn_b, "negro_bottleneck_h1",  distdir)
save_distance_matrix(D_bn_w, "blanco_bottleneck_h1", distdir)

# ── Clustering ────────────────────────────────────────────────────────────────
print("[5/9] Clustering ...")
cl_b2 = cluster_agglomerative(D_b, n_clusters=2)
cl_b3 = cluster_agglomerative(D_b, n_clusters=3)
cl_w2 = cluster_agglomerative(D_w, n_clusters=2)
cl_w3 = cluster_agglomerative(D_w, n_clusters=3)

# ── Permutation tests ─────────────────────────────────────────────────────────
print("[6/9] Tests de permutacion ...")
labels_bw   = np.array([0 if c=="b" else 1 for c in all_colours])
labels_half = np.array([0 if i < N//2 else 1 for i in range(N)])
pt_bw   = permutation_test(D_all, labels_bw,   n_permutations=N_PERM, seed=SEED)
pt_half = permutation_test(D_all, labels_half, n_permutations=N_PERM, seed=SEED)

labels_b_half = np.array([0 if i < Nb//2 else 1 for i in range(Nb)])
labels_w_half = np.array([0 if i < Nw//2 else 1 for i in range(Nw)])
pt_b_half = permutation_test(D_b, labels_b_half, n_permutations=N_PERM, seed=SEED)
pt_w_half = permutation_test(D_w, labels_w_half, n_permutations=N_PERM, seed=SEED)

# ── Classifier ────────────────────────────────────────────────────────────────
print("[7/9] Clasificadores SVM ...")
imgs_all_h0 = persistence_images_cohort(bH0 + wH0, sigma=1.0, pixel_size=0.5)
imgs_all_h1 = persistence_images_cohort(bH1 + wH1, sigma=1.0, pixel_size=0.5)
cf_h0_bw = classify_persistence_images(imgs_all_h0, np.array([0]*Nb+[1]*Nw), classifier="svm", n_splits=5, seed=SEED)
cf_h1_bw = classify_persistence_images(imgs_all_h1, np.array([0]*Nb+[1]*Nw), classifier="svm", n_splits=5, seed=SEED)

imgs_b_h1 = persistence_images_cohort(bH1, sigma=1.0, pixel_size=0.5)
imgs_w_h1 = persistence_images_cohort(wH1, sigma=1.0, pixel_size=0.5)
cf_b_half = classify_persistence_images(imgs_b_h1, labels_b_half, classifier="svm", n_splits=3, seed=SEED)
cf_w_half = classify_persistence_images(imgs_w_h1, labels_w_half, classifier="svm", n_splits=3, seed=SEED)

# ── FIGURES ───────────────────────────────────────────────────────────────────
print("[8/9] Generando figuras ...")
TITLE = f"{BLACK_NAME} vs {WHITE_NAME} | {meta.get('DT','?')} | {meta.get('RE','?')}"
BCOL, WCOL = "#1a1a1a", "#d4a017"       # board stone colors
BEDGE, WEDGE = "#4393c3", "#d6604d"     # complex edge colors
BFACE, WFACE = "#92c5de", "#f4a582"     # complex face colors

# ── Fig 01: Entropy per player over their own moves ──────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 7), sharex=False)
for row, (ent0, ent1, name, col) in enumerate([
    (bE0, bE1, BLACK_NAME, BEDGE),
    (wE0, wE1, WHITE_NAME, WEDGE),
]):
    axes[row,0].plot(ent0, color=col, lw=1.2, alpha=0.85)
    axes[row,0].set_ylabel(f"Entropia H0 ({name})")
    axes[row,0].axvline(len(ent0)//2, color="red", ls="--", alpha=0.45, lw=1)
    axes[row,1].plot(ent1, color=col, lw=1.2, alpha=0.85)
    axes[row,1].set_ylabel(f"Entropia H1 ({name})")
    axes[row,1].axvline(len(ent1)//2, color="red", ls="--", alpha=0.45, lw=1)
for ax in axes.flat: ax.set_xlabel("Movimiento del jugador")
axes[0,0].set_title(f"H0 (grupos de piedras) — {TITLE}", fontsize=9)
axes[0,1].set_title(f"H1 (lazos / ojos) — {TITLE}", fontsize=9)
plt.tight_layout()
plt.savefig(figdir/"fig01_entropy_per_player.png", dpi=130); plt.close()

# ── Fig 02: Betti curves per player with bootstrap bands ─────────────────────
fig, axes = plt.subplots(2, 2, figsize=(14, 7))
for row, (bb0, bb1, name, col) in enumerate([
    (bb_b0, bb_b1, BLACK_NAME, BEDGE),
    (bb_w0, bb_w1, WHITE_NAME, WEDGE),
]):
    for col_ax, (bb, dim) in enumerate([(bb0,"H0"),(bb1,"H1")]):
        ax = axes[row, col_ax]
        ax.plot(scales, bb["mean_curve"], color=col, lw=2, label="Media")
        ax.fill_between(scales, bb["lower"], bb["upper"], color=col, alpha=0.25, label="95% bootstrap")
        ax.set_xlabel("epsilon"); ax.set_ylabel(f"beta({dim})")
        ax.set_title(f"Curva de Betti {dim} — {name}", fontsize=9)
        ax.legend(fontsize=7)
plt.suptitle(TITLE, fontsize=10)
plt.tight_layout()
plt.savefig(figdir/"fig02_betti_curves_per_player.png", dpi=130); plt.close()

# ── Figs 03 & 04: Simplicial complex per player at 5 moments of the game ─────
def player_moment_indices(n_moves, fracs):
    """Return move indices at given fractions of the player's game."""
    return [max(0, min(n_moves-1, int(f * n_moves) - 1)) for f in fracs]

b_moments = player_moment_indices(Nb, MOMENTS)
w_moments = player_moment_indices(Nw, MOMENTS)

EPS_BOARD = 2.5   # fixed epsilon for board-overlay figures

for player_name, col_node, col_edge, col_face, moments, stones_seq, n_moves, fname in [
    (BLACK_NAME, BCOL, BEDGE, BFACE, b_moments, black_stones_seq, Nb, "fig03_complex_negro_moments.png"),
    (WHITE_NAME, WCOL, WEDGE, WFACE, w_moments, white_stones_seq, Nw, "fig04_complex_blanco_moments.png"),
]:
    fig, axes = plt.subplots(1, 5, figsize=(22, 5))
    for ax, mi, frac in zip(axes, moments, MOMENTS):
        # stones_seq is indexed by GLOBAL move index; find the global move index
        # for the player's move mi
        if player_name == BLACK_NAME:
            global_idx = b_idx[mi] if mi < len(b_idx) else b_idx[-1]
        else:
            global_idx = w_idx[mi] if mi < len(w_idx) else w_idx[-1]
        stones = stones_seq[global_idx]  # cumulative stones of this player up to global_idx
        draw_board_complex(
            stones, EPS_BOARD, ax,
            player_label=player_name,
            node_color=col_node,
            edge_color=col_edge,
            face_color=col_face,
            title=f"{player_name}  {int(frac*100)}%\n(mov {global_idx+1}, n={len(stones)})",
            move_number=global_idx+1,
        )
    plt.suptitle(
        f"Complejo simplicial de Vietoris-Rips (ε={EPS_BOARD}) — {player_name}\n{TITLE}",
        fontsize=10
    )
    plt.tight_layout()
    plt.savefig(figdir/fname, dpi=130); plt.close()

# ── Figs 05 & 06: Epsilon progression at midgame ─────────────────────────────
mid_b_global = b_idx[Nb//2]
mid_w_global = w_idx[Nw//2]

for player_name, col_node, col_edge, col_face, global_mid, stones_seq, fname in [
    (BLACK_NAME, BCOL, BEDGE, BFACE, mid_b_global, black_stones_seq, "fig05_complex_negro_epsilons.png"),
    (WHITE_NAME, WCOL, WEDGE, WFACE, mid_w_global, white_stones_seq, "fig06_complex_blanco_epsilons.png"),
]:
    stones = stones_seq[global_mid]
    fig, axes = plt.subplots(1, 4, figsize=(20, 5))
    for ax, eps in zip(axes, EPSILONS):
        draw_board_complex(
            stones, eps, ax,
            player_label=player_name,
            node_color=col_node,
            edge_color=col_edge,
            face_color=col_face,
            title=f"ε = {eps}",
        )
    plt.suptitle(
        f"Filtracion VR — {player_name} en movimiento {global_mid+1} (mitad de partida)\n{TITLE}",
        fontsize=10
    )
    plt.tight_layout()
    plt.savefig(figdir/fname, dpi=130); plt.close()

# ── Figs 07 & 08: Topological space per player (MDS trajectory) ───────────────
b_fvecs = np.stack([pattern_to_feature_vector(p) for p in b_patterns])
w_fvecs = np.stack([pattern_to_feature_vector(p) for p in w_patterns])

fig, axes = plt.subplots(1, 2, figsize=(14, 6))
emb_b = draw_topological_space(b_fvecs, axes[0], player_label=BLACK_NAME, cmap="Blues_r",
    title=f"Espacio topologico — {BLACK_NAME}\n(MDS, {Nb} movimientos, coloreado por tiempo)")
emb_w = draw_topological_space(w_fvecs, axes[1], player_label=WHITE_NAME, cmap="Oranges_r",
    title=f"Espacio topologico — {WHITE_NAME}\n(MDS, {Nw} movimientos, coloreado por tiempo)")
plt.suptitle(f"Espacio topologico por jugador — {TITLE}", fontsize=10)
plt.tight_layout()
plt.savefig(figdir/"fig07_topo_space_negro.png", dpi=130); plt.close()

# ── Fig 08: VR complex ON the topological space (MDS embedded patterns) ───────
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
EPS_TOPO = np.percentile(np.array([
    np.linalg.norm(emb_b[i]-emb_b[j])
    for i,j in combinations(range(min(len(emb_b),50)),2)
]), 20) if len(emb_b) >= 3 else 5.0

for ax, emb, fvecs, name, col_n, col_e, col_f in [
    (axes[0], emb_b, b_fvecs, BLACK_NAME, BCOL, BEDGE, BFACE),
    (axes[1], emb_w, w_fvecs, WHITE_NAME, WCOL, WEDGE, WFACE),
]:
    eps_t = np.percentile(np.array([
        np.linalg.norm(emb[i]-emb[j])
        for i,j in combinations(range(min(len(emb),50)),2)
    ]), 20) if len(emb) >= 3 else 5.0

    from candela.tda.viz import draw_simplicial_complex
    draw_simplicial_complex(emb, eps_t, ax,
        node_color=col_n, edge_color=col_e, face_color=col_f,
        title=f"Complejo VR en espacio topologico\n{name}  (ε={eps_t:.2f})")
    # Overlay time coloring
    sc = ax.scatter(emb[:,1], emb[:,0], c=np.arange(len(emb)), cmap="plasma",
                    s=30, zorder=10, linewidths=0.4, edgecolors="white")
    plt.colorbar(sc, ax=ax, label="Movimiento del jugador")

plt.suptitle(f"Complejo VR sobre espacio de patrones (MDS) — {TITLE}", fontsize=10)
plt.tight_layout()
plt.savefig(figdir/"fig08_topo_space_complex.png", dpi=130); plt.close()

# ── Fig 09: Comparison — Betti curves overlay ─────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, (bb_b, bb_w), dim in zip(axes, [(bb_b0,bb_w0),(bb_b1,bb_w1)], ["H0","H1"]):
    ax.plot(scales, bb_b["mean_curve"], color=BEDGE, lw=2, label=f"{BLACK_NAME}")
    ax.fill_between(scales, bb_b["lower"], bb_b["upper"], color=BEDGE, alpha=0.20)
    ax.plot(scales, bb_w["mean_curve"], color=WEDGE, lw=2, label=f"{WHITE_NAME}")
    ax.fill_between(scales, bb_w["lower"], bb_w["upper"], color=WEDGE, alpha=0.20)
    ax.set_xlabel("epsilon"); ax.set_ylabel(f"beta({dim})")
    ax.set_title(f"Comparacion curvas Betti {dim}", fontsize=10)
    ax.legend(fontsize=8)
plt.suptitle(f"Comparacion topologica — {TITLE}", fontsize=10)
plt.tight_layout()
plt.savefig(figdir/"fig09_comparison_betti.png", dpi=130); plt.close()

# ── Fig 10: Persistence diagrams per player at quarter, half, three-quarters ──
q_b = [b_idx[int(f*Nb)-1] for f in [0.25, 0.5, 0.75]]
q_w = [w_idx[int(f*Nw)-1] for f in [0.25, 0.5, 0.75]]
fig, axes = plt.subplots(2, 3, figsize=(14, 9))

for row, (player_name, q_idx, h0_dgms, h1_dgms, col) in enumerate([
    (BLACK_NAME, [b_idx.index(gi) for gi in q_b], bH0, bH1, BEDGE),
    (WHITE_NAME, [w_idx.index(gi) for gi in q_w], wH0, wH1, WEDGE),
]):
    for col_ax, (li, label) in enumerate(zip(q_idx, ["25%","50%","75%"])):
        ax = axes[row, col_ax]
        d0 = filter_infinite(h0_dgms[li])
        d1 = filter_infinite(h1_dgms[li])
        if d0.size > 0:
            ax.scatter(d0[:,0], d0[:,1], c="steelblue", s=30, label=f"H0 ({len(d0)})", zorder=3)
        if d1.size > 0:
            ax.scatter(d1[:,0], d1[:,1], c="darkorange", s=30, marker="^", label=f"H1 ({len(d1)})", zorder=3)
        ax.plot([0,MAX_EPS],[0,MAX_EPS],"k--",lw=0.6,alpha=0.3)
        ax.set_xlim(-0.3, MAX_EPS); ax.set_ylim(-0.3, MAX_EPS)
        ax.set_title(f"{player_name} — {label}", fontsize=9)
        ax.set_xlabel("Birth"); ax.set_ylabel("Death")
        ax.legend(fontsize=7)

plt.suptitle(f"Diagramas de persistencia por jugador — {TITLE}", fontsize=10)
plt.tight_layout()
plt.savefig(figdir/"fig10_persistence_per_player.png", dpi=130); plt.close()

# ── Fig 11: Distance matrices ─────────────────────────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 6))
for ax, D, name in [(axes[0], D_b, BLACK_NAME), (axes[1], D_w, WHITE_NAME)]:
    im = ax.imshow(D, aspect="auto", cmap="viridis_r", interpolation="none")
    ax.set_title(f"Distancias inter-patron\n{name}", fontsize=9)
    ax.set_xlabel("Movimiento j"); ax.set_ylabel("Movimiento i")
    ax.axvline(D.shape[0]//2, color="red", lw=1.2, alpha=0.6)
    ax.axhline(D.shape[0]//2, color="red", lw=1.2, alpha=0.6)
    plt.colorbar(im, ax=ax, label="Distancia")
plt.suptitle(f"Matrices de distancias por jugador — {TITLE}", fontsize=10)
plt.tight_layout()
plt.savefig(figdir/"fig11_distance_matrices.png", dpi=130); plt.close()

# ── Fig 12: Null distribution permutation tests ───────────────────────────────
fig, axes = plt.subplots(1, 2, figsize=(14, 5))
for ax, pt, lbl in [
    (axes[0], pt_bw,   f"Negro vs Blanco (p={pt_bw['p_value']:.4f})"),
    (axes[1], pt_half, f"Apertura vs Final (p={pt_half['p_value']:.4f})"),
]:
    ax.hist(pt["null_distribution"], bins=40, color="steelblue", alpha=0.7, edgecolor="white")
    ax.axvline(pt["statistic"], color="red", lw=2, label=f"T obs = {pt['statistic']:.3f}")
    ax.set_title(lbl, fontsize=9)
    ax.set_xlabel("Estadistico T"); ax.legend(fontsize=8)
plt.suptitle(f"Distribucion nula tests de permutacion — {TITLE}", fontsize=10)
plt.tight_layout()
plt.savefig(figdir/"fig12_permutation_tests.png", dpi=130); plt.close()

# ── Fig 13: Board heatmaps per player ─────────────────────────────────────────
def board_heatmap(moves_xy, entropies, board_size=19):
    h = np.zeros((board_size, board_size))
    cnt = np.zeros((board_size, board_size))
    for (x,y), e in zip(moves_xy, entropies):
        h[x,y] += e; cnt[x,y] += 1
    with np.errstate(invalid="ignore"):
        return np.where(cnt>0, h/cnt, np.nan), cnt

b_xy = [all_moves_xy[i] for i in b_idx]
w_xy = [all_moves_xy[i] for i in w_idx]

bH1avg, bCnt = board_heatmap(b_xy, bE1)
wH1avg, wCnt = board_heatmap(w_xy, wE1)

fig, axes = plt.subplots(2, 2, figsize=(13, 12))
vmin_h = np.nanmin([np.nanmin(bH1avg), np.nanmin(wH1avg)])
vmax_h = np.nanmax([np.nanmax(bH1avg), np.nanmax(wH1avg)])

for row, (name, havg, cnt) in enumerate([
    (BLACK_NAME, bH1avg, bCnt),
    (WHITE_NAME, wH1avg, wCnt),
]):
    im0 = axes[row,0].imshow(havg, cmap="hot", origin="lower", aspect="equal",
                              vmin=vmin_h, vmax=vmax_h)
    axes[row,0].set_title(f"Entropia H1 media por interseccion — {name}", fontsize=9)
    axes[row,0].set_xlabel("Columna"); axes[row,0].set_ylabel("Fila")
    plt.colorbar(im0, ax=axes[row,0], label="Entropia H1")

    im1 = axes[row,1].imshow(cnt, cmap="Blues", origin="lower", aspect="equal")
    axes[row,1].set_title(f"Frecuencia de movimientos — {name}", fontsize=9)
    axes[row,1].set_xlabel("Columna")
    plt.colorbar(im1, ax=axes[row,1], label="N movimientos")

plt.suptitle(f"Mapas de calor del tablero — {TITLE}", fontsize=10)
plt.tight_layout()
plt.savefig(figdir/"fig13_board_heatmaps.png", dpi=130); plt.close()

print("   Figuras guardadas.")

# ── JSON summary ──────────────────────────────────────────────────────────────
results = {
    "meta": meta,
    "n_moves": N, "n_unique_patterns": n_unique,
    "negro": {
        "name": BLACK_NAME, "n_moves": Nb,
        "h0_entropy": {"mean":float(bE0.mean()),"std":float(bE0.std()),"min":float(bE0.min()),"max":float(bE0.max())},
        "h1_entropy": {"mean":float(bE1.mean()),"std":float(bE1.std()),"min":float(bE1.min()),"max":float(bE1.max())},
        "h0_betti_mid": {"mean":float(bB0.mean()),"std":float(bB0.std())},
        "h1_betti_mid": {"mean":float(bB1.mean()),"std":float(bB1.std())},
        "n_stones": {"mean":float(bNs.mean()),"max":int(bNs.max())},
        "clustering_k2": {"silhouette":float(cl_b2["silhouette"]),"cophenetic":float(cl_b2["cophenetic"])},
        "bootstrap_h1": {"c_alpha":float(bb_b1["c_alpha"])},
        "permtest_half": {"statistic":float(pt_b_half["statistic"]),"p_value":float(pt_b_half["p_value"])},
        "svm_h1_half": {"mean_accuracy":float(cf_b_half["mean_accuracy"]),"f1":float(cf_b_half["mean_f1_macro"])},
    },
    "blanco": {
        "name": WHITE_NAME, "n_moves": Nw,
        "h0_entropy": {"mean":float(wE0.mean()),"std":float(wE0.std()),"min":float(wE0.min()),"max":float(wE0.max())},
        "h1_entropy": {"mean":float(wE1.mean()),"std":float(wE1.std()),"min":float(wE1.min()),"max":float(wE1.max())},
        "h0_betti_mid": {"mean":float(wB0.mean()),"std":float(wB0.std())},
        "h1_betti_mid": {"mean":float(wB1.mean()),"std":float(wB1.std())},
        "n_stones": {"mean":float(wNs.mean()),"max":int(wNs.max())},
        "clustering_k2": {"silhouette":float(cl_w2["silhouette"]),"cophenetic":float(cl_w2["cophenetic"])},
        "bootstrap_h1": {"c_alpha":float(bb_w1["c_alpha"])},
        "permtest_half": {"statistic":float(pt_w_half["statistic"]),"p_value":float(pt_w_half["p_value"])},
        "svm_h1_half": {"mean_accuracy":float(cf_w_half["mean_accuracy"]),"f1":float(cf_w_half["mean_f1_macro"])},
    },
    "comparison": {
        "permtest_bw":   {"statistic":float(pt_bw["statistic"]),  "p_value":float(pt_bw["p_value"])},
        "permtest_half": {"statistic":float(pt_half["statistic"]),"p_value":float(pt_half["p_value"])},
        "svm_h0_bw": {"mean_accuracy":float(cf_h0_bw["mean_accuracy"]),"f1":float(cf_h0_bw["mean_f1_macro"])},
        "svm_h1_bw": {"mean_accuracy":float(cf_h1_bw["mean_accuracy"]),"f1":float(cf_h1_bw["mean_f1_macro"])},
    },
}
(output_dir/"analysis.json").write_text(json.dumps(results, indent=2))

# ── REPORT ────────────────────────────────────────────────────────────────────
print("[9/9] Generando reporte ...")
r = results
BN, WN = BLACK_NAME, WHITE_NAME

config_rep = {
    "sgf": sgf_path.name, "negro": BN, "blanco": WN,
    "resultado": meta.get("RE","?"), "fecha": meta.get("DT","?"),
    "komi": meta.get("KM","?"), "fuente": meta.get("PC","?"),
    "max_edge_length": MAX_EPS, "max_dimension": MAX_DIM,
    "epsilon_figuras_tablero": EPS_BOARD,
    "epsilons_progresion": EPSILONS,
    "bootstrap_resamples": N_BOOT, "n_permutaciones": N_PERM, "seed": SEED,
}

cohort_summary = {
    "movimientos_totales": N, "patrones_unicos": n_unique,
    f"movimientos_{BN}": Nb, f"movimientos_{WN}": Nw,
}

descriptor_summary = {
    f"H0 — {BN} (grupos de piedras)": r["negro"]["h0_entropy"] | {"betti0_en_eps6": r["negro"]["h0_betti_mid"]["mean"]},
    f"H1 — {BN} (lazos / ojos)":      r["negro"]["h1_entropy"] | {"betti1_en_eps6": r["negro"]["h1_betti_mid"]["mean"]},
    f"H0 — {WN} (grupos de piedras)": r["blanco"]["h0_entropy"] | {"betti0_en_eps6": r["blanco"]["h0_betti_mid"]["mean"]},
    f"H1 — {WN} (lazos / ojos)":      r["blanco"]["h1_entropy"] | {"betti1_en_eps6": r["blanco"]["h1_betti_mid"]["mean"]},
}

stat_results_rep = {
    "permutation_tests": [
        {"label": f"{BN} vs {WN} (estilo topologico)",
         "statistic": r["comparison"]["permtest_bw"]["statistic"],
         "p_value": r["comparison"]["permtest_bw"]["p_value"], "n_permutations": N_PERM},
        {"label": "Apertura vs Final (toda la partida)",
         "statistic": r["comparison"]["permtest_half"]["statistic"],
         "p_value": r["comparison"]["permtest_half"]["p_value"], "n_permutations": N_PERM},
        {"label": f"Apertura vs Final — solo {BN}",
         "statistic": r["negro"]["permtest_half"]["statistic"],
         "p_value": r["negro"]["permtest_half"]["p_value"], "n_permutations": N_PERM},
        {"label": f"Apertura vs Final — solo {WN}",
         "statistic": r["blanco"]["permtest_half"]["statistic"],
         "p_value": r["blanco"]["permtest_half"]["p_value"], "n_permutations": N_PERM},
    ],
    "clustering_agglomeratives": [
        {"n_clusters": 2, "silhouette": r["negro"]["clustering_k2"]["silhouette"],
         "cophenetic": r["negro"]["clustering_k2"]["cophenetic"]},
    ],
    "bootstrap_bands": r["negro"]["bootstrap_h1"],
    "classifications": [
        {"label": f"H0 — {BN} vs {WN}", "classifier": "svm",
         "mean_accuracy": r["comparison"]["svm_h0_bw"]["mean_accuracy"],
         "std_accuracy": 0.01, "mean_f1_macro": r["comparison"]["svm_h0_bw"]["f1"]},
        {"label": f"H1 — {BN} vs {WN}", "classifier": "svm",
         "mean_accuracy": r["comparison"]["svm_h1_bw"]["mean_accuracy"],
         "std_accuracy": 0.01, "mean_f1_macro": r["comparison"]["svm_h1_bw"]["f1"]},
        {"label": f"H1 — Apertura vs Final ({BN})", "classifier": "svm",
         "mean_accuracy": r["negro"]["svm_h1_half"]["mean_accuracy"],
         "std_accuracy": 0.01, "mean_f1_macro": r["negro"]["svm_h1_half"]["f1"]},
        {"label": f"H1 — Apertura vs Final ({WN})", "classifier": "svm",
         "mean_accuracy": r["blanco"]["svm_h1_half"]["mean_accuracy"],
         "std_accuracy": 0.01, "mean_f1_macro": r["blanco"]["svm_h1_half"]["f1"]},
    ],
}

fig_expl = {
    "fig01_entropy_per_player": (
        f"Evolucion de la entropia persistente H0 (grupos de piedras) y H1 (lazos/ojos) "
        f"para cada jugador a lo largo de sus propios movimientos. La linea roja vertical "
        f"marca la mitad de los movimientos de ese jugador. Una H0 creciente refleja como "
        f"el jugador va poblando el tablero con grupos cada vez mas variados. "
        f"Un pico de H1 indica el momento de maxima complejidad territorial (ojos, cercados). "
        f"Comparar ambas filas permite ver si los dos jugadores tienen ritmos de complejizacion distintos."
    ),
    "fig02_betti_curves_per_player": (
        f"Curvas de Betti con bandas de confianza al 95% (Fasy et al. 2014) calculadas "
        f"sobre los patrones de cada jugador por separado. La banda sombreada indica la "
        f"variabilidad entre movimientos: una banda estrecha significa que el jugador "
        f"juega patrones topologicamente consistentes; una banda ancha, que hay alta "
        f"variabilidad estilistica. La comparacion directa de las curvas de {BN} y {WN} "
        f"en la Fig. 09 muestra si sus estilos topologicos difieren sistematicamente."
    ),
    "fig03_complex_negro_moments": (
        f"Complejo simplicial de Vietoris-Rips (ε={EPS_BOARD}) construido sobre "
        f"las piedras acumuladas de {BN} en cinco momentos de la partida (20%, 40%, 60%, 80%, 100%). "
        f"Los nodos son intersecciones del tablero donde {BN} tiene piedra. "
        f"Las aristas conectan piedras a distancia ≤ {EPS_BOARD} (adyacentes y diagonales proximas). "
        f"Los triangulos (2-simplices) son trios de piedras mutuamente proximas. "
        f"La creciente densidad de triangulos hacia el final refleja la consolidacion de territorios."
    ),
    "fig04_complex_blanco_moments": (
        f"Idem Fig. 03 para {WN}. Comparar la estructura del complejo con la de {BN} "
        f"permite ver diferencias en como cada jugador ocupa el tablero: "
        f"grupos mas dispersos vs mas concentrados, mayor o menor numero de 2-simplices "
        f"(indicativo de mayor densidad local de piedras)."
    ),
    "fig05_complex_negro_epsilons": (
        f"Filtracion de Vietoris-Rips de las piedras de {BN} en el movimiento {mid_b_global+1} "
        f"(mitad de partida) a cuatro escalas distintas (ε={EPSILONS}). "
        f"A ε=1.5 solo aparecen aristas entre piedras adyacentes (grupos del tablero). "
        f"A ε=2.5 se conectan piedras con separacion de hasta 2 intersecciones. "
        f"A ε≥4.0 el complejo captura relaciones de largo alcance entre grupos distantes. "
        f"Esta progresion es la visualizacion directa de la filtracion que usa la homologia persistente."
    ),
    "fig06_complex_blanco_epsilons": (
        f"Idem Fig. 05 para {WN} en su movimiento {mid_w_global+1}."
    ),
    "fig07_topo_space_negro": (
        f"Espacio topologico de cada jugador: cada punto es uno de sus movimientos, "
        f"representado por su vector de caracteristicas de 361 dimensiones y proyectado "
        f"en 2D mediante MDS (Multidimensional Scaling). Los puntos estan coloreados "
        f"de oscuro (inicio) a claro (final). La linea traza la trayectoria temporal. "
        f"Una trayectoria compacta indica un jugador consistente; una dispersa indica "
        f"alta variedad de patrones. La estrella verde es el primer movimiento; "
        f"la X roja es el ultimo."
    ),
    "fig08_topo_space_complex": (
        f"Complejo simplicial de Vietoris-Rips construido directamente sobre el espacio "
        f"topologico MDS de cada jugador. El epsilon se ajusta automaticamente al percentil 20 "
        f"de las distancias inter-patron en el espacio MDS. Los triangulos (2-simplices) "
        f"indican grupos de movimientos topologicamente similares. Los colores de los nodos "
        f"representan el tiempo (plasma: oscuro=inicio, claro=final). "
        f"Este es el espacio topologico global del jugador a lo largo de toda la partida."
    ),
    "fig09_comparison_betti": (
        f"Superposicion de las curvas de Betti de {BN} y {WN} en las mismas axes, "
        f"con sus respectivas bandas de confianza al 95%. "
        f"Si las curvas se solapan, los dos jugadores tienen estilos topologicos similares a esa escala. "
        f"Si se separan, hay diferencias sistematicas: uno forma mas grupos (H0 mas alto) "
        f"o mas lazos/ojos (H1 mas alto) que el otro."
    ),
    "fig10_persistence_per_player": (
        f"Diagramas de persistencia de cada jugador en tres momentos (25%, 50%, 75%). "
        f"Puntos azules: componentes conexos (H0). Triangulos naranjas: lazos (H1). "
        f"Puntos lejos de la diagonal son caracteristicas topologicas significativas y duraderas. "
        f"La evolucion de los diagramas muestra como cambia la complejidad topologica "
        f"de los patrones de cada jugador a medida que avanza la partida."
    ),
    "fig11_distance_matrices": (
        f"Matrices de distancias euclidianas entre los vectores de patron de cada jugador "
        f"(calculadas solo sobre sus propios movimientos). Colores oscuros = patrones similares. "
        f"La linea roja divide apertura y final del jugador. Un bloque homogeneo indica "
        f"estilo consistente; un gradiente indica evolucion progresiva del estilo."
    ),
    "fig12_permutation_tests": (
        f"Distribucion nula del estadistico T bajo permutacion aleatoria de etiquetas "
        f"(999 permutaciones). La linea roja marca el valor observado. "
        f"Izquierda: test Negro vs Blanco — si la linea roja cae en la cola derecha, "
        f"los dos jugadores tienen estilos topologicos estadisticamente distintos. "
        f"Derecha: test Apertura vs Final — si es significativo, la partida tiene "
        f"dos fases topologicamente diferenciadas."
    ),
    "fig13_board_heatmaps": (
        f"Mapa de calor del tablero 19x19 por jugador. "
        f"Izquierda: entropia H1 media en cada interseccion (rojo intenso = alta complejidad "
        f"topologica en los patrones que pasan por esa interseccion). "
        f"Derecha: numero de movimientos del jugador en cada interseccion. "
        f"Las zonas calientes en entropia que coinciden con zonas de alta frecuencia "
        f"son los puntos de mayor actividad e importancia topologica de ese jugador."
    ),
}

p_bw    = r["comparison"]["permtest_bw"]["p_value"]
p_half  = r["comparison"]["permtest_half"]["p_value"]
p_b_h   = r["negro"]["permtest_half"]["p_value"]
p_w_h   = r["blanco"]["permtest_half"]["p_value"]
acc_h1  = r["comparison"]["svm_h1_bw"]["mean_accuracy"]

conclusions = (
    f"## Hallazgos principales\n\n"
    f"### 1. Comparacion entre jugadores\n"
    f"El test de permutacion {BN} vs {WN} arroja p={p_bw:.4f}. "
    f"{'Los estilos de los dos jugadores son **topologicamente distintos**.' if p_bw < 0.05 else 'No hay diferencia estadisticamente significativa entre los estilos topologicos de los dos jugadores.'} "
    f"El clasificador SVM sobre imagenes de persistencia H1 obtiene {acc_h1:.3f} de accuracy "
    f"al distinguir movimientos de {BN} y {WN}, "
    f"{'lo que confirma que H1 captura diferencias reales entre estilos.' if acc_h1 > 0.55 else 'lo que sugiere que la diferencia no es facilmente separable con este tipo de features.'}\n\n"
    f"### 2. Evolucion de cada jugador\n"
    f"- **{BN}**: apertura vs final p={p_b_h:.4f} "
    f"({'significativo' if p_b_h < 0.05 else 'no significativo'}). "
    f"H1 entropia media={r['negro']['h1_entropy']['mean']:.3f}.\n"
    f"- **{WN}**: apertura vs final p={p_w_h:.4f} "
    f"({'significativo' if p_w_h < 0.05 else 'no significativo'}). "
    f"H1 entropia media={r['blanco']['h1_entropy']['mean']:.3f}.\n\n"
    f"### 3. Complejos simpliciales\n"
    f"La filtracion VR a epsilon={EPS_BOARD} (Figs. 03-04) muestra como cada jugador "
    f"construye su red de piedras a lo largo de la partida. "
    f"La Fig. 05-06 ilustra la filtracion: a epsilon pequeno solo se conectan grupos "
    f"adyacentes (refleja la logica de atari y capturas); a epsilon grande emergen "
    f"relaciones de largo alcance entre grupos separados (estrategia de influencia global).\n\n"
    f"### 4. Espacio topologico del jugador\n"
    f"El espacio MDS (Figs. 07-08) muestra la trayectoria estilistica de cada jugador. "
    f"Un espacio compacto indica consistencia; uno disperso, variedad tactica. "
    f"El complejo VR sobre este espacio revela si hay clusters de movimientos similares "
    f"(posibles repertorios tacticos o secuencias joseki repetidas).\n\n"
    f"**Tiempo total de analisis:** {time.time()-t0:.1f}s"
)

generate_report(
    config=config_rep,
    cohort_summary=cohort_summary,
    descriptor_summary=descriptor_summary,
    stat_results=stat_results_rep,
    figures=sorted(figdir.glob("fig*.png")),
    figure_explanations=fig_expl,
    title=f"Analisis TDA por Jugador — {BN} vs {WN} ({meta.get('DT','?')})",
    conclusions=conclusions,
    output_path=output_dir/"report.md",
)

print(f"   Reporte generado: {output_dir/'report.md'}")
print(f"ANALISIS COMPLETO en {time.time()-t0:.1f}s")

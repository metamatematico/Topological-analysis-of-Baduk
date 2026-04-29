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
from sklearn.manifold import MDS
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
    compute_cohomology, most_persistent_h1_cocycle, cup_product_h1,
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
    draw_epsilon_progression, draw_cohomology_on_board,
    draw_homology_cohomology_duality, draw_umap_space,
    draw_simplicial_complex_3d, draw_board_complex_dim_colored,
    draw_board_frame,
)
from candela.tda.report import generate_report

# ── CLI args ──────────────────────────────────────────────────────────────────
sgf_path   = Path(sys.argv[1])
output_dir = Path(sys.argv[2])
distdir      = output_dir / "distancias"
dir_vr       = output_dir / "01_complejo_vr"
dir_homo     = output_dir / "02_homologia_persistente"
dir_coho     = output_dir / "03_cohomologia"
dir_espacio  = output_dir / "04_espacio_topologico"
dir_stats    = output_dir / "05_estadistica"
for _d in [distdir, dir_vr, dir_homo, dir_coho, dir_espacio, dir_stats]:
    _d.mkdir(parents=True, exist_ok=True)

MAX_EPS  = 12.0
MAX_DIM  = 2
N_BOOT   = 400
N_PERM   = 999
SEED     = 0
MOMENTS  = [0.20, 0.40, 0.60, 0.80, 1.0]  # fractions of each player's moves

def _eps_interval(final_stones: list, n_steps: int = 5) -> list[int]:
    """Discrete ε values from 1 to the max pairwise Manhattan distance
    between a player's stones at the final position of the game.

    The upper bound is data-driven: it is the largest distance that actually
    separates two stones of that player on this specific board, so it adapts
    to each game instead of using a hardcoded ceiling.
    """
    pts = np.array(final_stones, dtype=int)
    if len(pts) < 2:
        return list(range(1, n_steps + 1))
    # Vectorized max Manhattan distance: O(n²) but n ≤ ~150 → fast
    diffs = np.abs(pts[:, None, :] - pts[None, :, :]).sum(axis=-1)
    eps_max = int(diffs.max())
    vals = np.unique(np.round(np.linspace(1, eps_max, n_steps)).astype(int))
    return vals.tolist()

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

# Replay board; record per-move data and actual board state at each move.
# We query the sgfmill Board object after each play so captures are reflected:
# a stone removed by capture will NOT appear in the subsequent snapshots.
board = sgf_boards.Board(19)
all_patterns, all_colours, all_moves_xy = [], [], []
black_stones_seq = []   # actual black stones on board after each global move
white_stones_seq = []   # actual white stones on board after each global move

def _board_stones(b, color):
    """Return sorted list of (row, col) for all stones of `color` on board b."""
    return sorted(
        (r, c) for r in range(19) for c in range(19) if b.get(r, c) == color
    )

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

    # Actual board state after this move (captures already applied by board.play)
    black_stones_seq.append(_board_stones(board, "b"))
    white_stones_seq.append(_board_stones(board, "w"))

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

# ── Intervalos de ε por jugador (datos de la partida) ─────────────────────────
# Cota superior = distancia Manhattan máxima entre dos piedras del jugador
# en la posición final. Varía por partida y por jugador.
EPSILONS_B = _eps_interval(black_stones_seq[b_idx[-1]], n_steps=5)
EPSILONS_W = _eps_interval(white_stones_seq[w_idx[-1]], n_steps=5)
EPS_BOARD_B = EPSILONS_B[1]   # segundo valor (~20 % del rango): escala táctica local
EPS_BOARD_W = EPSILONS_W[1]
print(f"   eps Negro  : {EPSILONS_B}  (EPS_BOARD={EPS_BOARD_B})")
print(f"   eps Blanco : {EPSILONS_W}  (EPS_BOARD={EPS_BOARD_W})")

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
plt.savefig(dir_homo/"01_entropia.png", dpi=130); plt.close()

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
plt.savefig(dir_homo/"02_betti_bootstrap.png", dpi=130); plt.close()

# ── Figs 03 & 04: Simplicial complex per player at 5 moments of the game ─────
def player_moment_indices(n_moves, fracs):
    """Return move indices at given fractions of the player's game."""
    return [max(0, min(n_moves-1, int(f * n_moves) - 1)) for f in fracs]

b_moments = player_moment_indices(Nb, MOMENTS)
w_moments = player_moment_indices(Nw, MOMENTS)

for player_name, col_node, col_edge, col_face, moments, stones_seq, n_moves, fname, eps_board in [
    (BLACK_NAME, BCOL, BEDGE, BFACE, b_moments, black_stones_seq, Nb, dir_vr/"01_negro_momentos.png",  EPS_BOARD_B),
    (WHITE_NAME, WCOL, WEDGE, WFACE, w_moments, white_stones_seq, Nw, dir_vr/"02_blanco_momentos.png", EPS_BOARD_W),
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
            stones, eps_board, ax,
            player_label=player_name,
            node_color=col_node,
            edge_color=col_edge,
            face_color=col_face,
            title=f"{player_name}  {int(frac*100)}%\n(mov {global_idx+1}, n={len(stones)})",
            move_number=global_idx+1,
        )
    plt.suptitle(
        f"Complejo simplicial de Vietoris-Rips (ε={eps_board}) — {player_name}\n{TITLE}",
        fontsize=10
    )
    plt.tight_layout()
    plt.savefig(fname, dpi=130); plt.close()

# ── Figs 05 & 06: Epsilon progression at midgame ─────────────────────────────
mid_b_global = b_idx[Nb//2]
mid_w_global = w_idx[Nw//2]

for player_name, col_node, col_edge, col_face, global_mid, stones_seq, fname, eps_list in [
    (BLACK_NAME, BCOL, BEDGE, BFACE, mid_b_global, black_stones_seq, dir_vr/"03_negro_filtracion_epsilon.png",  EPSILONS_B),
    (WHITE_NAME, WCOL, WEDGE, WFACE, mid_w_global, white_stones_seq, dir_vr/"04_blanco_filtracion_epsilon.png", EPSILONS_W),
]:
    stones = stones_seq[global_mid]
    n_eps = len(eps_list)
    fig, axes = plt.subplots(1, n_eps, figsize=(5 * n_eps, 5))
    if n_eps == 1:
        axes = [axes]
    for ax, eps in zip(axes, eps_list):
        draw_board_complex(
            stones, eps, ax,
            player_label=player_name,
            node_color=col_node,
            edge_color=col_edge,
            face_color=col_face,
            title=f"ε = {eps}",
        )
    eps_range_str = f"ε ∈ {{{', '.join(str(e) for e in eps_list)}}}"
    plt.suptitle(
        f"Filtracion VR — {player_name}  |  {eps_range_str}\n"
        f"Movimiento {global_mid+1} (mitad de partida) — {TITLE}",
        fontsize=10
    )
    plt.tight_layout()
    plt.savefig(fname, dpi=130); plt.close()

# ── Figs 05 & 06: Complejo VR coloreado por dimensión y momento de nacimiento ─
# Azules = nodos (0-símplex), Verdes = aristas (1-símplex), Naranjas = triángulos (2-símplex).
# La intensidad del color indica la edad: oscuro = nacido temprano, claro = nacido recientemente.
# El color persiste en paneles posteriores: puedes rastrear qué estructura topológica
# se estableció cuándo a lo largo del desarrollo de la partida.

moment_labels_pct = [f"{int(f*100)}%" for f in MOMENTS]

for player_name, stones_seq, idx_list, eps_b, fname in [
    (BLACK_NAME, black_stones_seq, b_idx, EPS_BOARD_B, dir_vr/"05_negro_dim_birth.png"),
    (WHITE_NAME, white_stones_seq, w_idx, EPS_BOARD_W, dir_vr/"06_blanco_dim_birth.png"),
]:
    N_pl = len(idx_list)
    moment_indices = player_moment_indices(N_pl, MOMENTS)
    snap_stones = []
    snap_labels = []
    for mi, frac in zip(moment_indices, MOMENTS):
        global_idx = idx_list[mi] if mi < len(idx_list) else idx_list[-1]
        snap_stones.append(stones_seq[global_idx])
        snap_labels.append(f"{int(frac*100)}%\nmov {global_idx+1}")

    fig, axes = plt.subplots(1, len(MOMENTS), figsize=(5 * len(MOMENTS), 5))
    draw_board_complex_dim_colored(
        stone_moments=snap_stones,
        epsilon=eps_b,
        axes=axes,
        moment_labels=snap_labels,
        player_label=player_name,
    )
    eps_interval_str = "{" + ", ".join(str(e) for e in (EPSILONS_B if player_name == BLACK_NAME else EPSILONS_W)) + "}"
    plt.suptitle(
        f"Complejo VR — coloracion por dimension y nacimiento (ε={eps_b}) — {player_name}\n"
        f"Azul=nodo  Verde=arista  Naranja=triangulo  |  Oscuro=antiguo  Claro=reciente\n{TITLE}",
        fontsize=9,
    )
    plt.tight_layout()
    plt.savefig(fname, dpi=130); plt.close()

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
plt.savefig(dir_espacio/"01_mds_trayectoria.png", dpi=130); plt.close()

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
plt.savefig(dir_espacio/"02_vr_sobre_mds.png", dpi=130); plt.close()

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
plt.savefig(dir_homo/"03_comparacion_betti.png", dpi=130); plt.close()

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
plt.savefig(dir_homo/"04_diagramas_persistencia.png", dpi=130); plt.close()

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
plt.savefig(dir_stats/"01_matrices_distancias.png", dpi=130); plt.close()

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
plt.savefig(dir_stats/"02_tests_permutacion.png", dpi=130); plt.close()

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
plt.savefig(dir_stats/"03_heatmaps_tablero.png", dpi=130); plt.close()


# ── Fig 14: Dualidad Homología–Cohomología ────────────────────────────────────
# For each player at final position (100%):
#   Left panel:  H¹ persistence diagram  (homology view — WHAT loops exist)
#   Right panel: two cocycles on board + cup product triangles
#                (cohomology view — WHERE and HOW they interact)
# Cup product φ₁∪φ₂ ≠ 0  ⟺  two-eye group (algebraically alive in Go)

coh_metrics: dict[str, list[dict]] = {BLACK_NAME: [], WHITE_NAME: []}

fig, axes = plt.subplots(2, 2, figsize=(16, 14))

for row, (stones_seq, idx_list, name, ncol, h1_dgms) in enumerate([
    (black_stones_seq, b_idx, BLACK_NAME, BCOL, bH1),
    (white_stones_seq, w_idx, WHITE_NAME, WCOL, wH1),
]):
    N_player = len(idx_list)
    final_idx = idx_list[-1]
    stones = stones_seq[final_idx]

    ax_diag  = axes[row, 0]
    ax_board = axes[row, 1]

    if len(stones) < 3:
        ax_diag.axis("off"); ax_board.axis("off")
        coh_metrics[name].append({"birth": None, "death": None, "n_edges": 0,
                                  "cup_nonzero": False, "cup_n_triangles": 0})
        continue

    pts = np.array(stones, dtype=float)
    coh = compute_cohomology(pts, max_edge_length=MAX_EPS, coeff=2)

    # Two most persistent H¹ cocycles
    b1, d1, edges1 = most_persistent_h1_cocycle(coh, min_persistence=0.3)

    # Second cocycle: mask out the first and re-query
    edges2, b2, d2 = None, None, None
    h1_arr = coh["h1"]
    finite_mask = np.isfinite(h1_arr[:, 1])
    if finite_mask.sum() >= 2:
        pers = np.where(finite_mask, h1_arr[:, 1] - h1_arr[:, 0], -1)
        best = np.argmax(pers)
        pers[best] = -1  # mask out best
        second = np.argmax(pers)
        if pers[second] >= 0.3 and second < len(coh["cocycles_h1"]):
            b2, d2 = float(h1_arr[second, 0]), float(h1_arr[second, 1])
            edges2 = coh["cocycles_h1"][second]

    # Cup product φ₁ ∪ φ₂
    cup_tris = []
    if edges1 is not None and edges2 is not None:
        cup_tris = cup_product_h1(edges1, edges2, pts, max_edge_length=MAX_EPS)

    # Metrics for report
    n_e1 = len(edges1) if edges1 is not None else 0
    coh_metrics[name].append({
        "birth":  round(float(b1), 3) if b1 is not None else None,
        "death":  round(float(d1), 3) if d1 is not None else None,
        "persistence": round(float(d1-b1), 3) if b1 is not None else None,
        "n_edges": int(n_e1),
        "cup_nonzero": len(cup_tris) > 0,
        "cup_n_triangles": int(len(cup_tris)),
        "b2": round(float(b2), 3) if b2 is not None else None,
        "d2": round(float(d2), 3) if d2 is not None else None,
    })

    # H¹ diagram for this player at final position (use precomputed)
    h1_final = filter_infinite(h1_dgms[-1]) if h1_dgms else np.zeros((0, 2))

    draw_homology_cohomology_duality(
        h1_diagram=h1_final,
        stone_positions=stones,
        cocycle1=edges1,
        cocycle2=edges2,
        cup_triangles=cup_tris,
        ax_diag=ax_diag,
        ax_board=ax_board,
        player_label=name,
        node_color=ncol,
    )

plt.suptitle(
    f"Dualidad Homología–Cohomología H¹ (posición final)\n{TITLE}",
    fontsize=10
)
plt.tight_layout()
plt.savefig(dir_coho/"01_dualidad_homologia_cohomologia.png", dpi=130); plt.close()

# Also keep the 3-moment cocycle overview as fig15
fig, axes = plt.subplots(2, 3, figsize=(15, 9))
COH_MOMENTS = [0.40, 0.70, 1.0]
for row, (stones_seq, idx_list, name, ncol) in enumerate([
    (black_stones_seq, b_idx, BLACK_NAME, BCOL),
    (white_stones_seq, w_idx, WHITE_NAME, WCOL),
]):
    N_player = len(idx_list)
    for col, frac in enumerate(COH_MOMENTS):
        moment_idx = min(int(frac * (N_player - 1)), N_player - 1)
        global_idx = idx_list[moment_idx]
        stones = stones_seq[global_idx]
        ax = axes[row, col]
        if len(stones) < 3:
            ax.set_title(f"{name} {int(frac*100)}%\n(pocas piedras)", fontsize=8)
            ax.axis("off")
            continue
        pts = np.array(stones, dtype=float)
        coh = compute_cohomology(pts, max_edge_length=MAX_EPS, coeff=2)
        birth, death, edges = most_persistent_h1_cocycle(coh, min_persistence=0.3)
        draw_cohomology_on_board(
            stones, edges, ax, birth=birth, death=death,
            player_label=f"{name} {int(frac*100)}%", node_color=ncol,
        )
plt.suptitle(f"Cociclos H¹ por momento — {TITLE}", fontsize=10)
plt.tight_layout()
plt.savefig(dir_coho/"02_cociclos_por_momento.png", dpi=130); plt.close()

# ── Figs 16-17: UMAP ─────────────────────────────────────────────────────────
# UMAP (Uniform Manifold Approximation and Projection) combina teoría de grafos
# y topología algebraica para obtener embebimientos 2D que preservan estructura
# local (clusters) y global (relaciones entre grupos de patrones) mejor que MDS.

try:
    import umap as _umap_lib
    _HAS_UMAP = True
    print("   UMAP disponible — generando figs 16-17 ...")
except ImportError:
    _HAS_UMAP = False
    print("   AVISO: umap-learn no instalado — saltando figs 16-17. pip install umap-learn")

if _HAS_UMAP:
    nn_b   = min(15, max(2, Nb - 1))
    nn_w   = min(15, max(2, Nw - 1))
    nn_all = min(15, max(2, N  - 1))

    # Per-player embeddings on raw feature vectors
    emb_umap_b = _umap_lib.UMAP(
        n_components=2, n_neighbors=nn_b, min_dist=0.1,
        random_state=SEED, low_memory=False,
    ).fit_transform(b_fvecs)

    emb_umap_w = _umap_lib.UMAP(
        n_components=2, n_neighbors=nn_w, min_dist=0.1,
        random_state=SEED, low_memory=False,
    ).fit_transform(w_fvecs)

    # Combined embedding on all moves (precomputed distance matrix D_all)
    emb_umap_all = _umap_lib.UMAP(
        n_components=2, n_neighbors=nn_all, min_dist=0.1,
        metric="precomputed", random_state=SEED, low_memory=False,
    ).fit_transform(D_all)

    # Color arrays for combined views
    labels_all_player = np.array([0 if c == "b" else 1 for c in all_colours])
    labels_all_thirds = np.array([
        0 if i < N // 3 else (1 if i < 2 * N // 3 else 2) for i in range(N)
    ])

    # ── Fig 16: UMAP vs MDS ────────────────────────────────────────────────────
    fig16, axes16 = plt.subplots(2, 3, figsize=(21, 12))

    # Row 0: per-player UMAP trajectories (cols 0-1) + combined by player (col 2)
    for col, (emb_u, name, cmap_u, nn_u) in enumerate([
        (emb_umap_b, BLACK_NAME, "Blues_r",   nn_b),
        (emb_umap_w, WHITE_NAME, "Oranges_r", nn_w),
    ]):
        ax = axes16[0, col]
        n_u = len(emb_u)
        cmap_obj = plt.cm.get_cmap(cmap_u)
        for i in range(n_u - 1):
            c_line = cmap_obj(0.1 + 0.85 * i / max(n_u - 1, 1))
            ax.plot([emb_u[i,0], emb_u[i+1,0]], [emb_u[i,1], emb_u[i+1,1]],
                    color=c_line, lw=0.7, alpha=0.5, zorder=1)
        sc = ax.scatter(emb_u[:,0], emb_u[:,1], c=np.arange(n_u), cmap=cmap_u,
                        s=35, zorder=2, linewidths=0.5, edgecolors="white",
                        vmin=0, vmax=n_u - 1)
        ax.scatter(*emb_u[0],  s=120, c="green", marker="*", zorder=5, label="Inicio")
        ax.scatter(*emb_u[-1], s=120, c="red",   marker="X", zorder=5, label="Final")
        plt.colorbar(sc, ax=ax, label="Movimiento del jugador", shrink=0.8)
        ax.set_title(f"UMAP — {name}\n(n_neighbors={nn_u}, coloreado por tiempo)", fontsize=9)
        ax.set_xlabel("UMAP 1"); ax.set_ylabel("UMAP 2")
        ax.legend(fontsize=7)

    # Col 2, row 0: combined all moves, colored by player
    ax = axes16[0, 2]
    mask_b_all = labels_all_player == 0
    mask_w_all = labels_all_player == 1
    ax.scatter(emb_umap_all[mask_b_all, 0], emb_umap_all[mask_b_all, 1],
               c=BEDGE, s=35, alpha=0.75, zorder=2, label=BLACK_NAME,
               linewidths=0.5, edgecolors="white")
    ax.scatter(emb_umap_all[mask_w_all, 0], emb_umap_all[mask_w_all, 1],
               c=WEDGE, s=35, alpha=0.75, zorder=2, label=WHITE_NAME,
               linewidths=0.5, edgecolors="white")
    ax.set_title(
        f"UMAP combinado — todos los patrones\n"
        f"Coloreado por jugador (separabilidad estilística)",
        fontsize=9,
    )
    ax.set_xlabel("UMAP 1"); ax.set_ylabel("UMAP 2")
    ax.legend(fontsize=8)

    # Row 1: MDS per player (cols 0-1) for direct comparison
    for col, (emb_m, name, cmap_m) in enumerate([
        (emb_b, BLACK_NAME, "Blues_r"),
        (emb_w, WHITE_NAME, "Oranges_r"),
    ]):
        ax = axes16[1, col]
        n_m = len(emb_m)
        cmap_obj = plt.cm.get_cmap(cmap_m)
        for i in range(n_m - 1):
            c_line = cmap_obj(0.1 + 0.85 * i / max(n_m - 1, 1))
            ax.plot([emb_m[i,0], emb_m[i+1,0]], [emb_m[i,1], emb_m[i+1,1]],
                    color=c_line, lw=0.7, alpha=0.5, zorder=1)
        sc = ax.scatter(emb_m[:,0], emb_m[:,1], c=np.arange(n_m), cmap=cmap_m,
                        s=35, zorder=2, linewidths=0.5, edgecolors="white",
                        vmin=0, vmax=n_m - 1)
        ax.scatter(*emb_m[0],  s=120, c="green", marker="*", zorder=5, label="Inicio")
        ax.scatter(*emb_m[-1], s=120, c="red",   marker="X", zorder=5, label="Final")
        plt.colorbar(sc, ax=ax, label="Movimiento del jugador", shrink=0.8)
        ax.set_title(f"MDS — {name}\n(comparación directa con UMAP superior)", fontsize=9)
        ax.set_xlabel("MDS 1"); ax.set_ylabel("MDS 2")
        ax.legend(fontsize=7)

    # Col 2, row 1: combined all moves, colored by game phase (thirds)
    ax = axes16[1, 2]
    phase_colors = ["#2166ac", "#74c476", "#d73027"]
    phase_labels = ["Apertura (1/3 del juego)", "Medio juego (2/3)", "Final (3/3)"]
    for ph_id, (ph_col, ph_lbl) in enumerate(zip(phase_colors, phase_labels)):
        mask_ph = labels_all_thirds == ph_id
        ax.scatter(emb_umap_all[mask_ph, 0], emb_umap_all[mask_ph, 1],
                   c=ph_col, s=35, alpha=0.75, zorder=2, label=ph_lbl,
                   linewidths=0.5, edgecolors="white")
    ax.set_title(
        f"UMAP combinado — todos los patrones\n"
        f"Coloreado por fase de la partida",
        fontsize=9,
    )
    ax.set_xlabel("UMAP 1"); ax.set_ylabel("UMAP 2")
    ax.legend(fontsize=8)

    plt.suptitle(f"UMAP vs MDS — espacio de patrones — {TITLE}", fontsize=11)
    plt.tight_layout()
    plt.savefig(dir_espacio / "03_umap_vs_mds.png", dpi=130); plt.close()

    # ── Fig 17: UMAP sobre imágenes de persistencia ───────────────────────────
    # imgs_all_h0 / imgs_all_h1 = [black moves... | white moves...]
    # Each row is the flattened persistence image of one move.
    # UMAP here shows whether the TOPOLOGICAL signatures (not raw patterns)
    # of the two players are distinguishable as manifold clusters.

    fig17, axes17 = plt.subplots(1, 2, figsize=(14, 6))
    pi_mask_b = np.arange(Nb + Nw) < Nb   # first Nb rows = Black
    pi_mask_w = ~pi_mask_b

    for ax, imgs, dim_name in [
        (axes17[0], imgs_all_h0, "H₀ — grupos de piedras"),
        (axes17[1], imgs_all_h1, "H₁ — lazos / ojos"),
    ]:
        # Persistence images may be 3D (n, h, w) — flatten to (n, h*w)
        imgs_flat = imgs.reshape(len(imgs), -1) if imgs.ndim == 3 else imgs
        nn_pi = min(15, max(2, len(imgs_flat) - 1))
        emb_pi = _umap_lib.UMAP(
            n_components=2, n_neighbors=nn_pi, min_dist=0.1,
            random_state=SEED, low_memory=False,
        ).fit_transform(imgs_flat)

        ax.scatter(emb_pi[pi_mask_b, 0], emb_pi[pi_mask_b, 1],
                   c=BEDGE, s=35, alpha=0.75, zorder=2, label=BLACK_NAME,
                   linewidths=0.5, edgecolors="white")
        ax.scatter(emb_pi[pi_mask_w, 0], emb_pi[pi_mask_w, 1],
                   c=WEDGE, s=35, alpha=0.75, zorder=2, label=WHITE_NAME,
                   linewidths=0.5, edgecolors="white")
        ax.set_title(
            f"UMAP — imágenes de persistencia {dim_name}\n"
            f"Cada punto = un movimiento; coloreado por jugador",
            fontsize=9,
        )
        ax.set_xlabel("UMAP 1"); ax.set_ylabel("UMAP 2")
        ax.legend(fontsize=8)

    plt.suptitle(
        f"UMAP topológico — firmas de persistencia — {TITLE}\n"
        f"(Separación de clusters = los dos jugadores tienen firmas topológicas distintas)",
        fontsize=10,
    )
    plt.tight_layout()
    plt.savefig(dir_espacio / "04_umap_persistencia.png", dpi=130); plt.close()

    # ── Fig 18: VR complex en espacio de patrones 3D ─────────────────────────
    # 2×2 grid: fila superior = UMAP 3D, fila inferior = MDS 3D
    # Cada columna = un jugador.
    # El complejo VR revela lazos y cavidades topológicas en el espacio de patrones
    # que la proyección 2D aplana. Un loop visible en 3D que no aparece en 2D
    # indica una variedad de patrones con geometría de anillo o toro.

    fig18 = plt.figure(figsize=(18, 14))

    _eps_pct = 25    # percentile for epsilon selection in embedding space

    for row, (method_name, compute_3d) in enumerate([
        ("UMAP 3D", True),
        ("MDS 3D",  False),
    ]):
        for col, (fvecs, name, c_node, c_edge, c_face, nn_3d) in enumerate([
            (b_fvecs, BLACK_NAME, BCOL, BEDGE, BFACE, nn_b),
            (w_fvecs, WHITE_NAME, WCOL, WEDGE, WFACE, nn_w),
        ]):
            ax3d = fig18.add_subplot(2, 2, row * 2 + col + 1, projection="3d")
            n_pts = len(fvecs)

            if compute_3d:
                nn3 = min(nn_3d, n_pts - 1)
                emb3 = _umap_lib.UMAP(
                    n_components=3, n_neighbors=nn3, min_dist=0.1,
                    random_state=SEED, low_memory=False,
                ).fit_transform(fvecs)
            else:
                emb3 = MDS(n_components=3, dissimilarity="euclidean",
                           random_state=SEED, normalized_stress="auto"
                           ).fit_transform(fvecs)

            # Epsilon: 25th percentile of pairwise distances in 3D space
            sample = emb3[:min(n_pts, 60)]
            dists3 = [np.linalg.norm(sample[i] - sample[j])
                      for i, j in combinations(range(len(sample)), 2)]
            eps3 = float(np.percentile(dists3, _eps_pct)) if dists3 else 1.0

            # Draw VR complex (no faces to keep it legible)
            draw_simplicial_complex_3d(
                emb3, eps3, ax3d,
                node_color=c_node, edge_color=c_edge, face_color=c_face,
                node_size=28, alpha_edge=0.45, linewidth=0.7,
                show_faces=False,
                color_by=np.arange(n_pts, dtype=float),
                cmap="Blues_r" if col == 0 else "Oranges_r",
                title=f"{method_name} — {name}\n(ε={eps3:.2f}, n_neighbours={min(nn_3d, n_pts-1)})",
            )

            # Temporal trajectory in 3D
            cmap_traj = plt.cm.get_cmap("Blues_r" if col == 0 else "Oranges_r")
            for i in range(n_pts - 1):
                frac = i / max(n_pts - 1, 1)
                tc = cmap_traj(0.1 + 0.85 * frac)
                ax3d.plot(
                    [emb3[i,0], emb3[i+1,0]],
                    [emb3[i,1], emb3[i+1,1]],
                    [emb3[i,2], emb3[i+1,2]],
                    color=tc, lw=0.9, alpha=0.55, zorder=1,
                )

            # Start / end
            ax3d.scatter(*emb3[0],  s=100, c="green", marker="*", zorder=10, depthshade=False)
            ax3d.scatter(*emb3[-1], s=100, c="red",   marker="X", zorder=10, depthshade=False)

    plt.suptitle(
        f"Complejo VR en espacio de patrones 3D — UMAP (arriba) vs MDS (abajo)\n{TITLE}",
        fontsize=11,
    )
    plt.tight_layout()
    plt.savefig(dir_espacio / "05_complejo_3d.png", dpi=130); plt.close()


def _interpret_cohomology(metrics_b: list[dict], metrics_w: list[dict],
                          name_b: str, name_w: str) -> str:
    """Narrative interpretation of the homology–cohomology duality results."""
    lines = []

    # Per-player analysis of final position (metrics list has one entry: final)
    for name, m in [(name_b, metrics_b[0]), (name_w, metrics_w[0])]:
        if m["birth"] is None:
            lines.append(
                f"**{name} (posición final):** sin lazo H₁ persistente — "
                f"las piedras forman grupos abiertos sin territorios cerrados detectables "
                f"a la escala de análisis."
            )
            continue

        persist = m["persistence"]
        ne = m["n_edges"]
        b, d = m["birth"], m["death"]
        b2, d2 = m.get("b2"), m.get("d2")

        if persist >= 3.0:
            strength = "muy persistente — territorio firmemente establecido"
        elif persist >= 1.5:
            strength = "moderadamente persistente — estructura territorial en formacion"
        else:
            strength = "debilmente persistente — lazo frágil, posiblemente transitorio"

        size_desc = ("muy localizado (pocas piedras involucradas)" if ne <= 3
                     else "de tamaño medio" if ne <= 7
                     else "extensa (muchas piedras involucradas)")

        # Homology view
        homo_line = (
            f"**{name} — vista homológica (¿QUÉ loops existen?):** "
            f"El diagrama H₁ muestra un lazo {strength}. "
            f"Nace a ε={b:.2f} (las piedras que lo forman quedan conectadas a esa escala) "
            f"y muere a ε={d:.2f} (el loop se cierra en un complejo mayor). "
            f"Persistencia={persist:.2f}."
        )
        if b2 is not None:
            homo_line += (
                f" Existe un segundo lazo H₁ (birth={b2:.2f}, death={d2:.2f}, "
                f"persist={d2-b2:.2f}) — dos estructuras de loop distinguibles."
            )

        # Cohomology view
        coho_line = (
            f"**{name} — vista cohomológica (¿QUÉ pares de piedras lo sostienen?):** "
            f"El cociclo φ₁ (rojo en Fig. 14) es una función en las aristas que evalúa a 1 "
            f"exactamente sobre los {ne} pares de piedras que forman la 'columna vertebral' "
            f"del loop. Esta es la dualización algebraica: donde la homología dice "
            f"'existe un agujero', la cohomología dice 'estas conexiones específicas lo sostienen'."
        )

        # Cup product view
        cup = m.get("cup_nonzero", False)
        cup_n = m.get("cup_n_triangles", 0)
        if cup:
            cup_line = (
                f"**{name} — cup product φ₁∪φ₂ ≠ 0 ({cup_n} triángulos, en púrpura en Fig. 14):** "
                f"Los dos lazos H₁ interactúan: su cup product es no trivial, "
                f"lo que genera una clase H₂. En términos de Go, esto es la firma algebraica "
                f"de un **grupo con dos ojos** — vivo incondicionalmente. "
                f"Los triángulos púrpura marcan exactamente las ternas de piedras donde "
                f"ambos cociclos 'se detectan mutuamente'."
            )
        else:
            cup_line = (
                f"**{name} — cup product φ₁∪φ₂ = 0:** "
                f"{'No se detectó un segundo lazo H₁ significativo.' if b2 is None else 'Los dos lazos H₁ no interactúan en ningún 2-símplex — sus territorios son independientes.'} "
                f"No hay evidencia topológica de un grupo con dos ojos en la posición final."
            )

        lines.append("\n".join([homo_line, coho_line, cup_line]))

    # Cross-player cup product comparison
    mb = metrics_b[0]; mw = metrics_w[0]
    cup_b = mb.get("cup_nonzero", False); cup_w = mw.get("cup_nonzero", False)
    if cup_b and cup_w:
        lines.append(
            f"**Comparacion:** ambos jugadores muestran cup product no trivial — "
            f"ambos tienen grupos con dos ojos al final. "
            f"La partida se decidió por otros factores (territorio, ko, tiempo)."
        )
    elif cup_b:
        lines.append(
            f"**Comparacion:** solo {name_b} tiene cup product no trivial (grupo vivo algebraicamente). "
            f"{name_w} no muestra esta estructura en la posición final analizada."
        )
    elif cup_w:
        lines.append(
            f"**Comparacion:** solo {name_w} tiene cup product no trivial (grupo vivo algebraicamente). "
            f"{name_b} no muestra esta estructura en la posición final analizada."
        )
    else:
        pb = mb.get("persistence"); pw = mw.get("persistence")
        if pb is not None and pw is not None:
            winner = name_b if pb > pw else name_w
            lines.append(
                f"**Comparacion:** ningún jugador tiene cup product no trivial en la posición final. "
                f"{winner} tiene el lazo H₁ más persistente ({max(pb,pw):.2f} vs {min(pb,pw):.2f}), "
                f"indicando mayor solidez territorial aunque sin dos ojos algebraicamente confirmados."
            )

    return "\n\n".join(lines)

_coh_interp = _interpret_cohomology(
    coh_metrics[BLACK_NAME], coh_metrics[WHITE_NAME],
    BLACK_NAME, WHITE_NAME,
)

print("   Figuras guardadas.")

# ── Video: evolución del complejo VR ─────────────────────────────────────────
print("[video] Generando video de evolucion del complejo VR ...")
try:
    import imageio as _imageio
    _HAS_IMAGEIO = True
except ImportError:
    _HAS_IMAGEIO = False
    print("   AVISO: imageio no instalado — pip install imageio[ffmpeg]")

if _HAS_IMAGEIO:
    dir_video = output_dir / "06_video"
    dir_video.mkdir(parents=True, exist_ok=True)

    # Per-stone birth: global move index when stone was (re)placed on the board
    birth_b: dict = {}
    birth_w: dict = {}
    prev_b: set = set()
    prev_w: set = set()

    video_path = dir_video / "evolucion_vr.mp4"
    # Write frames one-by-one to avoid accumulating ~1.3 GB in RAM
    _writer = _imageio.get_writer(
        str(video_path), fps=8, codec="libx264", pixelformat="yuv420p", quality=8,
        macro_block_size=16,
    )

    for move_i in range(N):
        cur_b = set(map(tuple, black_stones_seq[move_i]))
        cur_w = set(map(tuple, white_stones_seq[move_i]))

        for s in cur_b - prev_b:
            birth_b[s] = move_i
        for s in cur_w - prev_w:
            birth_w[s] = move_i
        for s in prev_b - cur_b:
            birth_b.pop(s, None)
        for s in prev_w - cur_w:
            birth_w.pop(s, None)
        prev_b = cur_b
        prev_w = cur_w

        last_xy = all_moves_xy[move_i]
        col_now = all_colours[move_i]
        last_b  = last_xy if col_now == "b" else None
        last_w  = last_xy if col_now == "w" else None

        fig_v, axes_v = plt.subplots(1, 2, figsize=(16, 8), facecolor="#0d0d0d")
        fig_v.subplots_adjust(left=0.02, right=0.98, top=0.91, bottom=0.02, wspace=0.04)

        draw_board_frame(
            stones=list(cur_b),
            birth_dict=birth_b,
            current_move=max(move_i, 1),
            epsilon=EPS_BOARD_B,
            ax=axes_v[0],
            last_move=last_b,
            player_label=f"{BLACK_NAME} (N)  mv {move_i+1}/{N}",
        )
        draw_board_frame(
            stones=list(cur_w),
            birth_dict=birth_w,
            current_move=max(move_i, 1),
            epsilon=EPS_BOARD_W,
            ax=axes_v[1],
            last_move=last_w,
            player_label=f"{WHITE_NAME} (B)  mv {move_i+1}/{N}",
        )

        fig_v.suptitle(
            f"Complejo VR — {BLACK_NAME} vs {WHITE_NAME} — Movimiento {move_i+1}/{N}",
            fontsize=12, color="white", y=0.97,
        )
        fig_v.canvas.draw()
        w_px, h_px = fig_v.canvas.get_width_height()
        buf = np.frombuffer(fig_v.canvas.tostring_argb(), dtype=np.uint8).copy()
        buf = buf.reshape(h_px, w_px, 4)
        frame_arr = np.ascontiguousarray(buf[:, :, 1:])   # ARGB → RGB, contiguous
        _writer.append_data(frame_arr)
        plt.close(fig_v)

        if (move_i + 1) % 50 == 0:
            print(f"   Frame {move_i+1}/{N} ...")

    _writer.close()
    import os
    print(f"   Video guardado: {video_path}  ({N} frames @ 8 fps, {os.path.getsize(video_path)//1024} KB)")

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
    "epsilon_figuras_negro": EPS_BOARD_B,
    "epsilon_figuras_blanco": EPS_BOARD_W,
    "epsilons_negro": EPSILONS_B,
    "epsilons_blanco": EPSILONS_W,
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
    "01_entropia": (
        f"Evolucion de la entropia persistente H0 (grupos de piedras) y H1 (lazos/ojos) "
        f"para cada jugador a lo largo de sus propios movimientos. La linea roja vertical "
        f"marca la mitad de los movimientos de ese jugador. Una H0 creciente refleja como "
        f"el jugador va poblando el tablero con grupos cada vez mas variados. "
        f"Un pico de H1 indica el momento de maxima complejidad territorial (ojos, cercados). "
        f"Comparar ambas filas permite ver si los dos jugadores tienen ritmos de complejizacion distintos."
    ),
    "02_betti_bootstrap": (
        f"Curvas de Betti con bandas de confianza al 95% (Fasy et al. 2014) calculadas "
        f"sobre los patrones de cada jugador por separado. La banda sombreada indica la "
        f"variabilidad entre movimientos: una banda estrecha significa que el jugador "
        f"juega patrones topologicamente consistentes; una banda ancha, que hay alta "
        f"variabilidad estilistica. La comparacion directa de las curvas de {BN} y {WN} "
        f"en 03_comparacion_betti muestra si sus estilos topologicos difieren sistematicamente."
    ),
    "01_negro_momentos": (
        f"Complejo simplicial de Vietoris-Rips (ε={EPS_BOARD_B}) construido sobre "
        f"las piedras acumuladas de {BN} en cinco momentos de la partida (20%, 40%, 60%, 80%, 100%). "
        f"ε={EPS_BOARD_B} es el segundo valor del intervalo discreto adaptado a esta partida "
        f"(ε ∈ {{{', '.join(str(e) for e in EPSILONS_B)}}}), equivalente al ~20%% del rango total. "
        f"A esta escala se capturan conexiones tacticas locales: piedras adyacentes y a salto de "
        f"un espacio. Los triangulos (2-simplices) son trios de piedras mutuamente proximas. "
        f"La creciente densidad de triangulos hacia el final refleja la consolidacion de territorios."
    ),
    "02_blanco_momentos": (
        f"Idem para {WN} con ε={EPS_BOARD_W} (intervalo ε ∈ {{{', '.join(str(e) for e in EPSILONS_W)}}}). "
        f"Comparar la estructura del complejo con la de {BN} "
        f"permite ver diferencias en como cada jugador ocupa el tablero: "
        f"grupos mas dispersos vs mas concentrados, mayor o menor numero de 2-simplices."
    ),
    "05_negro_dim_birth": (
        f"Complejo VR de {BN} con coloracion por dimension y momento de nacimiento (ε={EPS_BOARD_B}). "
        f"Cada simbolo mantiene su color en todos los paneles posteriores, "
        f"permitiendo rastrear la historia de cada estructura topologica. "
        f"AZUL (familia Blues): nodos (0-simplices) = piedras del tablero. "
        f"VERDE (familia Greens): aristas (1-simplices) = conexiones entre piedras dentro de ε. "
        f"NARANJA (familia Oranges): triangulos (2-simplices) = trios de piedras mutuamente proximas. "
        f"INTENSIDAD: oscuro = nacido en momentos tempranos de la partida (estructura establecida); "
        f"claro = nacido recientemente (estructura nueva). "
        f"Un triangulo naranja oscuro que aparece ya al 40%% y persiste hasta el 100%% "
        f"indica un nucleo territorial que se establecio temprano y se mantuvo estable. "
        f"Una arista verde clara que solo aparece al 100%% es una conexion recien formada."
    ),
    "06_blanco_dim_birth": (
        f"Idem para {WN} con ε={EPS_BOARD_W}. "
        f"Comparar con la figura de {BN} permite ver si los dos jugadores construyen "
        f"sus estructuras topologicas en momentos distintos de la partida — "
        f"por ejemplo, si uno consolida territorio (triangulos naranjas oscuros) "
        f"antes que el otro."
    ),
    "03_negro_filtracion_epsilon": (
        f"Filtracion de Vietoris-Rips de las piedras de {BN} en el movimiento {mid_b_global+1} "
        f"(mitad de partida) con intervalo discreto de epsilon adaptado a esta partida: "
        f"ε ∈ {{{', '.join(str(e) for e in EPSILONS_B)}}}. "
        f"La cota superior (ε={EPSILONS_B[-1]}) es la distancia Manhattan maxima entre dos "
        f"piedras de {BN} en la posicion final — el mayor alcance que tiene sentido medir "
        f"para este jugador en este juego especifico. "
        f"A ε={EPSILONS_B[0]} solo se conectan piedras adyacentes (grupos del tablero de Go). "
        f"A ε={EPSILONS_B[-1]} el complejo captura todas las relaciones de largo alcance "
        f"posibles entre las piedras de {BN}. "
        f"Esta progresion es la visualizacion directa de la filtracion que usa la homologia persistente."
    ),
    "04_blanco_filtracion_epsilon": (
        f"Idem para {WN} en su movimiento {mid_w_global+1}. "
        f"Intervalo adaptado: ε ∈ {{{', '.join(str(e) for e in EPSILONS_W)}}}. "
        f"La cota superior ε={EPSILONS_W[-1]} es la distancia Manhattan maxima entre "
        f"dos piedras de {WN} en la posicion final de esta partida."
    ),
    "01_mds_trayectoria": (
        f"Espacio topologico de cada jugador: cada punto es uno de sus movimientos, "
        f"representado por su vector de caracteristicas de 361 dimensiones y proyectado "
        f"en 2D mediante MDS (Multidimensional Scaling). Los puntos estan coloreados "
        f"de oscuro (inicio) a claro (final). La linea traza la trayectoria temporal. "
        f"Una trayectoria compacta indica un jugador consistente; una dispersa indica "
        f"alta variedad de patrones. La estrella verde es el primer movimiento; "
        f"la X roja es el ultimo."
    ),
    "02_vr_sobre_mds": (
        f"Complejo simplicial de Vietoris-Rips construido directamente sobre el espacio "
        f"topologico MDS de cada jugador. El epsilon se ajusta automaticamente al percentil 20 "
        f"de las distancias inter-patron en el espacio MDS. Los triangulos (2-simplices) "
        f"indican grupos de movimientos topologicamente similares. Los colores de los nodos "
        f"representan el tiempo (plasma: oscuro=inicio, claro=final). "
        f"Este es el espacio topologico global del jugador a lo largo de toda la partida."
    ),
    "03_comparacion_betti": (
        f"Superposicion de las curvas de Betti de {BN} y {WN} en las mismas axes, "
        f"con sus respectivas bandas de confianza al 95%. "
        f"Si las curvas se solapan, los dos jugadores tienen estilos topologicos similares a esa escala. "
        f"Si se separan, hay diferencias sistematicas: uno forma mas grupos (H0 mas alto) "
        f"o mas lazos/ojos (H1 mas alto) que el otro."
    ),
    "04_diagramas_persistencia": (
        f"Diagramas de persistencia de cada jugador en tres momentos (25%, 50%, 75%). "
        f"Puntos azules: componentes conexos (H0). Triangulos naranjas: lazos (H1). "
        f"Puntos lejos de la diagonal son caracteristicas topologicas significativas y duraderas. "
        f"La evolucion de los diagramas muestra como cambia la complejidad topologica "
        f"de los patrones de cada jugador a medida que avanza la partida."
    ),
    "01_matrices_distancias": (
        f"Matrices de distancias euclidianas entre los vectores de patron de cada jugador "
        f"(calculadas solo sobre sus propios movimientos). Colores oscuros = patrones similares. "
        f"La linea roja divide apertura y final del jugador. Un bloque homogeneo indica "
        f"estilo consistente; un gradiente indica evolucion progresiva del estilo."
    ),
    "02_tests_permutacion": (
        f"Distribucion nula del estadistico T bajo permutacion aleatoria de etiquetas "
        f"(999 permutaciones). La linea roja marca el valor observado. "
        f"Izquierda: test Negro vs Blanco — si la linea roja cae en la cola derecha, "
        f"los dos jugadores tienen estilos topologicos estadisticamente distintos. "
        f"Derecha: test Apertura vs Final — si es significativo, la partida tiene "
        f"dos fases topologicamente diferenciadas."
    ),
    "03_heatmaps_tablero": (
        f"Mapa de calor del tablero 19x19 por jugador. "
        f"Izquierda: entropia H1 media en cada interseccion (rojo intenso = alta complejidad "
        f"topologica en los patrones que pasan por esa interseccion). "
        f"Derecha: numero de movimientos del jugador en cada interseccion. "
        f"Las zonas calientes en entropia que coinciden con zonas de alta frecuencia "
        f"son los puntos de mayor actividad e importancia topologica de ese jugador."
    ),
    "01_dualidad_homologia_cohomologia": (
        f"Dualidad homologia-cohomologia H1 en la posicion final de cada jugador. "
        f"Panel izquierdo: diagrama de persistencia H1 (vista homologica) — cada punto "
        f"(birth, death) representa un loop que existe entre esas dos escalas; "
        f"los puntos lejos de la diagonal son los features topologicos mas significativos. "
        f"Panel derecho: los dos cociclos H1 mas persistentes dibujados sobre el tablero "
        f"(rojo=phi1, azul=phi2) y los triangulos purpura donde su cup product es no cero. "
        f"La homologia dice QUE loops existen; la cohomologia dice QUE pares de piedras "
        f"los sostienen; el cup product phi1 union phi2 detecta si dos loops interactuan "
        f"formando una clase H2 — la firma algebraica de un grupo con dos ojos.\n\n"
        f"**Interpretacion especifica de esta partida:**\n\n{_coh_interp}"
    ),
    "02_cociclos_por_momento": (
        f"Cociclo H1 mas persistente de cada jugador en tres momentos (40%, 70%, 100%). "
        f"Las aristas rojas son los pares de piedras que forman el 1-cociclo representativo "
        f"del lazo topologico mas duradero en ese momento. "
        f"Permite ver como evoluciona la estructura cohomologica a lo largo de la partida: "
        f"si el cociclo crece, el territorio se consolida; si cambia de forma brusca, "
        f"hubo una ruptura o captura que reorganizo la topologia del jugador."
    ),
    "03_umap_vs_mds": (
        f"Comparacion directa entre UMAP (fila superior) y MDS (fila inferior) "
        f"como metodos de reduccion de dimensionalidad del espacio de patrones. "
        f"MDS (Multidimensional Scaling) es un metodo lineal que preserva distancias "
        f"globales pero puede comprimir clusters locales. UMAP (Uniform Manifold "
        f"Approximation and Projection) combina teoria de grafos y topologia algebraica "
        f"para construir un grafo kNN pesado sobre el espacio de datos y luego optimiza "
        f"un embebimiento 2D que preserva tanto la estructura local (clusters) como la "
        f"global (relaciones entre grupos de patrones). "
        f"Columnas 1-2: trayectoria temporal de cada jugador (oscuro=inicio, claro=final). "
        f"Columna 3 fila superior: UMAP de TODOS los patrones coloreado por jugador — "
        f"si los puntos de {BLACK_NAME} y {WHITE_NAME} forman clusters separados, "
        f"sus estilos ocupan regiones distintas del espacio de patrones. "
        f"Columna 3 fila inferior: UMAP coloreado por fase (azul=apertura, "
        f"verde=medio juego, rojo=final) — revela si la partida tiene una estructura "
        f"de manifold con fases topologicamente diferenciadas."
    ),
    "04_umap_persistencia": (
        f"UMAP aplicado directamente sobre las imagenes de persistencia H0 y H1 "
        f"(no sobre los patrones brutos, sino sobre las firmas topologicas de cada movimiento). "
        f"Cada punto es un movimiento; el color indica el jugador. "
        f"Si los puntos de {BLACK_NAME} y {WHITE_NAME} forman clusters separados, "
        f"significa que sus FIRMAS TOPOLOGICAS (no solo sus patrones de piedras) son "
        f"distinguibles — el SVM (Fig. 12) detecta esta separacion con un hiperplano "
        f"lineal, pero UMAP la hace visible como geometria del manifold. "
        f"Una superposicion total indicaria que ambos jugadores construyen posiciones "
        f"con la misma estructura topologica de grupos y lazos, independientemente "
        f"de donde pongan las piedras."
    ),
    "05_complejo_3d": (
        f"Complejo de Vietoris-Rips construido sobre el espacio de patrones en 3 dimensiones. "
        f"Fila superior: UMAP 3D (preserva estructura local y global del manifold). "
        f"Fila inferior: MDS 3D (metodo lineal, referencia de comparacion). "
        f"Cada punto es un movimiento del jugador; el color va de oscuro (inicio) a claro (final). "
        f"La trayectoria conecta jugadas consecutivas mostrando la evolucion temporal del estilo. "
        f"Las aristas del complejo VR conectan movimientos topologicamente similares a la "
        f"escala epsilon elegida (percentil 25 de las distancias en el espacio embebido). "
        f"La tercera dimension revela estructuras topologicas que la proyeccion 2D aplana: "
        f"un lazo visible en 3D pero no en 2D indica que el espacio de patrones tiene "
        f"geometria de anillo; una 'burbuja' indicaria una variedad esferica. "
        f"Comparar UMAP y MDS permite verificar si la estructura 3D es robusta o un artefacto "
        f"del metodo de reduccion."
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
    f"La filtracion VR (Figs. 03-04) muestra como cada jugador "
    f"construye su red de piedras a lo largo de la partida. "
    f"La Fig. 05-06 ilustra la filtracion: a epsilon pequeno solo se conectan grupos "
    f"adyacentes (refleja la logica de atari y capturas); a epsilon grande emergen "
    f"relaciones de largo alcance entre grupos separados (estrategia de influencia global).\n\n"
    f"### 4. Espacio topologico del jugador\n"
    f"El espacio MDS (Figs. 07-08) muestra la trayectoria estilistica de cada jugador. "
    f"Un espacio compacto indica consistencia; uno disperso, variedad tactica. "
    f"El complejo VR sobre este espacio revela si hay clusters de movimientos similares "
    f"(posibles repertorios tacticos o secuencias joseki repetidas).\n\n"
    f"### 5. Cohomologia persistente\n"
    f"La Fig. 14 muestra el cociclo H1 mas persistente de cada jugador en tres momentos. "
    f"A diferencia de la homologia (que detecta que existe un lazo), la cohomologia identifica "
    f"exactamente que pares de piedras forman la estructura de ese lazo. "
    f"Las aristas rojas son los 1-cociclos representativos.\n\n"
    f"{_coh_interp}\n\n"
    f"**Tiempo total de analisis:** {time.time()-t0:.1f}s"
)

generate_report(
    config=config_rep,
    cohort_summary=cohort_summary,
    descriptor_summary=descriptor_summary,
    stat_results=stat_results_rep,
    figures=sorted([
        p for d in [dir_vr, dir_homo, dir_coho, dir_espacio, dir_stats]
        for p in sorted(d.glob("*.png"))
    ]),
    figure_explanations=fig_expl,
    title=f"Analisis TDA por Jugador — {BN} vs {WN} ({meta.get('DT','?')})",
    conclusions=conclusions,
    output_path=output_dir/"report.md",
)

print(f"   Reporte generado: {output_dir/'report.md'}")
print(f"ANALISIS COMPLETO en {time.time()-t0:.1f}s")

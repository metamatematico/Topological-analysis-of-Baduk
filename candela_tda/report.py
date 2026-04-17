"""
Fase 7 — Markdown report generator.

Produces a report with:
- Configuration
- Cohort summary
- Topological descriptors with narrative interpretation
- Statistical results with narrative interpretation
- Figure references with per-figure explanations
- Conclusions section
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

_OUTPUT_DIR = Path(__file__).parent.parent.parent / "outputs" / "tda"


def _fmt(value: Any, decimals: int = 4) -> str:
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.{decimals}f}"
    return str(value)


def _pval_label(p: float) -> str:
    if p < 0.001:
        return "**p < 0.001** (muy significativo)"
    if p < 0.01:
        return f"**p = {p:.3f}** (significativo)"
    if p < 0.05:
        return f"**p = {p:.3f}** (marginalmente significativo)"
    return f"p = {p:.3f} (no significativo)"


def _silhouette_label(s: float) -> str:
    if s > 0.7:
        return "estructura de cluster muy clara"
    if s > 0.5:
        return "estructura de cluster razonable"
    if s > 0.25:
        return "estructura debil pero existente"
    return "sin estructura de cluster clara"


def generate_report(
    config: dict,
    cohort_summary: dict,
    descriptor_summary: dict,
    stat_results: dict,
    figures: list[Path],
    figure_explanations: dict[str, str] | None = None,
    title: str = "Candela TDA Report",
    conclusions: str | None = None,
    output_path: Path | None = None,
) -> Path:
    """Generate a Markdown report with narrative interpretations.

    Parameters
    ----------
    config:
        Configuration dict.
    cohort_summary:
        Dict with n_patterns, n_cohort_a, n_cohort_b, etc.
    descriptor_summary:
        Dict[dim_key, Dict[descriptor, value]].
    stat_results:
        Dict with permutation_test, clustering_*, classification results.
    figures:
        List of paths to PNG/SVG files.
    figure_explanations:
        Dict mapping figure filename (stem or full name) to an explanation
        string that will appear directly below the figure in the report.
    title:
        Report title.
    conclusions:
        Optional free-text conclusions section.
    output_path:
        Defaults to outputs/tda/report.md.

    Returns
    -------
    path : Path to the written report.
    """
    if output_path is None:
        output_path = _OUTPUT_DIR / "report.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure_explanations = figure_explanations or {}

    L: list[str] = []
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Header ────────────────────────────────────────────────────────────────
    L += [f"# {title}", "", f"**Generado:** {ts}", "", "---", ""]

    # ── Configuration ─────────────────────────────────────────────────────────
    L += [
        "## Configuracion",
        "",
        "```json",
        json.dumps(config, indent=2, default=str),
        "```",
        "",
        "---",
        "",
    ]

    # ── Cohort summary ────────────────────────────────────────────────────────
    L += ["## Resumen de la cohorte", ""]
    L += ["| Parametro | Valor |", "|-----------|-------|"]
    for k, v in cohort_summary.items():
        L.append(f"| {k} | {_fmt(v)} |")
    L += ["", "---", ""]

    # ── Topological descriptors with interpretation ───────────────────────────
    L += ["## Descriptores topologicos", ""]

    for dim_key, dim_data in descriptor_summary.items():
        L.append(f"### {dim_key.upper()}")
        L.append("")
        L += ["| Descriptor | Valor |", "|------------|-------|"]
        for k, v in dim_data.items():
            L.append(f"| {k} | {_fmt(v)} |")
        L.append("")

        # Auto-generate interpretation for common keys
        interp = _interpret_descriptor(dim_key, dim_data)
        if interp:
            L += [f"> {interp}", ""]

    L += ["---", ""]

    # ── Statistical results with interpretation ───────────────────────────────
    L += ["## Resultados estadisticos", ""]

    if "permutation_test" in stat_results:
        pt = stat_results["permutation_test"]
        p = float(pt.get("p_value", 1.0))
        T = float(pt.get("statistic", 0.0))
        n_perm = pt.get("n_permutations", "?")
        label = pt.get("label", "")
        L += [
            f"### Test de permutacion{' — ' + label if label else ''}",
            "",
            f"| Estadistico T | {_fmt(T)} |",
            "|---------------|------|",
            f"| p-valor | {_fmt(p)} |",
            f"| Permutaciones | {n_perm} |",
            "",
            _interpret_permtest(T, p, label),
            "",
        ]

    if "permutation_tests" in stat_results:
        for entry in stat_results["permutation_tests"]:
            p = float(entry.get("p_value", 1.0))
            T = float(entry.get("statistic", 0.0))
            label = entry.get("label", "")
            n_perm = entry.get("n_permutations", "?")
            L += [
                f"### Test de permutacion — {label}",
                "",
                f"| Estadistico T | {_fmt(T)} |",
                "|---------------|------|",
                f"| p-valor | {_fmt(p)} |",
                f"| Permutaciones | {n_perm} |",
                "",
                _interpret_permtest(T, p, label),
                "",
            ]

    if "clustering_agglomerative" in stat_results:
        cl = stat_results["clustering_agglomerative"]
        sil = float(cl.get("silhouette", float("nan")))
        coph = float(cl.get("cophenetic", float("nan")))
        k = cl.get("n_clusters", "?")
        L += [
            f"### Clustering aglomerativo (k={k})",
            "",
            f"| Silhouette | {_fmt(sil)} |",
            "|------------|------|",
            f"| Cof. Cof. Cofenotico | {_fmt(coph)} |",
            f"| n_clusters | {k} |",
            "",
            _interpret_clustering(sil, coph, k),
            "",
        ]

    if "clustering_agglomeratives" in stat_results:
        for cl in stat_results["clustering_agglomeratives"]:
            sil = float(cl.get("silhouette", float("nan")))
            coph = float(cl.get("cophenetic", float("nan")))
            k = cl.get("n_clusters", "?")
            L += [
                f"### Clustering aglomerativo (k={k})",
                "",
                f"| Silhouette | {_fmt(sil)} |",
                "|------------|------|",
                f"| Coef. Cofenotico | {_fmt(coph)} |",
                "",
                _interpret_clustering(sil, coph, k),
                "",
            ]

    if "clustering_dbscan" in stat_results:
        db = stat_results["clustering_dbscan"]
        k = db.get("n_clusters", 0)
        nf = float(db.get("noise_fraction", 0.0))
        sil = float(db.get("silhouette", float("nan")))
        L += [
            "### DBSCAN",
            "",
            f"| Clusters encontrados | {k} |",
            "|----------------------|------|",
            f"| Fraccion de ruido | {_fmt(nf)} |",
            f"| Silhouette | {_fmt(sil)} |",
            "",
            _interpret_dbscan(k, nf, sil),
            "",
        ]

    if "bootstrap_bands" in stat_results:
        bb = stat_results["bootstrap_bands"]
        c_alpha = float(bb.get("c_alpha", float("nan")))
        alpha = float(bb.get("alpha", 0.05))
        L += [
            "### Bandas de confianza bootstrap (Fasy et al. 2014)",
            "",
            f"| Valor critico c_alpha | {_fmt(c_alpha)} |",
            "|------------------------|------|",
            f"| Nivel de significancia | {1-alpha:.0%} |",
            "",
            (f"La curva de Betti media cae dentro de una banda de confianza del {1-alpha:.0%} "
             f"con valor critico c_alpha={c_alpha:.3f}. Un c_alpha bajo indica poca variabilidad "
             f"entre los diagramas de la cohorte; uno alto indica diversidad topologica elevada."),
            "",
        ]

    if "classification" in stat_results:
        cf = stat_results["classification"]
        acc = float(cf.get("mean_accuracy", float("nan")))
        std = float(cf.get("std_accuracy", float("nan")))
        f1 = float(cf.get("mean_f1_macro", float("nan")))
        clf = cf.get("classifier", "SVM")
        label = cf.get("label", "")
        L += [
            f"### Clasificador {clf.upper()}{' — ' + label if label else ''}",
            "",
            f"| Accuracy media | {_fmt(acc)} +/- {_fmt(std)} |",
            "|----------------|------|",
            f"| F1 macro | {_fmt(f1)} |",
            "",
            _interpret_classifier(acc, std, f1, clf, label),
            "",
        ]

    if "classifications" in stat_results:
        for cf in stat_results["classifications"]:
            acc = float(cf.get("mean_accuracy", float("nan")))
            std = float(cf.get("std_accuracy", float("nan")))
            f1 = float(cf.get("mean_f1_macro", float("nan")))
            clf = cf.get("classifier", "SVM")
            label = cf.get("label", "")
            L += [
                f"### Clasificador {clf.upper()}{' — ' + label if label else ''}",
                "",
                f"| Accuracy media | {_fmt(acc)} +/- {_fmt(std)} |",
                "|----------------|------|",
                f"| F1 macro | {_fmt(f1)} |",
                "",
                _interpret_classifier(acc, std, f1, clf, label),
                "",
            ]

    L += ["---", ""]

    # ── Figures with explanations ─────────────────────────────────────────────
    if figures:
        L += ["## Figuras", ""]
        for fig in figures:
            fig_path = Path(fig)
            # Use relative path from output file's directory when possible
            try:
                rel = fig_path.resolve().relative_to(output_path.parent.resolve())
                display_path = rel.as_posix()
            except ValueError:
                display_path = fig_path.as_posix()

            L.append(f"### {fig_path.stem.replace('_', ' ').title()}")
            L.append("")
            L.append(f"![{fig_path.stem}]({display_path})")
            L.append("")

            # Look for explanation by stem or full name
            explanation = (
                figure_explanations.get(fig_path.stem)
                or figure_explanations.get(fig_path.name)
                or figure_explanations.get(str(fig_path))
            )
            if explanation:
                L.append(f"**Interpretacion:** {explanation}")
                L.append("")

    # ── Conclusions ───────────────────────────────────────────────────────────
    if conclusions:
        L += ["---", "", "## Conclusiones", "", conclusions, ""]

    content = "\n".join(L) + "\n"
    output_path.write_text(content, encoding="utf-8")
    return output_path


# ── Narrative interpretation helpers ──────────────────────────────────────────

def _interpret_descriptor(dim_key: str, data: dict) -> str:
    k = dim_key.lower()
    entropy = data.get("mean_entropy", data.get("entropy"))
    n_bars  = data.get("mean_n_bars", data.get("n_bars"))

    parts = []
    if entropy is not None:
        e = float(entropy)
        if "h0" in k:
            if e > 3.0:
                parts.append(
                    f"La entropia persistente H0 media ({e:.3f}) es alta, "
                    "lo que indica que los patrones contienen muchos grupos de piedras "
                    "que se van fusionando gradualmente al aumentar la escala de filtracion."
                )
            elif e > 1.5:
                parts.append(
                    f"La entropia persistente H0 ({e:.3f}) es moderada: "
                    "hay varios componentes conexos con tiempos de vida variados."
                )
            else:
                parts.append(
                    f"La entropia H0 baja ({e:.3f}) sugiere pocos grupos de piedras "
                    "con poca variabilidad en sus tiempos de vida."
                )
        elif "h1" in k:
            if e > 2.0:
                parts.append(
                    f"La entropia H1 ({e:.3f}) es significativa: los patrones contienen "
                    "lazos topologicos genuinos (ojos, cercados) con duraciones variadas. "
                    "Esto refleja complejidad estructural en las formaciones."
                )
            elif e > 0.5:
                parts.append(
                    f"La entropia H1 ({e:.3f}) es moderada: se detectan algunos lazos "
                    "topologicos, pero no dominan la estructura del patron."
                )
            else:
                parts.append(
                    f"La entropia H1 ({e:.3f}) es baja: los patrones contienen pocos "
                    "lazos topologicos, lo que indica formaciones abiertas o dispersas."
                )

    if n_bars is not None:
        parts.append(f"En promedio hay {float(n_bars):.1f} barras finitas por diagrama.")

    return " ".join(parts)


def _interpret_permtest(T: float, p: float, label: str) -> str:
    plabel = _pval_label(p)
    direction = "mayor" if T > 0 else "menor"
    if p < 0.05:
        return (
            f"El test de permutacion ({label}) resulta {plabel}. "
            f"El estadistico T={T:.4f} indica que la distancia media entre los dos grupos "
            f"es {direction} que la esperada bajo la hipotesis nula. "
            f"Esto significa que las dos cohortes de patrones tienen distribuciones "
            f"topologicas **estadisticamente diferentes**."
        )
    else:
        return (
            f"El test de permutacion ({label}) no es significativo ({plabel}). "
            f"No hay evidencia suficiente para rechazar que ambas cohortes "
            f"provienen de la misma distribucion topologica."
        )


def _interpret_clustering(sil: float, coph: float, k) -> str:
    sil_desc = _silhouette_label(sil)
    coph_desc = "muy buena" if coph > 0.8 else ("buena" if coph > 0.6 else "moderada")
    return (
        f"El coeficiente de silueta ({sil:.3f}) indica {sil_desc} con k={k} clusters. "
        f"El coeficiente cofenotico ({coph:.3f}) es {coph_desc}: "
        f"{'el dendrograma representa fielmente las distancias originales' if coph > 0.8 else 'el dendrograma aproxima razonablemente las distancias originales'}. "
        f"{'Los clusters identificados tienen una interpretacion geometrica clara.' if sil > 0.4 else 'Los clusters son difusos; interpretar con cautela.'}"
    )


def _interpret_dbscan(k: int, nf: float, sil: float) -> str:
    if k == 0:
        return (
            "DBSCAN no encontro ningun cluster (todos los puntos son ruido). "
            "El parametro eps puede ser demasiado pequeño para la escala de las distancias."
        )
    noise_desc = f"{nf:.0%} de puntos clasificados como ruido."
    sil_desc = _silhouette_label(sil) if not np.isnan(sil) else "no calculable (un solo cluster o todo ruido)"
    return (
        f"DBSCAN detecto {k} cluster(s) con {noise_desc} "
        f"La calidad de los clusters: {sil_desc}."
    )


def _interpret_classifier(acc: float, std: float, f1: float, clf: str, label: str) -> str:
    chance = 0.5  # binary default
    if np.isnan(acc):
        return "El clasificador no pudo ejecutarse (posiblemente imagenes de persistencia vacias)."
    margin = acc - chance
    if margin > 0.15:
        quality = "claramente mejor que el azar"
    elif margin > 0.05:
        quality = "moderadamente mejor que el azar"
    else:
        quality = "comparable al azar"

    return (
        f"El clasificador {clf.upper()} ({label}) obtiene una accuracy de {acc:.3f} +/- {std:.3f}, "
        f"{quality} (referencia azar ~{chance:.2f}). "
        f"El F1 macro de {f1:.3f} "
        + ("indica que el clasificador discrimina entre clases de forma equilibrada."
           if f1 > 0.5 else
           "es bajo, lo que sugiere que las imagenes de persistencia H0 no codifican "
           "suficiente informacion discriminante para esta tarea.")
    )

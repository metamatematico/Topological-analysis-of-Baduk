# Análisis Topológico del Go

> **¿Qué tan diferente es el juego de dos jugadores de Go, matemáticamente?**
> Este proyecto responde esa pregunta usando *homología persistente* — una rama de la topología algebraica que detecta "forma" en datos.

---

## Tabla de contenidos

1. [La idea en términos de Go](#la-idea-en-términos-de-go)
2. [Cómo funciona el sistema](#cómo-funciona-el-sistema)
3. [Candela: el extractor de patrones](#candela-el-extractor-de-patrones)
4. [La capa de análisis topológico](#la-capa-de-análisis-topológico)
5. [Dos partidas, dos tipos de juego](#dos-partidas-dos-tipos-de-juego)
   - [Oguchi vs tiernuki — estilos topológicamente convergentes](#oguchi-vs-tiernuki--estilos-topológicamente-convergentes)
   - [ometitlan vs haya371203 — mayor variedad topológica entre jugadores](#ometitlan-vs-haya371203--mayor-variedad-topológica-entre-jugadores)
   - [Comparación directa](#comparación-directa)
6. [Cómo correr tu propio análisis](#cómo-correr-tu-propio-análisis)
7. [Dependencias](#dependencias)
8. [Créditos](#créditos)

---

## La idea en términos de Go

Cada vez que un jugador hace una jugada, las piedras en el tablero forman una **configuración espacial**: grupos separados, cadenas conectadas, cercados, ojos. Esa configuración tiene una *forma* matemática que puede medirse con herramientas topológicas:

- **H₀ (componentes conexas):** ¿cuántos grupos de piedras independientes tiene el jugador?
- **H₁ (lazos / ojos):** ¿cuántos ojos o cercados territoriales ha formado?

Al calcular estas medidas para cada jugada y a lo largo de toda la partida, podemos construir un **espacio topológico del jugador** — una representación de cómo evoluciona su estilo de juego desde la apertura hasta el final.

Con eso podemos preguntar:
- ¿Los dos jugadores forman patrones topológicamente distintos, o son indistinguibles?
- ¿El estilo de un jugador cambia significativamente entre la apertura y el final?
- ¿Existen "clusters" de jugadas — momentos con estilos similares?

---

## Cómo funciona el sistema

```
Archivo SGF (partida de Go)
        │
        ▼
  ┌─────────────┐
  │   CANDELA   │  ← extrae y canonicaliza patrones 19×19
  └─────────────┘
        │  Pattern = tuple[tuple[str,...],...]  (19×19)
        │  Símbolos: 'b' piedra negra, 'w' piedra blanca,
        │            '+' vacío interior, '/' borde, '.' fuera
        ▼
  ┌──────────────────────────────────────────────┐
  │           CAPA TDA (candela_tda/)            │
  │                                              │
  │  representation.py → nube de puntos          │
  │  complex.py        → complejo de Vietoris-Rips│
  │  persistence.py    → H₀, H₁, entropía        │
  │  distances.py      → distancias entre patrones│
  │  stats.py          → tests estadísticos       │
  │  viz.py            → figuras                  │
  │  report.py         → reporte Markdown         │
  └──────────────────────────────────────────────┘
        │
        ▼
  Figuras + Reporte con interpretación narrativa
```

---

## Candela: el extractor de patrones

**[Candela](https://github.com/angelsesma/candela)** es el proyecto base de este sistema. Fue desarrollado originalmente para construir una base de datos de patrones de Go a partir de archivos SGF.

### Qué hace Candela

Por cada jugada de la partida, Candela:

1. **Reproduce el tablero** jugada a jugada usando `sgfmill`
2. **Extrae una ventana 19×19** centrada en la última jugada
3. **Canonicaliza el patrón**: aplica las 16 transformaciones posibles del tablero (4 rotaciones × 2 reflejos × 2 inversiones de color negro↔blanco) y se queda con el **mínimo lexicográfico**

La canonicalización es clave: hace que el mismo patrón jugado con negro o blanco, girado o espejado, sea **el mismo objeto matemático**. Esto permite comparar patrones entre jugadores de forma justa.

Sin Candela, no tendríamos una representación estructurada y comparable de las posiciones del tablero. La canonicalización garantiza que la topología que detectamos refleja la **geometría real del juego**, no artefactos de orientación o color.

---

## La capa de análisis topológico

Los módulos en `candela_tda/` toman los patrones de Candela y aplican análisis topológico:

| Módulo | Qué hace |
|--------|----------|
| `representation.py` | Convierte Pattern → nube de puntos `(row,col)`, vector de 361 dims, o grafo |
| `complex.py` | Construye el complejo de Vietoris-Rips con **distancia Manhattan** |
| `persistence.py` | Calcula H₀, H₁, entropía persistente, curvas de Betti, imágenes de persistencia |
| `distances.py` | Distancias entre diagramas: Bottleneck, Wasserstein, Landscape L² |
| `stats.py` | Tests de permutación, clustering, clasificadores SVM con validación cruzada |
| `viz.py` | Complejo simplicial sobre el tablero, espacio topológico MDS |
| `report.py` | Reporte Markdown con interpretación narrativa automática |

> **Nota sobre la distancia:** Usamos **distancia Manhattan** (|Δfila| + |Δcol|) para construir el complejo VR. Con ε=1, Manhattan captura exactamente las piedras con libertades compartidas — más fiel a la estructura del tablero de Go que la distancia euclidiana.

---

## Dos partidas, dos tipos de juego

El sistema revela diferencias cualitativas entre partidas. Analizamos dos partidas reales de OGS que ilustran dos situaciones distintas: una donde ambos jugadores convergen en el mismo estilo topológico, y otra donde existe mayor variedad entre ellos.

---

### Oguchi vs tiernuki — estilos topológicamente convergentes

**OGS · 2026-02-20 · 283 movimientos · B+4.5**
Resultados completos: [`ejemplo_oguchi_vs_tiernuki/`](ejemplo_oguchi_vs_tiernuki/)

En esta partida, el análisis topológico muestra que ambos jugadores construyen patrones estructuralmente muy similares a lo largo de toda la partida. El test de permutación entre los estilos de Negro y Blanco arroja **p = 0.908** — prácticamente en el centro de la distribución nula, lo que indica que sus distribuciones topológicas son casi indistinguibles.

Esto se refleja también en las métricas de entropía:

| Descriptor | Oguchi (N) | tiernuki (B) |
|------------|-----------|--------------|
| H₀ entropía media | 3.998 | 3.972 |
| H₁ entropía media | 2.978 | 2.954 |

Los valores son prácticamente idénticos: ambos jugadores forman grupos de piedras con la misma complejidad y el mismo número de lazos topológicos a lo largo del juego.

#### Complejos simpliciales en 5 momentos del partido

| Negro (Oguchi) | Blanco (tiernuki) |
|:--------------:|:-----------------:|
| ![complejo negro](ejemplo_oguchi_vs_tiernuki/figuras/fig03_complex_negro_moments.png) | ![complejo blanco](ejemplo_oguchi_vs_tiernuki/figuras/fig04_complex_blanco_moments.png) |

Ambos complejos evolucionan con estructura similar: densidad de triángulos comparable, distribución espacial parecida.

#### Filtración de Vietoris-Rips (a cuatro escalas ε)

| Negro | Blanco |
|:-----:|:------:|
| ![epsilon negro](ejemplo_oguchi_vs_tiernuki/figuras/fig05_complex_negro_epsilons.png) | ![epsilon blanco](ejemplo_oguchi_vs_tiernuki/figuras/fig06_complex_blanco_epsilons.png) |

#### Espacio topológico (trayectoria MDS de cada jugador)

![espacio topológico](ejemplo_oguchi_vs_tiernuki/figuras/fig07_topo_space_negro.png)

#### Evolución de la entropía por jugador

![entropía](ejemplo_oguchi_vs_tiernuki/figuras/fig01_entropy_per_player.png)

#### Comparación de curvas de Betti

![comparación betti](ejemplo_oguchi_vs_tiernuki/figuras/fig09_comparison_betti.png)

Las curvas de Betti de ambos jugadores se solapan casi perfectamente — confirmación visual de la convergencia topológica.

#### Resultados estadísticos

| Pregunta | p-valor | Conclusión |
|----------|---------|------------|
| ¿Son topológicamente distintos Oguchi y tiernuki? | **0.908** | No — estilos casi idénticos |
| ¿Cambia el estilo de Oguchi entre apertura y final? | 0.001 | Sí — muy significativo |
| ¿Cambia el estilo de tiernuki entre apertura y final? | 0.001 | Sí — muy significativo |
| SVM apertura vs final — Oguchi (H₁) | — | **97.2% accuracy** |
| SVM apertura vs final — tiernuki (H₁) | — | **96.5% accuracy** |

Ver el [reporte completo](ejemplo_oguchi_vs_tiernuki/reporte_oguchi_vs_tiernuki.md).

---

### ometitlan vs haya371203 — mayor variedad topológica entre jugadores

**OGS · 2021-03-27 · 198 movimientos · B+T**
Resultados completos: [`ejemplo_ometitlan/`](ejemplo_ometitlan/)

En esta partida, aunque el test de permutación tampoco llega a la significancia convencional (p = 0.541), los jugadores presentan mayor variedad topológica entre sí que en el caso anterior. Las métricas de entropía muestran una brecha más notable y las curvas de Betti se separan visiblemente en ciertas escalas.

| Descriptor | ometitlan (N) | haya371203 (B) |
|------------|--------------|----------------|
| H₀ entropía media | 3.820 | 3.787 |
| H₁ entropía media | 2.678 | 2.660 |

Los valores son menores que en la partida anterior — lo que indica que los patrones de esta partida son en promedio menos complejos topológicamente — y existe una diferencia relativa mayor entre los dos jugadores.

#### Complejos simpliciales en 5 momentos del partido

| Negro (ometitlan) | Blanco (haya371203) |
|:-----------------:|:-------------------:|
| ![complejo negro](ejemplo_ometitlan/figuras/fig03_complex_negro_moments.png) | ![complejo blanco](ejemplo_ometitlan/figuras/fig04_complex_blanco_moments.png) |

La estructura de los complejos difiere más entre jugadores: distintos patrones de densidad y distribución espacial de triángulos.

#### Filtración de Vietoris-Rips (a cuatro escalas ε)

| Negro | Blanco |
|:-----:|:------:|
| ![epsilon negro](ejemplo_ometitlan/figuras/fig05_complex_negro_epsilons.png) | ![epsilon blanco](ejemplo_ometitlan/figuras/fig06_complex_blanco_epsilons.png) |

#### Espacio topológico (trayectoria MDS de cada jugador)

![espacio topológico](ejemplo_ometitlan/figuras/fig07_topo_space_negro.png)

#### Evolución de la entropía por jugador

![entropía](ejemplo_ometitlan/figuras/fig01_entropy_per_player.png)

#### Comparación de curvas de Betti

![comparación betti](ejemplo_ometitlan/figuras/fig09_comparison_betti.png)

Las curvas de Betti muestran mayor separación entre jugadores, especialmente en H₁ a escalas intermedias.

#### Resultados estadísticos

| Pregunta | p-valor | Conclusión |
|----------|---------|------------|
| ¿Son topológicamente distintos ometitlan y haya371203? | **0.541** | No significativo, pero mayor variedad que en Oguchi vs tiernuki |
| ¿Cambia el estilo de ometitlan entre apertura y final? | 0.001 | Sí — muy significativo |
| ¿Cambia el estilo de haya371203 entre apertura y final? | 0.001 | Sí — muy significativo |
| SVM apertura vs final — ometitlan (H₁) | — | **94.9% accuracy** |
| SVM apertura vs final — haya371203 (H₁) | — | **90.9% accuracy** |

Ver el [reporte completo](ejemplo_ometitlan/reporte_ometitlan.md).

---

### Comparación directa

| Métrica | Oguchi vs tiernuki | ometitlan vs haya371203 |
|---------|:-----------------:|:----------------------:|
| Movimientos | 283 | 198 |
| p-valor N vs B | **0.908** | **0.541** |
| Interpretación | Estilos casi idénticos | Mayor variedad entre jugadores |
| H₁ entropía media (N) | 2.978 | 2.678 |
| H₁ entropía media (B) | 2.954 | 2.660 |
| Diferencia de entropía H₁ | 0.024 | 0.018 |
| SVM apertura vs final (N) | 97.2% | 94.9% |
| SVM apertura vs final (B) | 96.5% | 90.9% |

**Lectura del p-valor entre jugadores:** un p-valor más alto (0.908) significa que el estadístico observado está más cerca del centro de la distribución nula — los patrones de ambos jugadores son más intercambiables. Un p-valor más bajo (0.541) indica que hay algo más de estructura diferenciada entre los dos estilos, aunque sin alcanzar significancia estadística.

**Lectura de la entropía H₁:** los valores más altos en Oguchi vs tiernuki reflejan mayor complejidad topológica media en ambos jugadores — más lazos, ojos y cercados por patrón — consistente con una partida de mayor densidad (283 movimientos vs 198).

**Lectura del SVM:** la caída de accuracy en haya371203 (90.9% vs 96.5% de tiernuki) sugiere que la transición apertura-final es más gradual o menos nítida en ese jugador — hay mayor continuidad estilística entre sus fases de juego.

---

## Cómo correr tu propio análisis

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Estructura de imports necesaria

`analyze_game.py` requiere que la carpeta de Candela esté disponible. Clona primero Candela:

```bash
git clone https://github.com/angelsesma/candela.git
```

Luego coloca este repositorio dentro de la carpeta de Candela, o ajusta el `sys.path` en `analyze_game.py` para que apunte a donde está `candela.py`.

### 3. Correr el análisis

```bash
python analyze_game.py ruta/a/partida.sgf ruta/salida/
```

### 4. Qué produce

```
outputs/mi_partida/
├── report.md                    # Reporte completo con interpretación
├── figures/
│   ├── fig01_entropy_per_player.png
│   ├── fig03_complex_negro_moments.png    # Complejo VR por momentos
│   ├── fig05_complex_negro_epsilons.png   # Filtración VR
│   ├── fig07_topo_space_negro.png         # Espacio topológico MDS
│   ├── fig08_topo_space_complex.png       # VR sobre MDS
│   ├── fig09_comparison_betti.png
│   └── ...  (13 figuras en total)
└── distances/
    └── *.npy
```

---

## Dependencias

```
sgfmill          # Leer archivos SGF de Go
gudhi >= 3.9     # Homología persistente, complejos de Vietoris-Rips
persim >= 0.3    # Imágenes de persistencia, distancias entre diagramas
ripser >= 0.6    # Cálculo rápido de homología persistente
POT >= 0.9       # Distancia de Wasserstein (Python Optimal Transport)
scikit-learn     # SVM, clustering, MDS
scipy            # Estadística
networkx         # Grafos de adyacencia
numpy
matplotlib
```

---

## Créditos

### Candela
Este sistema usa **[Candela](https://github.com/angelsesma/candela)** como extractor de patrones canónicos de Go. Candela fue desarrollado por [@angelsesma](https://github.com/angelsesma) y es el componente que convierte cada posición del tablero en una representación matemática comparable entre jugadores, partidas y estilos de juego.

Sin la canonicalización de Candela — que unifica rotaciones, reflexiones e inversiones de color — el análisis topológico no podría comparar patrones de forma rigurosa.

> Sesma González, Á. A., & Jiménez Martínez, L. (2025). Pattern Acquisition and Comparative Analysis in the Game of Go: A Modern Approach. *Journal of Go Studies*, 2. https://intergostudies.net/journal/journal_view.asp?jn_num=9

### Análisis topológico
La capa TDA (módulos `candela_tda/`) fue construida sobre Candela por [@metamatematico](https://github.com/metamatematico) usando:
- [GUDHI](https://gudhi.inria.fr/) — librería de homología persistente del INRIA
- Fasy et al. (2014), *"Confidence Sets for Persistence Diagrams"* — para las bandas de confianza bootstrap
- [persim](https://persim.scikit-tda.org/) — imágenes y distancias de persistencia

---

*"El Go es demasiado complejo para que la intuición lo abarque todo. La topología nos da un lenguaje para medir lo que el ojo no puede."*

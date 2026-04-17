# Sistema de Análisis Topológico del Go

> Extensión de [Candela](https://github.com/angelsesma/candela) que aplica **homología persistente** a los patrones de Go para medir, comparar y visualizar el estilo de juego de cada jugador.

---

## ¿Qué problema resuelve?

Candela produce una base de datos de patrones canónicos del Go: cada jugada de cada partida queda representada como una configuración 19×19 de piedras, normalizada por rotación, reflexión e inversión de color.

Pero esos patrones, por sí solos, no responden preguntas como:

- ¿Qué tan diferente es el estilo topológico de dos jugadores?
- ¿Cambia el estilo de un jugador entre la apertura y el final de la partida?
- ¿Cuándo forma un jugador sus primeros "ojos" o territorios cerrados?

Este sistema responde esas preguntas usando **topología algebraica**: convierte los patrones de Candela en complejos simpliciales, calcula su homología persistente y aplica estadística sobre los resultados.

---

## Rol de Candela en este sistema

```
Partida SGF
    │
    ▼
candela.py  ←─── extrae patrones canónicos 19×19 por jugada
    │
    │  Pattern = tuple[tuple[str,...],...]  (19×19)
    │  Símbolos: 'b' piedra negra, 'w' piedra blanca,
    │            '+' vacío interior, '/' borde, '.' fuera
    ▼
candela/tda/  ←─── análisis topológico sobre esos patrones
```

Candela hace lo que ninguna librería de topología puede hacer: **entender el tablero de Go**. Su función `canonical_form()` garantiza que el mismo patrón jugado con negro o blanco, en cualquier esquina del tablero, sea el mismo objeto matemático. Sin esa garantía, comparar jugadores topológicamente carecería de sentido.

---

## Módulos de la capa TDA

### `candela/tda/representation.py` — Del patrón al dato matemático

Tres formas de representar un patrón de Candela:

| Función | Salida | Uso |
|---------|--------|-----|
| `pattern_to_pointcloud(p)` | Array `(n_piedras, 2)` | Construir el complejo VR sobre las piedras del jugador |
| `pattern_to_feature_vector(p)` | Vector de 361 dimensiones | Comparar patrones, MDS, SVM |
| `pattern_to_graph(p)` | `nx.Graph` 4-adyacente | Análisis de conectividad |

---

### `candela/tda/complex.py` — Complejo de Vietoris-Rips

Convierte las piedras del jugador en un **complejo simplicial** variando la escala ε:

```
ε = 1.0  →  solo conecta piedras con libertades compartidas (grupos del tablero)
ε = 2.5  →  conecta piedras a distancia Manhattan ≤ 2 (influencia local)
ε = 4.0  →  grupos que comparten influencia en el sector
ε = 6.0  →  relaciones de largo alcance entre grupos distantes
```

> Se usa **distancia Manhattan** (|Δfila| + |Δcol|) en lugar de euclidiana, porque el tablero de Go es una cuadrícula donde la conexión es ortogonal. Con ε=1 Manhattan captura exactamente las piedras con libertades compartidas.

La filtración de ε=0 a ε=∞ es lo que la homología persistente analiza.

---

### `candela/tda/persistence.py` — Homología persistente

Para cada patrón calcula cómo cambian H₀ y H₁ al barrer ε:

| Descriptor | Qué mide en términos de Go |
|------------|---------------------------|
| **H₀** | Número de grupos de piedras independientes |
| **H₁** | Número de lazos topológicos (ojos, cercados) |
| **Entropía persistente** | Complejidad global del patrón en un solo número |
| **Curva de Betti** | H₀ o H₁ activos en función de ε |
| **Imagen de persistencia** | Representación 2D del diagrama de persistencia, útil para ML |

---

### `candela/tda/distances.py` — Distancias entre diagramas

Mide qué tan diferentes son dos posiciones topológicamente:

| Distancia | Propiedad |
|-----------|-----------|
| Bottleneck | Robusta a ruido, sensible al rasgo más persistente |
| Wasserstein | Tiene en cuenta todos los rasgos, ponderados por longitud |
| Landscape L² | Computable en espacios de Hilbert, apta para estadística |

---

### `candela/tda/stats.py` — Validación estadística

- **Test de permutación:** ¿La diferencia entre dos grupos de patrones es estadísticamente significativa?
- **Bootstrap (Fasy et al. 2014):** Banda de confianza al 95% para curvas de Betti
- **Clustering aglomerativo:** ¿Hay fases de juego con estilos similares?
- **SVM sobre imágenes de persistencia:** ¿Se puede clasificar apertura vs final, negro vs blanco?

---

### `candela/tda/viz.py` — Visualización sobre el tablero

Dibuja el complejo simplicial **sobre el tablero de Go real**:

- Nodos (0-símplices): intersecciones donde el jugador tiene piedra
- Aristas (1-símplices): pares de piedras a distancia Manhattan ≤ ε
- Triángulos (2-símplices): tríos de piedras mutuamente cercanas — indicadores de densidad territorial

También proyecta el espacio topológico de un jugador en 2D via MDS, mostrando la trayectoria estilística a lo largo de la partida.

---

### `candela/tda/report.py` — Reporte narrativo

Genera un Markdown con:
- Tablas de métricas por jugador
- Interpretación automática de cada resultado (qué significa ese p-valor, esa entropía, ese silhouette en términos de Go)
- Figuras embebidas con explicación por figura

---

## Script principal: `analyze_game.py`

Corre el pipeline completo sobre cualquier archivo SGF:

```bash
python analyze_game.py ruta/partida.sgf ruta/salida/
```

Produce **13 figuras** y un **reporte Markdown** completo en ~40-60 segundos.

### Las 13 figuras

| # | Figura | Qué muestra |
|---|--------|-------------|
| 01 | Entropía por jugador | H₀ y H₁ a lo largo de los movimientos de cada jugador |
| 02 | Curvas de Betti con bootstrap | Variabilidad del estilo topológico de cada jugador |
| 03 | Complejo VR — Negro en 5 momentos | Cómo construye su red de piedras Oguchi |
| 04 | Complejo VR — Blanco en 5 momentos | Idem para tiernuki |
| 05 | Filtración VR — Negro | La misma posición a ε=1.5, 2.5, 4.0, 6.0 |
| 06 | Filtración VR — Blanco | Idem |
| 07 | Espacio topológico MDS | Trayectoria estilística de cada jugador en 2D |
| 08 | VR sobre espacio MDS | Clusters de jugadas topológicamente similares |
| 09 | Comparación curvas de Betti | Los dos jugadores superpuestos |
| 10 | Diagramas de persistencia | En tres momentos (25%, 50%, 75%) por jugador |
| 11 | Matrices de distancias | Similitud entre patrones propios de cada jugador |
| 12 | Distribuciones nulas | Tests de permutación: N vs B y apertura vs final |
| 13 | Heatmaps del tablero | Zonas de alta complejidad topológica por jugador |

---

## Instalación

```bash
pip install -r requirements.txt
```

Dependencias principales: `gudhi`, `persim`, `ripser`, `POT`, `scikit-learn`, `sgfmill`, `matplotlib`

---

## Ejemplo de resultados

Partida **Oguchi vs tiernuki** (OGS, 2026-02-20, 283 movimientos, B+4.5):

| Pregunta | p-valor | Resultado |
|----------|---------|-----------|
| ¿Son topológicamente distintos los dos jugadores? | 0.908 | No — estilos indistinguibles |
| ¿Cambia el estilo de Oguchi entre apertura y final? | 0.001 | Sí — diferencia muy significativa |
| ¿Cambia el estilo de tiernuki entre apertura y final? | 0.001 | Sí — diferencia muy significativa |

SVM apertura vs final (H₁): **97.2% accuracy** (Oguchi) y **96.5%** (tiernuki) — la topología captura con precisión el cambio de fase.

Ver el análisis completo: [github.com/metamatematico/an-lisis-topol-gico-del-Go](https://github.com/metamatematico/an-lisis-topol-gico-del-Go)

---

## Referencia

Si usas este sistema en un trabajo académico, cita también a Candela:

> Sesma González, Á. A., & Jiménez Martínez, L. (2025). Pattern Acquisition and Comparative Analysis in the Game of Go: A Modern Approach. *Journal of Go Studies*, 2. https://intergostudies.net/journal/journal_view.asp?jn_num=9

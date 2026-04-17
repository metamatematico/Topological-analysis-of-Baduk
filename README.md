# Análisis Topológico del Go

> **¿Qué tan diferente es el juego de dos jugadores de Go, matemáticamente?**
> Este proyecto responde esa pregunta usando *homología persistente* — una rama de la topología algebraica que detecta "forma" en datos.

---

## Tabla de contenidos

1. [La idea en términos de Go](#la-idea-en-términos-de-go)
2. [Cómo funciona el sistema](#cómo-funciona-el-sistema)
3. [Candela: el extractor de patrones](#candela-el-extractor-de-patrones)
4. [La capa de análisis topológico](#la-capa-de-análisis-topológico)
5. [Ejemplo completo: ometitlan vs haya371203](#ejemplo-completo-ometitlan-vs-haya371203)
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
        │  Patrón (tupla 19×19 de 'b','w','+','/')
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

### Por qué es importante para el TDA

Sin Candela, no tendríamos una representación estructurada y comparable de las posiciones del tablero. La canonicalización garantiza que la topología que detectamos refleja la **geometría real del juego**, no artefactos de orientación o color.

```python
# Candela produce patrones como este (fragmento 5×5 del centro):
# ('b', '+', '+', 'w', '+')
# ('+', 'b', 'w', '+', '+')
# ('+', '+', 'b', '+', 'w')
# ...
# Cada celda: 'b'=piedra negra, 'w'=piedra blanca,
#             '+'=vacía (interior), '/'=borde, '.'=fuera
```

---

## La capa de análisis topológico

Los módulos en `candela_tda/` toman los patrones de Candela y aplican análisis topológico:

### `representation.py` — Convertir patrones en datos

| Función | Entrada | Salida | Para qué sirve |
|---------|---------|--------|----------------|
| `pattern_to_pointcloud` | Patrón 19×19 | Array (n,2) de coordenadas | Construir el complejo simplicial |
| `pattern_to_feature_vector` | Patrón 19×19 | Vector de 361 dimensiones | Comparar patrones, MDS, SVM |
| `pattern_to_graph` | Patrón 19×19 | Grafo de adyacencia | Análisis de conectividad |

### `complex.py` — El complejo de Vietoris-Rips

El **complejo de Vietoris-Rips** convierte las piedras del jugador en un objeto geométrico:
- A escala ε pequeña (ε=1.5): solo conecta piedras adyacentes — refleja los *grupos* del Go
- A escala ε mediana (ε=2.5): conecta piedras con distancia Manhattan ≤ 2.5 — captura *influencia local*
- A escala ε grande (ε=6.0): relaciones de largo alcance entre grupos distantes — *estrategia global*

> **Nota:** Usamos **distancia Manhattan** (|Δfila| + |Δcolumna|) en lugar de euclidiana, porque el tablero de Go es una cuadrícula donde el movimiento es ortogonal. Con ε=1, Manhattan captura exactamente las piedras con libertades compartidas.

### `persistence.py` — Homología persistente

Calcula cómo cambian H₀ y H₁ conforme ε crece de 0 a ∞:
- Un **diagrama de persistencia** muestra qué features topológicas nacen y mueren
- La **entropía persistente** cuantifica la complejidad del patrón con un solo número
- Las **curvas de Betti** muestran cuántos grupos/lazos están activos a cada escala

### `stats.py` — Validación estadística

- **Test de permutación:** ¿Las distribuciones topológicas de dos grupos son distintas?
- **Bootstrap (Fasy et al. 2014):** Bandas de confianza al 95% para las curvas de Betti
- **SVM sobre imágenes de persistencia:** ¿Se pueden clasificar jugadores por su topología?

### `viz.py` — Visualización

Dibuja el complejo simplicial **sobre el tablero de Go real**, mostrando:
- Nodos = intersecciones con piedra
- Aristas = pares de piedras a distancia ≤ ε
- Triángulos (2-símplices) = tríos de piedras mutuamente cercanas

---

## Ejemplo completo: Oguchi vs tiernuki

Partida de OGS, 2026-02-20. **283 movimientos. Victoria de Blanco por 4.5 puntos (B+4.5).**

Los resultados completos están en [`ejemplo_oguchi_vs_tiernuki/`](ejemplo_oguchi_vs_tiernuki/).

### Complejo simplicial de cada jugador a lo largo del partido

Las figuras muestran el complejo VR (ε=2.5, distancia Manhattan) de las piedras acumuladas en cinco momentos (20%, 40%, 60%, 80%, 100% de sus jugadas):

| Negro (Oguchi) | Blanco (tiernuki) |
|:--------------:|:-----------------:|
| ![complejo negro](ejemplo_oguchi_vs_tiernuki/figuras/fig03_complex_negro_moments.png) | ![complejo blanco](ejemplo_oguchi_vs_tiernuki/figuras/fig04_complex_blanco_moments.png) |

Los triángulos (zonas rellenas) son tríos de piedras mutuamente cercanas — indicador de densidad territorial. Su crecimiento hacia el final refleja la consolidación de grupos.

### Filtración de Vietoris-Rips: cómo la escala revela estructura

La misma posición a cuatro valores de ε — esto es literalmente lo que la homología persistente "ve" al barrer de ε=0 a ε=∞:

| Negro | Blanco |
|:-----:|:------:|
| ![epsilon negro](ejemplo_oguchi_vs_tiernuki/figuras/fig05_complex_negro_epsilons.png) | ![epsilon blanco](ejemplo_oguchi_vs_tiernuki/figuras/fig06_complex_blanco_epsilons.png) |

### Espacio topológico de cada jugador

Cada punto es una jugada del jugador, proyectada en 2D con MDS. El color va de oscuro (inicio) a claro (final). La trayectoria muestra cómo evoluciona el estilo topológico del jugador:

![espacio topológico](ejemplo_oguchi_vs_tiernuki/figuras/fig07_topo_space_negro.png)

El complejo VR construido sobre ese espacio MDS revela clusters de jugadas similares:

![complejo sobre MDS](ejemplo_oguchi_vs_tiernuki/figuras/fig08_topo_space_complex.png)

### Evolución de la entropía topológica

H₀ = grupos de piedras. H₁ = lazos / ojos. La línea roja marca la mitad de la partida:

![entropía](ejemplo_oguchi_vs_tiernuki/figuras/fig01_entropy_per_player.png)

### Comparación de curvas de Betti (con bandas de confianza al 95%)

![comparación betti](ejemplo_oguchi_vs_tiernuki/figuras/fig09_comparison_betti.png)

### Resultados estadísticos principales

| Pregunta | p-valor | Conclusión |
|----------|---------|------------|
| ¿Son distintos los estilos de Oguchi y tiernuki? | 0.908 | No — topológicamente indistinguibles |
| ¿Cambia el estilo de Oguchi entre apertura y final? | 0.001 | Sí — diferencia muy significativa |
| ¿Cambia el estilo de tiernuki entre apertura y final? | 0.001 | Sí — diferencia muy significativa |

El SVM sobre imágenes de persistencia H₁ para clasificar apertura vs final alcanza **97.2% de accuracy** (Oguchi) y **96.5%** (tiernuki) — la topología captura con precisión el cambio de fase de la partida.

Ver el [reporte completo con interpretación](ejemplo_oguchi_vs_tiernuki/reporte_oguchi_vs_tiernuki.md).

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

**Ejemplo:**
```bash
python analyze_game.py mi_partida.sgf outputs/mi_partida/
```

### 4. Qué produce

```
outputs/mi_partida/
├── report.md                    # Reporte completo con interpretación
├── analysis.json                # Todos los números del análisis
├── figures/
│   ├── fig01_entropy_per_player.png
│   ├── fig02_betti_curves_per_player.png
│   ├── fig03_complex_negro_moments.png    # Complejo por momentos
│   ├── fig04_complex_blanco_moments.png
│   ├── fig05_complex_negro_epsilons.png   # Filtración VR
│   ├── fig06_complex_blanco_epsilons.png
│   ├── fig07_topo_space_negro.png         # Espacio topológico MDS
│   ├── fig08_topo_space_complex.png       # VR sobre MDS
│   ├── fig09_comparison_betti.png
│   ├── fig10_persistence_per_player.png
│   ├── fig11_distance_matrices.png
│   ├── fig12_permutation_tests.png
│   └── fig13_board_heatmaps.png
└── distances/
    ├── negro_feature_euclidean.npy
    ├── blanco_feature_euclidean.npy
    └── all_feature_euclidean.npy
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

### Análisis topológico
La capa TDA (módulos `candela_tda/`) fue construida sobre Candela por [@metamatematico](https://github.com/metamatematico) usando:
- [GUDHI](https://gudhi.inria.fr/) — librería de homología persistente del INRIA
- Fasy et al. (2014), *"Confidence Sets for Persistence Diagrams"* — para las bandas de confianza bootstrap
- [persim](https://persim.scikit-tda.org/) — imágenes y distancias de persistencia

---

*"El Go es demasiado complejo para que la intuición lo abarque todo. La topología nos da un lenguaje para medir lo que el ojo no puede."*

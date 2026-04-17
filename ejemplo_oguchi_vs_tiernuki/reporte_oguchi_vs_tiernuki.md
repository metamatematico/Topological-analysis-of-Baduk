# Analisis TDA por Jugador — Oguchi vs tiernuki (2026-02-20)

**Generado:** 2026-04-16 21:03:07

---

## Configuracion

```json
{
  "sgf": "84385826-285-tiernuki-Oguchi.sgf",
  "negro": "Oguchi",
  "blanco": "tiernuki",
  "resultado": "B+4.5",
  "fecha": "2026-02-20",
  "komi": 6.5,
  "fuente": "OGS: https://online-go.com/game/84385826",
  "max_edge_length": 12.0,
  "max_dimension": 2,
  "epsilon_figuras_tablero": 2.5,
  "epsilons_progresion": [
    1.5,
    2.5,
    4.0,
    6.0
  ],
  "bootstrap_resamples": 400,
  "n_permutaciones": 999,
  "seed": 0
}
```

---

## Resumen de la cohorte

| Parametro | Valor |
|-----------|-------|
| movimientos_totales | 283 |
| patrones_unicos | 281 |
| movimientos_Oguchi | 142 |
| movimientos_tiernuki | 141 |

---

## Descriptores topologicos

### H0 — OGUCHI (GRUPOS DE PIEDRAS)

| Descriptor | Valor |
|------------|-------|
| mean | 3.9978 |
| std | 1.1666 |
| min | 0.0000 |
| max | 5.2623 |
| betti0_en_eps6 | 0.1056 |

### H1 — OGUCHI (LAZOS / OJOS)

| Descriptor | Valor |
|------------|-------|
| mean | 2.9778 |
| std | 1.3238 |
| min | 0.0000 |
| max | 4.6142 |
| betti1_en_eps6 | 0.0423 |

### H0 — TIERNUKI (GRUPOS DE PIEDRAS)

| Descriptor | Valor |
|------------|-------|
| mean | 3.9724 |
| std | 1.1571 |
| min | 0.0000 |
| max | 5.3053 |
| betti0_en_eps6 | 0.0780 |

### H1 — TIERNUKI (LAZOS / OJOS)

| Descriptor | Valor |
|------------|-------|
| mean | 2.9541 |
| std | 1.3125 |
| min | -0.0000 |
| max | 4.7491 |
| betti1_en_eps6 | 0.0638 |

---

## Resultados estadisticos

### Test de permutacion — Oguchi vs tiernuki (estilo topologico)

| Estadistico T | -0.0492 |
|---------------|------|
| p-valor | 0.9080 |
| Permutaciones | 999 |

El test de permutacion (Oguchi vs tiernuki (estilo topologico)) no es significativo (p = 0.908 (no significativo)). No hay evidencia suficiente para rechazar que ambas cohortes provienen de la misma distribucion topologica.

### Test de permutacion — Apertura vs Final (toda la partida)

| Estadistico T | 2.0054 |
|---------------|------|
| p-valor | 0.0010 |
| Permutaciones | 999 |

El test de permutacion (Apertura vs Final (toda la partida)) resulta **p = 0.001** (significativo). El estadistico T=2.0054 indica que la distancia media entre los dos grupos es mayor que la esperada bajo la hipotesis nula. Esto significa que las dos cohortes de patrones tienen distribuciones topologicas **estadisticamente diferentes**.

### Test de permutacion — Apertura vs Final — solo Oguchi

| Estadistico T | 2.3280 |
|---------------|------|
| p-valor | 0.0010 |
| Permutaciones | 999 |

El test de permutacion (Apertura vs Final — solo Oguchi) resulta **p = 0.001** (significativo). El estadistico T=2.3280 indica que la distancia media entre los dos grupos es mayor que la esperada bajo la hipotesis nula. Esto significa que las dos cohortes de patrones tienen distribuciones topologicas **estadisticamente diferentes**.

### Test de permutacion — Apertura vs Final — solo tiernuki

| Estadistico T | 1.6257 |
|---------------|------|
| p-valor | 0.0010 |
| Permutaciones | 999 |

El test de permutacion (Apertura vs Final — solo tiernuki) resulta **p = 0.001** (significativo). El estadistico T=1.6257 indica que la distancia media entre los dos grupos es mayor que la esperada bajo la hipotesis nula. Esto significa que las dos cohortes de patrones tienen distribuciones topologicas **estadisticamente diferentes**.

### Clustering aglomerativo (k=2)

| Silhouette | 0.3012 |
|------------|------|
| Coef. Cofenotico | 0.8716 |

El coeficiente de silueta (0.301) indica estructura debil pero existente con k=2 clusters. El coeficiente cofenotico (0.872) es muy buena: el dendrograma representa fielmente las distancias originales. Los clusters son difusos; interpretar con cautela.

### Bandas de confianza bootstrap (Fasy et al. 2014)

| Valor critico c_alpha | 0.2510 |
|------------------------|------|
| Nivel de significancia | 95% |

La curva de Betti media cae dentro de una banda de confianza del 95% con valor critico c_alpha=0.251. Un c_alpha bajo indica poca variabilidad entre los diagramas de la cohorte; uno alto indica diversidad topologica elevada.

### Clasificador SVM — H0 — Oguchi vs tiernuki

| Accuracy media | 0.5018 +/- 0.0100 |
|----------------|------|
| F1 macro | 0.3341 |

El clasificador SVM (H0 — Oguchi vs tiernuki) obtiene una accuracy de 0.502 +/- 0.010, comparable al azar (referencia azar ~0.50). El F1 macro de 0.334 es bajo, lo que sugiere que las imagenes de persistencia H0 no codifican suficiente informacion discriminante para esta tarea.

### Clasificador SVM — H1 — Oguchi vs tiernuki

| Accuracy media | 0.4313 +/- 0.0100 |
|----------------|------|
| F1 macro | 0.4176 |

El clasificador SVM (H1 — Oguchi vs tiernuki) obtiene una accuracy de 0.431 +/- 0.010, comparable al azar (referencia azar ~0.50). El F1 macro de 0.418 es bajo, lo que sugiere que las imagenes de persistencia H0 no codifican suficiente informacion discriminante para esta tarea.

### Clasificador SVM — H1 — Apertura vs Final (Oguchi)

| Accuracy media | 0.9716 +/- 0.0100 |
|----------------|------|
| F1 macro | 0.9716 |

El clasificador SVM (H1 — Apertura vs Final (Oguchi)) obtiene una accuracy de 0.972 +/- 0.010, claramente mejor que el azar (referencia azar ~0.50). El F1 macro de 0.972 indica que el clasificador discrimina entre clases de forma equilibrada.

### Clasificador SVM — H1 — Apertura vs Final (tiernuki)

| Accuracy media | 0.9645 +/- 0.0100 |
|----------------|------|
| F1 macro | 0.9644 |

El clasificador SVM (H1 — Apertura vs Final (tiernuki)) obtiene una accuracy de 0.965 +/- 0.010, claramente mejor que el azar (referencia azar ~0.50). El F1 macro de 0.964 indica que el clasificador discrimina entre clases de forma equilibrada.

---

## Figuras

### Fig01 Entropy Per Player

![fig01_entropy_per_player](figures/fig01_entropy_per_player.png)

**Interpretacion:** Evolucion de la entropia persistente H0 (grupos de piedras) y H1 (lazos/ojos) para cada jugador a lo largo de sus propios movimientos. La linea roja vertical marca la mitad de los movimientos de ese jugador. Una H0 creciente refleja como el jugador va poblando el tablero con grupos cada vez mas variados. Un pico de H1 indica el momento de maxima complejidad territorial (ojos, cercados). Comparar ambas filas permite ver si los dos jugadores tienen ritmos de complejizacion distintos.

### Fig02 Betti Curves Per Player

![fig02_betti_curves_per_player](figures/fig02_betti_curves_per_player.png)

**Interpretacion:** Curvas de Betti con bandas de confianza al 95% (Fasy et al. 2014) calculadas sobre los patrones de cada jugador por separado. La banda sombreada indica la variabilidad entre movimientos: una banda estrecha significa que el jugador juega patrones topologicamente consistentes; una banda ancha, que hay alta variabilidad estilistica. La comparacion directa de las curvas de Oguchi y tiernuki en la Fig. 09 muestra si sus estilos topologicos difieren sistematicamente.

### Fig03 Complex Negro Moments

![fig03_complex_negro_moments](figures/fig03_complex_negro_moments.png)

**Interpretacion:** Complejo simplicial de Vietoris-Rips (ε=2.5) construido sobre las piedras acumuladas de Oguchi en cinco momentos de la partida (20%, 40%, 60%, 80%, 100%). Los nodos son intersecciones del tablero donde Oguchi tiene piedra. Las aristas conectan piedras a distancia ≤ 2.5 (adyacentes y diagonales proximas). Los triangulos (2-simplices) son trios de piedras mutuamente proximas. La creciente densidad de triangulos hacia el final refleja la consolidacion de territorios.

### Fig04 Complex Blanco Moments

![fig04_complex_blanco_moments](figures/fig04_complex_blanco_moments.png)

**Interpretacion:** Idem Fig. 03 para tiernuki. Comparar la estructura del complejo con la de Oguchi permite ver diferencias en como cada jugador ocupa el tablero: grupos mas dispersos vs mas concentrados, mayor o menor numero de 2-simplices (indicativo de mayor densidad local de piedras).

### Fig05 Complex Negro Epsilons

![fig05_complex_negro_epsilons](figures/fig05_complex_negro_epsilons.png)

**Interpretacion:** Filtracion de Vietoris-Rips de las piedras de Oguchi en el movimiento 143 (mitad de partida) a cuatro escalas distintas (ε=[1.5, 2.5, 4.0, 6.0]). A ε=1.5 solo aparecen aristas entre piedras adyacentes (grupos del tablero). A ε=2.5 se conectan piedras con separacion de hasta 2 intersecciones. A ε≥4.0 el complejo captura relaciones de largo alcance entre grupos distantes. Esta progresion es la visualizacion directa de la filtracion que usa la homologia persistente.

### Fig06 Complex Blanco Epsilons

![fig06_complex_blanco_epsilons](figures/fig06_complex_blanco_epsilons.png)

**Interpretacion:** Idem Fig. 05 para tiernuki en su movimiento 142.

### Fig07 Topo Space Negro

![fig07_topo_space_negro](figures/fig07_topo_space_negro.png)

**Interpretacion:** Espacio topologico de cada jugador: cada punto es uno de sus movimientos, representado por su vector de caracteristicas de 361 dimensiones y proyectado en 2D mediante MDS (Multidimensional Scaling). Los puntos estan coloreados de oscuro (inicio) a claro (final). La linea traza la trayectoria temporal. Una trayectoria compacta indica un jugador consistente; una dispersa indica alta variedad de patrones. La estrella verde es el primer movimiento; la X roja es el ultimo.

### Fig08 Topo Space Complex

![fig08_topo_space_complex](figures/fig08_topo_space_complex.png)

**Interpretacion:** Complejo simplicial de Vietoris-Rips construido directamente sobre el espacio topologico MDS de cada jugador. El epsilon se ajusta automaticamente al percentil 20 de las distancias inter-patron en el espacio MDS. Los triangulos (2-simplices) indican grupos de movimientos topologicamente similares. Los colores de los nodos representan el tiempo (plasma: oscuro=inicio, claro=final). Este es el espacio topologico global del jugador a lo largo de toda la partida.

### Fig09 Comparison Betti

![fig09_comparison_betti](figures/fig09_comparison_betti.png)

**Interpretacion:** Superposicion de las curvas de Betti de Oguchi y tiernuki en las mismas axes, con sus respectivas bandas de confianza al 95%. Si las curvas se solapan, los dos jugadores tienen estilos topologicos similares a esa escala. Si se separan, hay diferencias sistematicas: uno forma mas grupos (H0 mas alto) o mas lazos/ojos (H1 mas alto) que el otro.

### Fig10 Persistence Per Player

![fig10_persistence_per_player](figures/fig10_persistence_per_player.png)

**Interpretacion:** Diagramas de persistencia de cada jugador en tres momentos (25%, 50%, 75%). Puntos azules: componentes conexos (H0). Triangulos naranjas: lazos (H1). Puntos lejos de la diagonal son caracteristicas topologicas significativas y duraderas. La evolucion de los diagramas muestra como cambia la complejidad topologica de los patrones de cada jugador a medida que avanza la partida.

### Fig11 Distance Matrices

![fig11_distance_matrices](figures/fig11_distance_matrices.png)

**Interpretacion:** Matrices de distancias euclidianas entre los vectores de patron de cada jugador (calculadas solo sobre sus propios movimientos). Colores oscuros = patrones similares. La linea roja divide apertura y final del jugador. Un bloque homogeneo indica estilo consistente; un gradiente indica evolucion progresiva del estilo.

### Fig12 Permutation Tests

![fig12_permutation_tests](figures/fig12_permutation_tests.png)

**Interpretacion:** Distribucion nula del estadistico T bajo permutacion aleatoria de etiquetas (999 permutaciones). La linea roja marca el valor observado. Izquierda: test Negro vs Blanco — si la linea roja cae en la cola derecha, los dos jugadores tienen estilos topologicos estadisticamente distintos. Derecha: test Apertura vs Final — si es significativo, la partida tiene dos fases topologicamente diferenciadas.

### Fig13 Board Heatmaps

![fig13_board_heatmaps](figures/fig13_board_heatmaps.png)

**Interpretacion:** Mapa de calor del tablero 19x19 por jugador. Izquierda: entropia H1 media en cada interseccion (rojo intenso = alta complejidad topologica en los patrones que pasan por esa interseccion). Derecha: numero de movimientos del jugador en cada interseccion. Las zonas calientes en entropia que coinciden con zonas de alta frecuencia son los puntos de mayor actividad e importancia topologica de ese jugador.

---

## Conclusiones

## Hallazgos principales

### 1. Comparacion entre jugadores
El test de permutacion Oguchi vs tiernuki arroja p=0.9080. No hay diferencia estadisticamente significativa entre los estilos topologicos de los dos jugadores. El clasificador SVM sobre imagenes de persistencia H1 obtiene 0.431 de accuracy al distinguir movimientos de Oguchi y tiernuki, lo que sugiere que la diferencia no es facilmente separable con este tipo de features.

### 2. Evolucion de cada jugador
- **Oguchi**: apertura vs final p=0.0010 (significativo). H1 entropia media=2.978.
- **tiernuki**: apertura vs final p=0.0010 (significativo). H1 entropia media=2.954.

### 3. Complejos simpliciales
La filtracion VR a epsilon=2.5 (Figs. 03-04) muestra como cada jugador construye su red de piedras a lo largo de la partida. La Fig. 05-06 ilustra la filtracion: a epsilon pequeno solo se conectan grupos adyacentes (refleja la logica de atari y capturas); a epsilon grande emergen relaciones de largo alcance entre grupos separados (estrategia de influencia global).

### 4. Espacio topologico del jugador
El espacio MDS (Figs. 07-08) muestra la trayectoria estilistica de cada jugador. Un espacio compacto indica consistencia; uno disperso, variedad tactica. El complejo VR sobre este espacio revela si hay clusters de movimientos similares (posibles repertorios tacticos o secuencias joseki repetidas).

**Tiempo total de analisis:** 101.3s


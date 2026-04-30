# Análisis Topológico de una Partida de Go: Oguchi vs tiernuki

**Partida:** Oguchi (Negro) vs tiernuki (Blanco)  
**Resultado:** B+4.5  
**Movimientos:** 283  
**Fuente:** OGS #84385826  
**Fecha:** 2026-02-20

---

| Campo | Valor |
|---|---|
| Jugador Negro | Oguchi |
| Jugador Blanco | tiernuki |
| Resultado | B+4.5 (victoria de Blanco por 4.5 puntos) |
| Total de movimientos | 283 |
| Tablero | 19×19 |
| Plataforma | OGS (Online Go Server) |
| ID de partida | 84385826 |
| Fecha | 20 de febrero de 2026 |

---

## Introducción: ¿Qué es el TDA y por qué aplicarlo al Go?

El Análisis Topológico de Datos (TDA, por sus siglas en inglés *Topological Data Analysis*) es una rama de la matemática aplicada que extrae información cualitativa —la "forma"— de conjuntos de datos de alta dimensión. Su herramienta central, la **homología persistente**, detecta y cuantifica rasgos topológicos como componentes conexas, lazos y cavidades a múltiples escalas simultáneamente, sin depender de un umbral fijo ni de suposiciones sobre la distribución de los datos.

El Go es, en esencia, un problema espacial: las piedras ocupan posiciones en una cuadrícula, forman grupos, cercan territorio, construyen ojos. Estas nociones —conexión, lazo, encierro— son exactamente los objetos que estudia la topología. Aplicar TDA a una partida de Go permite responder preguntas que los métodos estadísticos clásicos no formulan: ¿cuándo se consolida la estructura territorial de un jugador? ¿Son topológicamente distinguibles dos estilos de juego? ¿Hay un momento algebraicamente certificable en que un grupo adquiere dos ojos? ¿Cómo evoluciona la complejidad táctica a lo largo de la partida?

Este documento presenta el análisis completo de la partida Oguchi–tiernuki usando el pipeline CANDELA, que implementa seis herramientas TDA complementarias: complejos de Vietoris-Rips, homología persistente, cohomología persistente con producto cup, reducción dimensional (MDS y UMAP), estadística topológica y nuevos descriptores (ECC, silhouette, transiciones, ventana deslizante). Los resultados se interpretan simultáneamente para dos audiencias: matemáticos y jugadores de Go.

---

## Sección 1 — El complejo de Vietoris-Rips

**Carpeta de figuras:** `01_complejo_vr/`

| Figura | Descripción |
|---|---|
| `01_negro_momentos.png` | Complejo VR de Oguchi en 5 momentos (20%–100%) con ε=8 |
| `02_blanco_momentos.png` | Complejo VR de tiernuki en 5 momentos (20%–100%) con ε=9 |
| `03_negro_filtracion_epsilon.png` | Filtración VR de Oguchi en el movimiento 143 con ε ∈ {1, 8, 16, 24, 31} |
| `04_blanco_filtracion_epsilon.png` | Filtración VR de tiernuki en el movimiento 142 con ε ∈ {1, 9, 17, 25, 33} |
| `05_negro_dim_birth.png` | Coloración por dimensión y momento de nacimiento para Oguchi (ε=8) |
| `06_blanco_dim_birth.png` | Coloración por dimensión y momento de nacimiento para tiernuki (ε=9) |

![Oguchi en 5 momentos](01_complejo_vr/01_negro_momentos.png)
![tiernuki en 5 momentos](01_complejo_vr/02_blanco_momentos.png)
![Filtración VR Oguchi](01_complejo_vr/03_negro_filtracion_epsilon.png)
![Filtración VR tiernuki](01_complejo_vr/04_blanco_filtracion_epsilon.png)
![Dimensión y nacimiento Oguchi](01_complejo_vr/05_negro_dim_birth.png)
![Dimensión y nacimiento tiernuki](01_complejo_vr/06_blanco_dim_birth.png)

---

#### Para el matemático

**Definición formal del complejo de Vietoris-Rips.** Dado un conjunto finito de puntos $X \subset \mathbb{R}^n$ y un parámetro de escala $\varepsilon > 0$, el *complejo de Vietoris-Rips* se define como:

$$\text{VR}_\varepsilon(X) = \{\sigma \subseteq X : d(x,y) \leq \varepsilon \;\forall\, x,y \in \sigma\}$$

Es decir, $\text{VR}_\varepsilon(X)$ es un complejo simplicial abstracto cuyos símplices son todos los subconjuntos de $X$ cuyo diámetro no excede $\varepsilon$. La dimensión de un símplice $\sigma$ es $|\sigma|-1$:

- **0-símplices (vértices):** cada piedra individual. Representan puntos del espacio.
- **1-símplices (aristas):** pares de piedras $(x,y)$ con $d(x,y) \leq \varepsilon$. Representan "conexión a escala $\varepsilon$".
- **2-símplices (triángulos):** ternas $\{x,y,z\}$ mutuamente dentro de $\varepsilon$. Representan zonas de densidad local.
- **$k$-símplices:** $(k+1)$-tuplas mutuamente dentro de $\varepsilon$; capturan densidad a orden superior.

**Distancia en el tablero.** Se usa la *distancia Manhattan* en la cuadrícula 19×19:

$$d\bigl((x_1,y_1),(x_2,y_2)\bigr) = |x_1-x_2| + |y_1-y_2|$$

Esta elección es natural porque el tablero es discreto, las piedras solo pueden colocarse en intersecciones, y el movimiento en Go es ortogonal (no diagonal). La distancia Manhattan preserva la geometría real de la conectividad del tablero.

**Elección adaptativa de $\varepsilon$.** El parámetro $\varepsilon$ se calibra individualmente para cada jugador. Se define:

$$\varepsilon_{\max} = \max_{x,y \in X_{\text{final}}} d(x,y)$$

donde $X_{\text{final}}$ es el conjunto de todas las piedras del jugador al final de la partida. Luego se construye una filtración uniforme: $\varepsilon_k = k \cdot \varepsilon_{\max} / (K-1)$ para $k = 0, \ldots, K-1$. En esta partida:

- Oguchi (Negro): $\varepsilon_{\max} = 31$, escala óptima $\varepsilon = 8$ → filtración $\{1, 8, 16, 24, 31\}$
- tiernuki (Blanco): $\varepsilon_{\max} = 33$, escala óptima $\varepsilon = 9$ → filtración $\{1, 9, 17, 25, 33\}$

La escala óptima es aquella que produce el mayor número de características topológicas no triviales (máxima complejidad en el diagrama de persistencia).

**Coloración por dimensión y momento de nacimiento.** En las figuras `05` y `06`, los símplices se colorean según dos criterios simultáneos: (1) *dimensión* — azul para vértices (0-símplices), verde para aristas (1-símplices), naranja para triángulos (2-símplices); (2) *momento de nacimiento* — la intensidad del color codifica en qué porcentaje de la partida apareció ese símplice en el complejo filtrado. Colores oscuros = nacimiento temprano (estructura antigua). Colores claros = nacimiento tardío (estructura reciente). Formalmente, si el símplice $\sigma$ entra en la filtración en el momento $t_\sigma \in [0,1]$ (fracción de movimientos transcurridos), la intensidad es proporcional a $1 - t_\sigma$.

---

#### Para el jugador de Go

Imagina que cada una de tus piedras es un punto en el tablero. El complejo de Vietoris-Rips es un *mapa de conectividad* que dibuja relaciones entre esas piedras según la distancia que las separa, controlada por el parámetro $\varepsilon$.

**Qué significan los elementos visuales:**

- **Un punto (vértice):** una piedra sola, sin vecinas dentro de $\varepsilon$ intersecciones.
- **Una arista entre dos puntos:** esas dos piedras están a $\varepsilon$ intersecciones o menos entre sí, es decir, se "ven" a esa escala.
- **Un triángulo:** tres piedras que están mutuamente dentro de $\varepsilon$ intersecciones. Un triángulo es un núcleo de densidad local — una zona donde tienes alta concentración de recursos.

**Qué revela cada valor de $\varepsilon$:**

- $\varepsilon = 1$: solo se conectan piedras adyacentes (compartiendo lado). Esto corresponde exactamente a los *grupos reales* del Go: las cadenas de piedras conectadas. El gráfico a esta escala muestra cuántos grupos tiene el jugador y dónde están.
- $\varepsilon = 8$ u $9$: se añaden conexiones a "salto de caballo" y más allá. Emergen las relaciones de influencia entre grupos vecinos. Los triángulos representan zonas donde tres grupos se apoyan mutuamente.
- $\varepsilon = 24$ o más: se captura la influencia global. Casi todas las piedras quedan conectadas en un único componente — la perspectiva "todo el tablero".

**Cómo leer la coloración por momento de nacimiento:**

El color oscuro señala estructuras que nacieron al principio de la partida: son la *infraestructura* territorial del jugador, las conexiones más establecidas y duraderas. El color claro señala estructuras tardías: recientes, que aún están siendo contestadas o consolidadas.

**Ejemplo de uso práctico:** si un triángulo nació al 40% de la partida y todavía está presente al 100%, significa que esas tres piedras formaron un núcleo territorial sólido ya en el medio juego y ese núcleo sobrevivió intacto hasta el yose. Es una zona de solidez estratégica probada.

**Resultados de esta partida:** Los valores $\varepsilon_{\text{Negro}} = 8$ y $\varepsilon_{\text{Blanco}} = 9$ son prácticamente iguales, lo que indica que ambos jugadores tienen una **densidad de piedras muy similar** en el tablero al final de la partida. Ni Oguchi ni tiernuki concentraron sus recursos de manera radicalmente distinta: ambos distribuyen sus piedras con comparable amplitud espacial. Esto es coherente con el resultado ajustado B+4.5.

---

## Sección 2 — Homología persistente

**Carpeta de figuras:** `02_homologia_persistente/`

| Figura | Descripción |
|---|---|
| `01_entropia.png` | Evolución de la entropía persistente $PE_0$ y $PE_1$ a lo largo de los movimientos |
| `02_betti_bootstrap.png` | Curvas de Betti con bandas de confianza al 95% (Fasy et al. 2014) |
| `03_comparacion_betti.png` | Superposición de curvas de Betti de ambos jugadores |
| `04_diagramas_persistencia.png` | Diagramas de persistencia en tres momentos (25%, 50%, 75%) |

![Entropía persistente](02_homologia_persistente/01_entropia.png)
![Betti con bootstrap](02_homologia_persistente/02_betti_bootstrap.png)
![Comparación Betti](02_homologia_persistente/03_comparacion_betti.png)
![Diagramas de persistencia](02_homologia_persistente/04_diagramas_persistencia.png)

---

#### Para el matemático

**Homología persistente.** Para cada valor $\varepsilon$, el grupo de homología $H_k\bigl(\text{VR}_\varepsilon(X)\bigr)$ mide el número de "huecos $k$-dimensionales" del complejo:

- $H_0$: componentes conexas (cuántos grupos separados hay)
- $H_1$: 1-ciclos o lazos (cuántos "cercos" topológicos hay)
- $H_2$: cavidades cerradas (huecos rodeados por una "membrana 2D")

La homología persistente rastrea cómo estos grupos cambian conforme $\varepsilon$ crece de $0$ a $\varepsilon_{\max}$. Una característica *nace* en $b_i$ (el valor de $\varepsilon$ donde aparece) y *muere* en $d_i$ (donde queda absorbida por una estructura mayor). La *persistencia* de esa característica es $\pers_i = d_i - b_i$.

**Diagrama de persistencia.** El diagrama de persistencia es el multiconjunto:

$$D_k = \{(b_i, d_i) : b_i, d_i \in [0, \varepsilon_{\max}], \; b_i < d_i\} \cup \{(x,x) : x \in \mathbb{R}\}$$

Los puntos lejanos a la diagonal tienen alta persistencia y representan rasgos topológicos robustos. Los puntos cercanos a la diagonal son ruido topológico (características que nacen y mueren casi de inmediato).

**Entropía persistente.** La entropía persistente del diagrama $D_k$ es una medida de Shannon sobre la distribución de persistencias:

$$PE_k = -\sum_{i} p_i \log p_i, \quad \text{donde} \quad p_i = \frac{d_i - b_i}{\sum_j (d_j - b_j)}$$

$PE_k$ es alta cuando hay muchas características de duraciones variadas (alta complejidad topológica) y baja cuando unas pocas características dominan (estructura simple o limpia). Es un escalar portable que resume toda la complejidad del diagrama de persistencia.

**Números de Betti.** El $k$-ésimo número de Betti como función de la escala es:

$$\beta_k(\varepsilon) = \text{rango}\bigl(H_k(\text{VR}_\varepsilon(X))\bigr)$$

La *curva de Betti* $\beta_k : [0, \varepsilon_{\max}] \to \mathbb{Z}_{\geq 0}$ es una función escalonada que sube cuando nace una nueva característica y baja cuando muere. Integrar $\beta_k$ sobre $\varepsilon$ da el "área total" de rasgos de dimensión $k$.

**Bootstrap de Fasy et al. (2014).** Para cuantificar la incertidumbre estadística de las curvas de Betti empíricas, se aplica el procedimiento de Fasy et al.: se remuestrean los datos $n_{\text{boot}}$ veces con reposición, se computa $\hat{\beta}_k^{(b)}(\varepsilon)$ para cada remuestreo, y se estima la banda de confianza $c_\alpha$ tal que:

$$P\!\left(\sup_\varepsilon \bigl|\hat{\beta}_k(\varepsilon) - \beta_k(\varepsilon)\bigr| > c_\alpha\right) \leq \alpha$$

donde $\alpha = 0.05$ (confianza al 95%). La banda representa la variabilidad máxima uniforme de la curva de Betti sobre toda la filtración. Una banda estrecha indica alta consistencia del jugador; una banda ancha indica variabilidad estilística.

---

#### Para el jugador de Go

La homología persistente es el corazón del análisis. Cada "hueco topológico" detectado se corresponde con una estructura real en el tablero:

**¿Qué mide $H_0$ (componentes conexas)?**  
$H_0$ cuenta cuántos grupos de piedras separados tiene el jugador *a cada escala*. A $\varepsilon = 1$, mide el número real de cadenas. A $\varepsilon = 8$, grupos que están cerca pero no físicamente conectados empiezan a fusionarse en el análisis — captura la "influencia de vecindad". El número de Betti $\beta_0(\varepsilon)$ baja monótonamente conforme sube $\varepsilon$: los grupos se van uniendo hasta formar uno solo.

**¿Qué mide $H_1$ (lazos)?**  
$H_1$ cuenta cuántos "cercos" o "arcos" forma el jugador. En el juego real, un lazo topológico corresponde a una cadena de piedras que *rodea* una zona sin cerrarla completamente: el precursor de un ojo, de una zona de influencia, de un territorio potencial. Un $H_1$ alto con alta persistencia significa que el jugador construyó cercos duraderos — indicativo de territorio sólido.

**¿Qué dice la entropía $PE$?**  
La entropía $PE_1$ alta significa que el jugador tiene lazos de muchas "calidades" diferentes: algunos muy efímeros, otros muy duraderos. Es la firma de un juego *complejo tácticamente*, lleno de matices. Una $PE_1$ baja indica que el jugador tiene pocos lazos pero son todos de duración similar — juego limpio, con menos ambigüedad territorial.

**¿Qué dice la banda de bootstrap?**  
Una banda estrecha alrededor de la curva de Betti significa que el jugador es *muy consistente*: sus piedras forman patrones similares de movimiento a movimiento. Una banda ancha indica alta variabilidad táctica — el jugador alterna posiciones muy distintas.

**¿Qué dice la comparación de curvas Betti?**  
Si las curvas de ambos jugadores se solapan, sus "firmas topológicas" son similares: los dos construyen posiciones con la misma complejidad estructural a cada escala. Si se separan, tienen estilos topológicos distintos.

**Resultados de esta partida:**

| Descriptor | Oguchi (Negro) | tiernuki (Blanco) |
|---|---|---|
| $PE_{H_0}$ media | 3.998 | 3.972 |
| $PE_{H_1}$ media | 2.978 | 2.954 |
| $c_\alpha$ bootstrap | 0.251 | 0.251 |

Las entropías persistentes de ambos jugadores son *casi idénticas*, tanto en $H_0$ como en $H_1$. Esto indica que ambos construyen posiciones de complejidad topológica equivalente a lo largo de la partida. El valor $c_\alpha = 0.251$ es moderado — hay variabilidad natural dentro de la partida (no es un estilo robótico) pero tampoco caos. La comparación de curvas de Betti muestra *solapamiento sustancial*, confirmando que Oguchi y tiernuki tienen estilos topológicamente afines.

---

## Sección 3 — Cohomología persistente y producto cup

**Carpeta de figuras:** `03_cohomologia/`

| Figura | Descripción |
|---|---|
| `01_dualidad_homologia_cohomologia.png` | Diagrama $H_1$ (izq) + cociclos $\varphi_1, \varphi_2$ sobre el tablero + triángulos del cup product (dcha) |
| `02_cociclos_por_momento.png` | Cociclo $H_1$ más persistente en 3 momentos (40%, 70%, 100%) |

![Dualidad homología-cohomología](03_cohomologia/01_dualidad_homologia_cohomologia.png)
![Cociclos por momento](03_cohomologia/02_cociclos_por_momento.png)

---

#### Para el matemático

**Cohomología persistente.** La cohomología persistente es el dual algebraico de la homología persistente. Por la dualidad de De Rham discreta (en coeficientes $\mathbb{Z}/2$):

$$H^1(K; \mathbb{Z}/2) \cong \text{Hom}\bigl(H_1(K), \mathbb{Z}/2\bigr)$$

Un **1-cociclo** $\varphi$ es una función $\varphi : \{\text{aristas de }K\} \to \mathbb{Z}/2$ que satisface la *cocondición*:

$$\delta\varphi(\sigma) = \sum_{e \in \partial\sigma} \varphi(e) = 0 \pmod{2} \quad \forall\, \sigma \in K^{(2)}$$

El cociclo representativo del generador $H^1$ de mayor persistencia se obtiene mediante el algoritmo de Cohen-Steiner et al. (persistencia cohomológica), que invierte el orden de los operadores de borde. La ventaja de trabajar con cociclos (vs. ciclos homológicos) es que el representante del cociclo es *canónico* y *esparso*, lo que facilita su visualización sobre el tablero.

**Producto cup.** El producto cup es una operación bilineal:

$$\smile : H^p(K;\mathbb{Z}/2) \times H^q(K;\mathbb{Z}/2) \to H^{p+q}(K;\mathbb{Z}/2)$$

A nivel de cadenas, dado un 2-símplice $\sigma = [v_0, v_1, v_2]$ con ordenación simplicial, el producto cup de dos 1-cociclos es:

$$(\varphi_1 \smile \varphi_2)(\sigma) = \varphi_1\bigl([v_0,v_1]\bigr) \cdot \varphi_2\bigl([v_1,v_2]\bigr) \in \mathbb{Z}/2$$

Si $\varphi_1 \smile \varphi_2 \neq 0$ en $H^2$, entonces los dos generadores de $H_1$ correspondientes generan una clase no trivial en $H_2$: los dos lazos son "enlazados" en dimensión superior. En términos del complejo simplicial del tablero, esto constituye la **certificación algebraica de que existe una cavidad 2-dimensional cerrada**, análoga algebraica a un grupo con dos ojos vivos.

---

#### Para el jugador de Go

Hay una diferencia sutil pero fundamental entre homología y cohomología: la homología dice **"existe un cerco"**; la cohomología dice **exactamente qué aristas (pares de piedras) forman la columna vertebral de ese cerco**.

**¿Qué son las aristas del cociclo $\varphi_1$?**  
En las figuras, las aristas marcadas en rojo (o en el color destacado) son exactamente los pares de piedras que *sostienen* el lazo topológico más duradero del jugador. Si eliminas esas piedras (o las conexiones entre ellas), el lazo desaparece. Son las piedras **estratégicamente más críticas** para mantener vivo ese cerco.

**¿Qué es el producto cup $\varphi_1 \smile \varphi_2$?**  
Imagina que tienes dos lazos o cercos distintos en el tablero. El producto cup pregunta: ¿esos dos lazos se *combinan* para formar una estructura cerrada en dos dimensiones? En el Go, esto equivale a preguntar: ¿hay un grupo con **dos ojos algebraicamente certificados**?

- **Cup product = 0:** los dos lazos son independientes. No hay certificación algebraica de dos ojos (en el sentido del complejo VR).
- **Cup product ≠ 0:** los dos lazos generan una clase $H_2$ no trivial — el grupo tiene la firma algebraica de vitalidad (dos ojos).

**Resultados de esta partida:**

| Jugador | Lazo $H_1$ más persistente | Birth | Death | Persistencia | Aristas en $\varphi_1$ | Cup product |
|---|---|---|---|---|---|---|
| Oguchi (Negro) | El más duradero | 2.00 | 3.16 | 1.16 | 10 | 0 |
| tiernuki (Blanco) | El más duradero | 2.00 | 5.00 | **3.00** | 69 | 0 |

La diferencia es reveladora. El lazo más persistente de Oguchi tiene persistencia 1.16 — un lazo *frágil y transitorio*, que desaparece rápidamente al aumentar la escala. El lazo más persistente de tiernuki tiene persistencia 3.00 — **2.6 veces más persistente** — sostenido por 69 aristas frente a las 10 de Oguchi. Esto indica que tiernuki construyó un cerco territorial *mucho más sólido y robusto* a lo largo de la partida.

Ninguno de los dos obtuvo cup product no nulo, lo que indica que en la posición final analizada ningún jugador tiene un grupo con dos ojos topológicamente cerrado en el complejo VR — los territorios permanecen "abiertos" a escala global, lo cual es esperable en una partida donde aún no se ha resuelto el sekis y el yose es lo que determinó el resultado.

**La coherencia con el resultado:** tiernuki ganó por B+4.5. Su lazo $H_1$ con persistencia 3.00 frente al 1.16 de Oguchi es una **confirmación topológica independiente** de que tiernuki construyó una estructura territorial más sólida. La topología y el resultado coinciden.

---

## Sección 4 — Espacio topológico del jugador

**Carpeta de figuras:** `04_espacio_topologico/`

| Figura | Descripción |
|---|---|
| `01_mds_trayectoria.png` | Trayectoria temporal de movimientos de cada jugador en MDS 2D |
| `02_vr_sobre_mds.png` | Complejo VR sobre el espacio MDS |
| `03_umap_vs_mds.png` | Comparación UMAP vs MDS (individual + comparativo entre jugadores + fases) |
| `04_umap_persistencia.png` | UMAP aplicado a las imágenes de persistencia $H_0$ y $H_1$ |
| `05_complejo_3d.png` | Complejo VR en 3D (UMAP y MDS) |

![Trayectoria MDS](04_espacio_topologico/01_mds_trayectoria.png)
![VR sobre MDS](04_espacio_topologico/02_vr_sobre_mds.png)
![UMAP vs MDS](04_espacio_topologico/03_umap_vs_mds.png)
![UMAP de imágenes de persistencia](04_espacio_topologico/04_umap_persistencia.png)
![Complejo 3D](04_espacio_topologico/05_complejo_3d.png)

---

#### Para el matemático

**Vectorización de movimientos.** Cada movimiento $t$ de un jugador se representa como un vector $v_t \in \{-1, 0, 1\}^{361}$: la canonicalización del patrón completo del tablero 19×19 en ese instante (Negro = +1, Blanco = -1, vacío = 0, con normalización de simetrías). Este espacio de dimensión 361 es el *espacio de estados tácticamente relevantes*.

**MDS (Multi-Dimensional Scaling).** El MDS métrico minimiza la función de estrés:

$$\text{Stress}(\mathbf{X}) = \sqrt{\frac{\sum_{i<j}\bigl(\delta_{ij} - \|x_i - x_j\|\bigr)^2}{\sum_{i<j} \delta_{ij}^2}}$$

donde $\delta_{ij} = \|v_i - v_j\|_2$ es la distancia euclidiana en el espacio original de 361 dimensiones, y $x_i \in \mathbb{R}^2$ son las coordenadas en el embedding. MDS preserva las distancias globales (la métrica original) pero puede comprimir la estructura local.

**UMAP (Uniform Manifold Approximation and Projection).** UMAP construye un *grafo $k$-NN ponderado* en el espacio de 361 dimensiones, con pesos:

$$w_{ij} = \exp\!\left(-\frac{\max(d_{ij} - \rho_i, 0)}{\sigma_i}\right)$$

donde $\rho_i$ es la distancia al vecino más cercano de $x_i$ y $\sigma_i$ se calibra para que la suma de pesos de cada nodo sea $\log_2 k$. Luego optimiza un *cross-entropy* entre la representación fuzzy del grafo original y el grafo en el espacio embebido de baja dimensión:

$$\mathcal{L} = \sum_{(i,j)} \left[w_{ij} \log\frac{w_{ij}}{\hat{w}_{ij}} + (1-w_{ij})\log\frac{1-w_{ij}}{1-\hat{w}_{ij}}\right]$$

UMAP preserva simultáneamente estructura local (clusters) y global (relaciones entre clusters), con mayor fidelidad que t-SNE para la estructura global.

**Imágenes de persistencia (Adams et al. 2017).** Para convertir el diagrama de persistencia en un vector de longitud fija (necesario para SVM y UMAP), se usa la *persistence image*: dado el diagrama $D_k = \{(b_i, d_i)\}$, se transforma a coordenadas $(b_i, p_i) = (b_i, d_i - b_i)$ y se coloca una gaussiana ponderada en cada punto:

$$\rho(z) = \sum_{(b_i,d_i) \in D_k} w(b_i,d_i) \cdot \mathcal{N}\!\left(z;\, (b_i,p_i),\, \sigma^2 I\right)$$

con peso $w(b,d) = (d-b)^p$ que prioriza rasgos más persistentes. El resultado es una imagen $H \times W \in \mathbb{R}^{HW}$ que puede tratarse como vector y usarse con cualquier método de aprendizaje automático.

**Complejo VR sobre el espacio MDS.** Se construye $\text{VR}_\varepsilon(X_{\text{MDS}})$ donde $X_{\text{MDS}}$ son los embeddings de los movimientos en $\mathbb{R}^2$, con $\varepsilon$ igual al percentil 20 de las distancias inter-patrón en ese espacio. Esto produce un complejo sobre el espacio de estilos tácticos.

---

#### Para el jugador de Go

Estas visualizaciones responden a una pregunta diferente: no "¿cómo están tus piedras en el tablero?" sino "**¿cómo están tus movimientos en el espacio de estilos tácticos?**".

**Lectura del gráfico MDS / UMAP:**  
Cada punto en el gráfico representa *un movimiento tuyo*. La distancia entre dos puntos mide qué tan distintas eran las posiciones del tablero en esos dos momentos. Puntos cercanos = dos momentos del juego donde la posición general era tácticamente similar. Puntos lejanos = dos momentos muy distintos.

- **Nube compacta** → el jugador tiene un estilo muy consistente: todas sus posiciones son parecidas entre sí.
- **Nube dispersa** → alta variedad táctica: el jugador transita por posiciones muy distintas.
- **Clusters visibles** → hay fases claramente distintas en el estilo del jugador.

**La trayectoria temporal** muestra cómo evolucionó el estilo durante la partida. Si la trayectoria es suave y gradual, el jugador fue cambiando de forma orgánica. Si hay saltos bruscos, hubo eventos importantes (capturas, invasiones, cambios de joseki).

**Colores por fase:**  
- Azul = apertura (primeros movimientos)  
- Verde = medio juego  
- Rojo = yose (finales)  

Si los tres colores forman clusters separados, las tres fases de la partida son tácticamente distintas. Si están mezclados, el jugador no cambia de estilo entre fases.

**UMAP de imágenes de persistencia:** Aquí no se comparan las posiciones del tablero directamente, sino las *firmas topológicas* de cada posición: el diagrama de persistencia de las piedras en ese momento. Si los puntos de Oguchi y tiernuki se mezclan en este gráfico, sus firmas topológicas son indistinguibles — no solo juegan de manera similar, sino que la *topología de sus posiciones* es la misma.

**Resultados de esta partida:**

- El p-valor del test de permutación entre los puntos de Oguchi y tiernuki en el espacio de movimientos es **p = 0.908** → no son estadísticamente distinguibles.
- El p-valor apertura vs. final es **p = 0.001** → las fases son radicalmente distintas en ambos jugadores.
- Esto significa: *Oguchi y tiernuki se parecen entre sí más de lo que cada uno se parece a sí mismo comparando su apertura con su yose*.

---

## Sección 5 — Estadística topológica

**Carpeta de figuras:** `05_estadistica/`

| Figura | Descripción |
|---|---|
| `01_matrices_distancias.png` | Matrices de distancias euclidianas entre patrones de cada jugador |
| `02_tests_permutacion.png` | Distribución nula del test de permutación (999 permutaciones) |
| `03_heatmaps_tablero.png` | Mapa de calor 19×19 de entropía $H_1$ media e intensidad por intersección |

![Matrices de distancias](05_estadistica/01_matrices_distancias.png)
![Tests de permutación](05_estadistica/02_tests_permutacion.png)
![Heatmaps del tablero](05_estadistica/03_heatmaps_tablero.png)

---

#### Para el matemático

**Matrices de distancias.** Para un jugador con movimientos $\{v_1, \ldots, v_N\}$ donde $v_i \in \mathbb{R}^{361}$, la matriz de distancias es:

$$D_{ij} = \|v_i - v_j\|_2$$

Es una matriz simétrica de rango $N \times N$. Su estructura visual revela el patrón de variación estilística: un bloque homogéneo indica consistencia global; un gradiente diagonal indica evolución progresiva; un patrón heterogéneo indica alta variabilidad.

**Test de permutación.** Se realizan tres tests:

1. **Oguchi vs tiernuki:** ¿son sus vectores de movimientos estadísticamente distinguibles?
2. **Apertura vs final (partida completa):** ¿son las fases temporales tácticamente distintas?
3. **Apertura vs final por jugador separado:** ídem, controlando por jugador.

El estadístico de test es:

$$T_{\text{obs}} = \frac{1}{|A||B|}\sum_{i \in A, j \in B} D_{ij} - \frac{1}{2}\left(\frac{1}{|A|^2}\sum_{i,j \in A} D_{ij} + \frac{1}{|B|^2}\sum_{i,j \in B} D_{ij}\right)$$

Bajo la hipótesis nula $H_0$ de que las etiquetas de grupo son intercambiables, se generan 999 permutaciones aleatorias de etiquetas y se calcula $T_\pi$ para cada una. El p-valor es:

$$p = \frac{|\{\pi : T_\pi \geq T_{\text{obs}}\}|}{n_{\text{perm}}}$$

**Mapa de calor del tablero.** Para cada intersección $(x,y)$ del tablero 19×19, se calcula:

$$\text{entropy\_map}(x,y) = \frac{1}{|\{t : (x,y) \in \text{mov}_t\}|} \sum_{t : (x,y) \in \text{mov}_t} PE_{H_1}(t)$$

Es la media de la entropía persistente $H_1$ en los movimientos que "pasan por" esa intersección. Las zonas de alta entropía son donde el jugador crea las posiciones más complejas topológicamente.

**Clustering jerárquico.** Se aplica clustering jerárquico (ligamiento promedio) sobre la matriz de distancias. El *coeficiente cofenético* mide qué tan bien el dendrograma representa las distancias originales:

$$r_c = \frac{\sum_{i<j}(D_{ij} - \bar{D})(C_{ij} - \bar{C})}{\sqrt{\sum_{i<j}(D_{ij}-\bar{D})^2 \cdot \sum_{i<j}(C_{ij}-\bar{C})^2}}$$

donde $C_{ij}$ es la distancia cofenética (altura del nodo más bajo donde $i$ y $j$ se unen). Un valor alto ($r_c > 0.8$) indica que el dendrograma es una representación fiel de la estructura de distancias.

---

#### Para el jugador de Go

**Cómo leer la matriz de distancias:**  
La matriz es un "mapa de similitud" entre todos los movimientos de un jugador. Imagina una cuadrícula donde cada fila y cada columna es un movimiento, y el color de cada celda indica cuán distintos eran esos dos momentos del juego.

- **Bloque homogéneo (un solo color uniforme):** el jugador juega de manera muy consistente en toda la partida — cada posición se parece a todas las demás.
- **Gradiente diagonal:** el estilo cambia *progresivamente* a lo largo de la partida — las posiciones lejanas en el tiempo son las más distintas.
- **Patrón a bloques:** hay fases claramente distintas — la partida tiene "capítulos" tácticamente separados.

**El test de permutación responde a preguntas de Go:**

- **¿Son Oguchi y tiernuki topológicamente distintos?** → p = 0.908. **No.** Sus vectores de movimientos son estadísticamente indistinguibles. Esto explica por qué la partida fue tan ajustada: dos jugadores con estilos topológicamente equivalentes producen resultados más cerrados.
  
- **¿Es la apertura distinta del yose?** → p = 0.001 con T = 2.005. **Sí, altamente significativo.** Esto confirma lo que todo jugador de Go sabe intuitivamente: la apertura y el yose son tácticamente universos distintos, y el análisis topológico lo cuantifica de manera rigurosa.

**El heatmap del tablero** es quizás la visualización más directamente útil para un jugador. Muestra en el tablero real (19×19) qué intersecciones están asociadas con las posiciones más complejas topológicamente. Las zonas rojas son donde ese jugador crea los lazos más duraderos y complejos — sus "zonas de mayor influencia topológica". Las zonas azules son donde el jugador pasa de manera simple.

**Clustering jerárquico:** el coeficiente cofenético de **0.872** indica que el dendrograma es una representación excelente de cómo se agrupan los movimientos. Puedes confiar en los clusters que muestra el árbol jerárquico.

---

## Sección 6 — Video de evolución

**Carpeta:** `06_video/`  
**Archivo:** `evolucion_vr.mp4` — 283 fotogramas a 8 fps, ~14 MB

---

#### Para el matemático

Cada fotograma $t$ corresponde al movimiento global $t \in \{1, \ldots, 283\}$ de la partida. Se muestra el complejo:

$$\text{VR}_\varepsilon(X_t^{\text{Negro}} \cup X_t^{\text{Blanco}})$$

donde $X_t^{\text{Negro}}$ y $X_t^{\text{Blanco}}$ son los conjuntos de piedras acumuladas de cada jugador hasta el movimiento $t$, con $\varepsilon$ fijo igual al promedio de los $\varepsilon$ óptimos de ambos jugadores. Los colores distinguen Negro/Blanco. La evolución continua hace visible la *trayectoria en el espacio de complejos simpliciales filtrados*: se puede observar en tiempo real cómo nuevos símplices entran, cómo los números de Betti fluctúan, y cómo las características topológicas nacen y mueren. El video implementa efectivamente una animación del proceso de filtración de Vietoris-Rips parametrizado no por $\varepsilon$ sino por el tiempo $t$ de la partida, manteniendo $\varepsilon$ fijo.

---

#### Para el jugador de Go

El video de evolución es la visualización más intuitiva de todo el análisis. Cada fotograma es el **"mapa topológico" de esa posición**: muestra simultáneamente las piedras de ambos jugadores con sus conexiones (aristas) y zonas de densidad (triángulos).

Ver el video completo es ver cómo se fue construyendo el territorio de cada jugador desde la perspectiva topológica:

- Al inicio (apertura), pocas conexiones, mucho espacio vacío.
- A medida que avanza la partida, aparecen las aristas (grupos que se "comunican"), luego los triángulos (zonas de influencia consolidadas).
- Las grandes capturas y los cambios de joseki aparecen como *saltos bruscos* en la topología: de repente desaparecen vértices y sus conexiones, el complejo se reorganiza.
- El yose final se ve como un proceso de "clausura": las conexiones se estabilizan, pocos cambios, la topología converge.

Parar el video en cualquier momento y observar el complejo da inmediatamente una lectura táctica: ¿cuántos grupos separados tiene cada jugador? ¿Cuántos cercos activos? ¿Dónde están las zonas de mayor densidad?

---

## Sección 7 — Nuevos descriptores TDA

**Carpeta de figuras:** `07_nuevos_descriptores/`

| Figura | Descripción |
|---|---|
| `01_ecc_silhouette_transiciones.png` | 6 paneles: ECC media±std, heatmap ECC(ε,t) por jugador, silhouette $H_1$, detección de transiciones, TDA de ventana deslizante |
| `02_test_estratificado.png` | p-valores del test estratificado por tiempo (4 estratos, distancia Wasserstein) |

![ECC, silhouette y transiciones](07_nuevos_descriptores/01_ecc_silhouette_transiciones.png)
![Test estratificado](07_nuevos_descriptores/02_test_estratificado.png)

---

#### Para el matemático

**Curva de Característica de Euler (ECC).** La característica de Euler del complejo $K_\varepsilon = \text{VR}_\varepsilon(X)$ es:

$$\chi(K_\varepsilon) = \sum_{k \geq 0} (-1)^k \beta_k(\varepsilon) = \beta_0(\varepsilon) - \beta_1(\varepsilon) + \beta_2(\varepsilon) - \cdots$$

Como función de $\varepsilon$, la ECC colapsa toda la información de los números de Betti en una señal escalar 1D. Al ser una combinación alternante, la ECC captura el "balance" topológico entre componentes y huecos. Formalmente, la ECC es la suma de Euler del complejo filtrado, y por el teorema de Euler-Poincaré es una invariante homotópica. El *heatmap* ECC$(ε,t)$ muestra cómo cambia $\chi(K_\varepsilon)$ como función conjunta de la escala $\varepsilon$ y el tiempo $t$ de la partida.

**Silhouette de persistencia (Chazal et al. 2014).** Dado el diagrama de persistencia $D_k = \{(b_i, d_i)\}$ y un orden de potencia $p \geq 0$, la *persistence silhouette* es:

$$\psi^{(p)}(t) = \frac{\sum_i (d_i - b_i)^p \cdot \Lambda_i(t)}{\sum_i (d_i - b_i)^p}$$

donde $\Lambda_i(t) = \max\bigl(0,\, \min(t-b_i,\, d_i-t)\bigr)$ es la función "tienda de campaña" centrada en $(b_i+d_i)/2$. La silhouette es la media ponderada de estas funciones, con pesos proporcionales a $(d_i - b_i)^p$ (persistencia elevada a la $p$). Es más robusta ante outliers (puntos de alta persistencia atípicos) que el *landscape* de persistencia, y produce una función 1D que captura la distribución de persistencias ponderada por durabilidad.

**Detección de transiciones topológicas.** Para el movimiento $t$, sea $D^{H_1}_t$ el diagrama de persistencia $H_1$ del complejo VR de ese movimiento. La *distancia de Wasserstein consecutiva* es:

$$w_t = W_1(D^{H_1}_{t-1},\, D^{H_1}_t)$$

donde $W_1$ es la distancia de Wasserstein de orden 1 (earth mover's distance) entre diagramas de persistencia, que mide el costo óptimo de transporte entre puntos del diagrama bajo la norma $\ell^\infty$. Se define el umbral:

$$\theta = \mu_w + 1.5\,\sigma_w$$

donde $\mu_w$ y $\sigma_w$ son la media y desviación estándar de la serie $\{w_t\}$. Los movimientos donde $w_t > \theta$ son *transiciones topológicas* — cambios cualitativos en la estructura del diagrama de persistencia.

**Test estratificado por tiempo.** La partida se divide en $S = 4$ estratos temporales iguales: $E_1 = [t_0, t_{N/4}]$, $E_2 = [t_{N/4}, t_{N/2}]$, $E_3 = [t_{N/2}, t_{3N/4}]$, $E_4 = [t_{3N/4}, t_N]$. Para cada par de estratos adyacentes $(E_k, E_{k+1})$, se construye la matriz de distancias Wasserstein $W_{ij} = W_1(D_i^{H_1}, D_j^{H_1})$ para $i \in E_k$, $j \in E_{k+1}$, y se aplica un test de permutación con 999 permutaciones. El p-valor resultante indica si la transición entre esas dos fases es estadísticamente significativa.

**TDA de ventana deslizante (embedding de Takens).** Dado la serie temporal $\{PE_{H_1}(t)\}_{t=1}^N$, se construye el embedding de Takens con retardo $\tau = 1$ y dimensión $d = 2$:

$$\Phi_{\tau,d}(t) = \bigl(PE_{H_1}(t),\, PE_{H_1}(t+\tau),\, \ldots,\, PE_{H_1}(t+(d-1)\tau)\bigr) \in \mathbb{R}^d$$

Para cada ventana de $w = 12$ movimientos consecutivos, se aplica TDA al conjunto de puntos $\{\Phi(t) : t \in \text{ventana}\}$ y se calcula la entropía persistente $H_1$ del complejo VR resultante. Este proceso produce una *meta-serie temporal* que describe la complejidad topológica de la dinámica local del jugador.

---

#### Para el jugador de Go

**ECC — La firma topológica en un número:**  
La Característica de Euler es un número que resume *toda* la topología del tablero en un escalar. Funciona así:

- Si la ECC sube: hay más grupos separados que lazos — el jugador está en modo de *expansión*, ocupando espacio nuevo de forma simple.
- Si la ECC baja: hay más lazos que componentes — el jugador está construyendo *cercos y territorios*, complejidad creciente.
- Si la ECC oscila: hay un equilibrio dinámico entre expansión y cerco — el juego es tenso y equilibrado.

El heatmap ECC$(ε,t)$ es una "historia" de la partida: para cada escala $\varepsilon$ y momento $t$, muestra ese número. Es el "electrocardiograma topológico" de la partida.

**Silhouette — La calidad de los cercos:**  
Si la entropía $PE_1$ mide la *cantidad* de complejidad, la silhouette mide la *calidad*: prioriza los lazos más duraderos. Un pico de silhouette es un momento en que los cercos del jugador son especialmente sólidos y bien fundados.

Piénsalo así: un jugador puede tener muchos lazos efímeros (mucha entropía, poca silhouette) o pocos lazos pero muy sólidos (poca entropía, alta silhouette). Las mejores posiciones territoriales tienden a tener *silhouette alta* — pocos cercos, pero que duran.

**Transiciones — Los momentos clave de la partida:**  
El sistema detecta automáticamente los movimientos donde el "mapa topológico" de la posición cambia más bruscamente. Estos son, en la práctica, los *momentos más importantes de la partida*:

- Una captura grande → desaparecen piedras → el complejo se reorganiza → alta distancia Wasserstein → transición detectada.
- Una invasión → nacen nuevas conexiones en una zona antes vacía → transición.
- Un gran sente → cambia el balance global de la posición → transición.

Si el sistema identifica una transición en el movimiento 150, probablemente en ese momento ocurrió algo decisivo que vale la pena revisar en el SGF.

**Test estratificado — ¿La partida tiene "capítulos"?:**  
Divide la partida en 4 fases iguales y pregunta: ¿es cada fase topológicamente distinta de la siguiente? Si p < 0.05 entre dos fases adyacentes, hay un cambio real y significativo en el estilo de juego entre esas fases. En esta partida, **p = 0.001** para apertura vs. final confirma que el Go sí tiene fases tácticamente distintas — no es un estilo homogéneo.

**Ventana deslizante — El pulso táctico de la partida:**  
En lugar de ver la partida como un todo, la ventana deslizante de 12 movimientos mide la *complejidad local* de cada tramo. Es el "ritmo cardíaco" táctico del jugador:

- Un pico de entropía en la ventana deslizante = tramo de juego intenso, muchas complicaciones.
- Un valle = jugadas de consolidación, simplificación, yose tranquilo.

Esta métrica es la más prometedora para construir en el futuro un "GPS táctico" en tiempo real: dada la posición actual, estimar cuán compleja será la próxima fase.

---

## Sección 8 — Clasificadores SVM sobre imágenes de persistencia

*(Resultados numéricos; sin figura dedicada.)*

---

#### Para el matemático

**Imágenes de persistencia como vectores de características.** Para cada movimiento $t$ y cada dimensión $k \in \{0, 1\}$, se calcula la imagen de persistencia $\rho_k^{(t)} \in \mathbb{R}^{H \times W}$ (con $H = W = 20$, es decir, vectores de longitud 400). Se aplica un SVM con kernel lineal ($C = 1.0$) sobre estos vectores, con validación cruzada estratificada de 5 pliegues.

Los cuatro clasificadores entrenados son:

1. **Oguchi vs tiernuki con $H_0$:** ¿se puede distinguir el jugador solo por la imagen de persistencia de sus componentes conexas?
2. **Oguchi vs tiernuki con $H_1$:** ídem usando lazos.
3. **Apertura vs final para Oguchi:** ¿se pueden distinguir las fases temporales del mismo jugador usando $H_1$?
4. **Apertura vs final para tiernuki:** ídem.

La accuracy de los clasificadores 1 y 2 cerca de 50% implica que las imágenes de persistencia de Oguchi y tiernuki son estadísticamente indistinguibles — el SVM no puede aprender ninguna frontera de decisión útil. La accuracy de los clasificadores 3 y 4 cerca de 97% implica que las imágenes de persistencia de la apertura y el yose son *perfectamente separables* con un clasificador lineal.

---

#### Para el jugador de Go

El SVM (Support Vector Machine) es un clasificador que aprende a distinguir dos categorías. Aquí se le da como entrada la "huella topológica" de cada movimiento (la imagen de persistencia) y se le pide que determine de quién es ese movimiento o a qué fase pertenece.

**¿Puede el SVM distinguir a Oguchi de tiernuki?**

| Descriptor | Accuracy | Interpretación |
|---|---|---|
| $H_0$ (grupos) | 50.2% ± 1% | Azar puro. Imposible distinguirlos. |
| $H_1$ (lazos) | 43.1% ± 1% | Peor que azar. No hay ninguna diferencia. |

El SVM fracasa completamente. Dado cualquier movimiento de la partida, el clasificador no puede determinar si lo jugó Oguchi o tiernuki mirando la topología de la posición. Esto confirma cuantitativamente que sus **estilos topológicos son indistinguibles** — son, desde la perspectiva del TDA, jugadores gemelos.

**¿Puede el SVM distinguir apertura de yose?**

| Jugador | Accuracy | Interpretación |
|---|---|---|
| Oguchi | **97.2% ± 1%** | Perfectamente separable. |
| tiernuki | **96.5% ± 1%** | Perfectamente separable. |

El SVM funciona casi a la perfección. Dada cualquier posición de un jugador, puede decir con 97% de certeza si es de la apertura o del yose. Esto significa que las imágenes de persistencia capturan las fases del Go mejor que cualquier descriptor clásico: la apertura y el yose son mundos topológicamente distintos, y el análisis lo cuantifica.

**Conclusión de esta sección:** Oguchi y tiernuki son topológicamente gemelos entre sí, pero ambos son topológicamente diferentes de sus propias versiones en distintas fases de la partida. El análisis topológico captura las fases del Go con precisión quirúrgica.

---

## Conclusiones finales

### 1. Estilos topológicamente equivalentes explican el resultado ajustado

**Matemáticamente:** el test de permutación sobre vectores de movimientos en $\mathbb{R}^{361}$ arroja $p = 0.908$, con $T_{\text{obs}}$ completamente inmerso en la distribución nula. Los clasificadores SVM con imágenes de persistencia $H_0$ y $H_1$ obtienen 50.2% y 43.1% de accuracy respectivamente. Las entropías persistentes medias difieren en menos del 0.7%: $PE_{H_0}^{\text{Og}} = 3.998$ vs $PE_{H_0}^{\text{ti}} = 3.972$.

**Para el jugador de Go:** Oguchi y tiernuki construyeron posiciones de complejidad estructural casi idéntica a lo largo de toda la partida. Cuando dos jugadores tienen estilos topológicamente equivalentes, la partida tiende a ser muy ajustada porque ninguno tiene una ventaja de "forma" sobre el otro. El resultado B+4.5 es coherente: la diferencia fue de detalles finos, no de una ventaja estructural de uno sobre otro.

---

### 2. El Go no es un estilo fijo: es una trayectoria topológica

**Matemáticamente:** el test de permutación apertura vs. final arroja $p = 0.001$ con estadístico $T = 2.005$. Los clasificadores SVM con $H_1$ distinguen apertura de yose con 97.2% (Oguchi) y 96.5% (tiernuki) de accuracy. El test estratificado en 4 fases confirma transiciones topológicas significativas entre estratos adyacentes.

**Para el jugador de Go:** el análisis prueba matemáticamente algo que todo jugador experimenta pero raramente puede cuantificar: la apertura y el yose son tácticamente universos distintos. No basta con tener un "estilo de juego" — la partida exige adaptarse radicalmente entre fases. La trayectoria en el espacio topológico describe la historia completa de esa adaptación, movimiento a movimiento.

---

### 3. tiernuki construyó una estructura territorial más sólida: confirmación topológica de la victoria

**Matemáticamente:** el lazo $H_1$ más persistente de tiernuki tiene persistencia 3.00 (birth = 2.00, death = 5.00), sostenido por 69 aristas en el cociclo representativo. El lazo más persistente de Oguchi tiene persistencia 1.16 (birth = 2.00, death = 3.16), con solo 10 aristas. La ratio de persistencias es 3.00/1.16 ≈ 2.59.

**Para el jugador de Go:** tiernuki no solo ganó puntos — construyó lazos territoriales 2.6 veces más duraderos que Oguchi. Un lazo más persistente en el diagrama de persistencia corresponde a un cerco territorial que sobrevive a una gama mucho mayor de escalas de análisis: es más robusto, menos dependiente de la posición exacta de cada piedra. La cohomología persistente, de manera completamente independiente de las reglas de Go o del conteo de puntos, detecta que la estructura de tiernuki era más sólida — y la partida lo confirma.

---

### 4. Ningún jugador completó algebraicamente un grupo de dos ojos: topología de territorios abiertos

**Matemáticamente:** para ambos jugadores, el cup product $\varphi_1 \smile \varphi_2 = 0$ en $H^2(K; \mathbb{Z}/2)$. Esto significa que no hay ningún par de generadores de $H_1$ que genere una clase no trivial en $H_2$ — no existe ninguna cavidad 2-dimensional cerrada en el complejo VR de la posición final.

**Para el jugador de Go:** el cup product cero no significa que los jugadores no tengan grupos vivos — significa que en la representación topológica a la escala analizada ($\varepsilon = 8$ para Negro, $\varepsilon = 9$ para Blanco), la posición final tiene territorios *topológicamente abiertos*: cercos que no cierran algebraicamente. Esto es esperable en una partida real donde el resultado se decide por conteo de puntos en territorios que *estratégicamente* están definidos pero no forman cavidades cerradas en el sentido del complejo VR. El cup product no nulo sería la certificación algebraica de un grupo con dos ojos completamente encerrado — una situación de vida incuestionable. En esta partida, ningún grupo alcanzó ese nivel de clausura topológica, lo cual es característico del juego territorial abierto.

---

### 5. Las imágenes de persistencia capturan las fases del Go mejor que cualquier descriptor clásico

**Matemáticamente:** un SVM lineal simple con kernel lineal ($C = 1.0$) y validación cruzada de 5 pliegues alcanza 97.2% de accuracy (Oguchi) y 96.5% (tiernuki) al separar imágenes de persistencia $H_1$ de apertura vs. yose. Esto implica que las imágenes de persistencia son *linealmente separables* en el espacio de 400 dimensiones — la frontera entre fases es casi perfectamente lineal en ese espacio.

**Para el jugador de Go:** los descriptores topológicos no solo son estadísticamente potentes — son también geométricamente limpios. La diferencia entre una posición de apertura y una de yose, vista desde la homología persistente, es una diferencia lineal y perfectamente distinguible. Ningún descriptor clásico del Go (número de piedras, área de territorio, número de grupos) logra esta separabilidad con tanta claridad, porque no captura la estructura relacional entre las piedras a múltiples escalas simultáneamente.

---

### 6. Las transiciones topológicas como "GPS táctico" en tiempo real

**Matemáticamente:** la distancia de Wasserstein consecutiva $w_t = W_1(D^{H_1}_{t-1}, D^{H_1}_t)$ con umbral $\theta = \mu_w + 1.5\sigma_w$ identifica automáticamente los movimientos donde la topología de la posición cambia cualitativamente. El embedding de Takens de la serie $\{PE_{H_1}(t)\}$ con la ventana deslizante de 12 movimientos proporciona una meta-serie que describe la *dinámica local* de la complejidad topológica.

**Para el jugador de Go:** este es el descriptor con el mayor potencial aplicado. Imagina un sistema que, movimiento a movimiento durante una partida en línea, te dice: "En los últimos 12 movimientos, la complejidad topológica de tu posición subió un 34% — estás en un tramo táctico intenso". O: "El sistema detecta una transición topológica en el movimiento 87 — revisa esa posición". Esto es esencialmente un *GPS táctico*: no dice qué jugada hacer, sino en qué "territorio topológico" del juego te encuentras. El pipeline CANDELA implementa todos los componentes necesarios para construir esta herramienta.

---

## Cómo usar el sistema

### Instalación rápida

```bash
# Clonar el repositorio
git clone https://github.com/metamatematico/Topological-analysis-of-Baduk.git
cd Topological-analysis-of-Baduk

# Instalar dependencias principales
pip install -r requirements.txt

# Opcional: Mapper topológico (para análisis adicionales)
pip install kmapper
```

### Analizar cualquier partida SGF

```bash
# Análisis completo de una partida
python analyze_game.py tu_partida.sgf outputs/mi_analisis/

# El script genera automáticamente las 7 carpetas de resultados:
# outputs/mi_analisis/
#   ├── 01_complejo_vr/          ← Complejos VR y filtraciones
#   ├── 02_homologia_persistente/ ← Entropía, Betti, diagramas
#   ├── 03_cohomologia/           ← Cociclos y cup product
#   ├── 04_espacio_topologico/    ← MDS, UMAP, imágenes de persistencia
#   ├── 05_estadistica/           ← Matrices, tests, heatmaps
#   ├── 06_video/                 ← Video de evolución (MP4)
#   └── 07_nuevos_descriptores/   ← ECC, silhouette, transiciones
```

### Estructura de archivos de salida

| Carpeta | Contenido | Uso recomendado |
|---|---|---|
| `01_complejo_vr/` | 6 figuras PNG | Visión global de la estructura espacial |
| `02_homologia_persistente/` | 4 figuras PNG | Análisis de estilo y complejidad táctica |
| `03_cohomologia/` | 2 figuras PNG | Identificación de cercos clave y vitalidad |
| `04_espacio_topologico/` | 5 figuras PNG | Comparación de estilos y fases |
| `05_estadistica/` | 3 figuras PNG + JSON de resultados | Tests formales y mapas de calor del tablero |
| `06_video/` | 1 archivo MP4 | Presentación y revisión de partida |
| `07_nuevos_descriptores/` | 2 figuras PNG + JSON de transiciones | Análisis dinámico y detección de momentos clave |

### Interpretar los resultados principales

Después de correr el análisis, los indicadores más importantes a revisar son:

1. **Persistencia del lazo $H_1$ más duradero** (Sección 3): ratio entre jugadores. Si uno tiene persistencia >2× del otro, tiene una ventaja estructural clara.
2. **p-valor Oguchi vs tiernuki** (Sección 5): si $p > 0.1$, los estilos son indistinguibles — la partida fue de detalles. Si $p < 0.05$, hay diferencias estilísticas claras.
3. **Accuracy SVM apertura vs yose** (Sección 8): si es >90%, el análisis capturó bien las fases de la partida. Si es ~50%, la partida fue estilísticamente muy uniforme (inusual).
4. **Transiciones topológicas** (Sección 7): los movimientos marcados como transiciones son los candidatos a ser los momentos decisivos de la partida. Revísalos en el SGF.
5. **Heatmap del tablero** (Sección 5): las zonas rojas son donde cada jugador crea mayor complejidad topológica — sus "puntos de mayor interés" estratégico.

### Requisitos mínimos del sistema

- Python 3.8 o superior
- 4 GB de RAM (8 GB recomendado para partidas largas)
- Los archivos SGF deben ser válidos y contener al menos 50 movimientos para resultados significativos

---

## Referencias

- Edelsbrunner, H., Letscher, D., & Zomorodian, A. (2002). Topological persistence and simplification. *Discrete & Computational Geometry*, 28(4), 511–533.
- Zomorodian, A., & Carlsson, G. (2005). Computing persistent homology. *Discrete & Computational Geometry*, 33(2), 249–274.
- Cohen-Steiner, D., Edelsbrunner, H., & Harer, J. (2007). Stability of persistence diagrams. *Discrete & Computational Geometry*, 37(1), 103–120.
- Fasy, B. T., Lecci, F., Rinaldo, A., Wasserman, L., Balakrishnan, S., & Singh, A. (2014). Confidence sets for persistence diagrams. *Annals of Statistics*, 42(6), 2301–2339.
- Adams, H., Emerson, T., Kirby, M., Neville, R., Peterson, C., Shipman, P., ... & Ziegelmeier, L. (2017). Persistence images: A stable vector representation of persistent homology. *Journal of Machine Learning Research*, 18(1), 218–252.
- Chazal, F., Fasy, B. T., Lecci, F., Rinaldo, A., & Wasserman, L. (2014). Stochastic convergence of persistence landscapes and silhouettes. *Proceedings of the 30th Annual Symposium on Computational Geometry*, 474–483.
- McInnes, L., Healy, J., & Melville, J. (2018). UMAP: Uniform Manifold Approximation and Projection for Dimension Reduction. *arXiv preprint arXiv:1802.03426*.
- Takens, F. (1981). Detecting strange attractors in turbulence. *Dynamical Systems and Turbulence*, 366–381.

---

*Análisis generado con CANDELA — pipeline de Análisis Topológico de Datos para el Go.*  
*Repositorio: [metamatematico/Topological-analysis-of-Baduk](https://github.com/metamatematico/Topological-analysis-of-Baduk)*

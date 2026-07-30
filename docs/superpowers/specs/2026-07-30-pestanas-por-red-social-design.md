# Pestañas de análisis por red en Social Orgánico

**Fecha:** 30-jul-2026 · **Estado:** aprobado, pendiente de plan de implementación

## Problema

La página de Social Orgánico compara las cuatro redes entre sí, y eso está bien
resuelto. Pero no permite entender **ninguna red por dentro**: no hay contexto
temporal (un número sin el del mes pasado no dice si va bien), no se ve qué
formato funciona, y no hay ni rastro de quién compone la audiencia.

Sin eso, la página responde «cuál va mejor» pero no «qué publico la semana que
viene» ni «le estoy hablando a quien quiero».

## Qué se construye

Cinco pestañas: **Resumen** (la página actual, sin cambios) y una por red. Cada
pestaña de red repite la misma estructura de cinco bloques, con el mismo orden y
los mismos títulos, pero con el contenido que esa red sí puede dar.

La estructura fija es deliberada: hace que las pestañas se puedan comparar de
memoria. El contenido variable también: cada API ofrece cosas distintas y
forzarlas a un molde común significaría o inventar datos o desperdiciar los que
hay.

---

## Restricciones verificadas contra las cuentas reales (30-jul-2026)

No son suposiciones: están sondeadas con credenciales en producción.

### Demografía disponible

| Red | Edad | Género | Ubicación | Unidad |
|---|---|---|---|---|
| **Instagram** | ✅ 6 tramos | ✅ F/M/U | ✅ país + 45 ciudades | personas que siguen |
| **YouTube** | ✅ 6 tramos | ✅ | ✅ país | **% de visualizaciones** |
| **Facebook** | ❌ | ❌ | ❌ | — |
| **LinkedIn** | ❌ no existe | ❌ no existe | ✅ | seguidores |

- **Facebook no tiene demografía.** `page_fans_gender_age`, `page_fans_country`,
  `page_fans_city`, `page_follows_by_age_gender_unique` y
  `page_fans_by_like_source` responden `(#100) The value must be a valid
  insights metric`. Meta las retiró en la misma purga que se llevó impresiones y
  alcance de Página. No hay sustituto.
- **LinkedIn no publica edad ni género** en ninguna versión de su API. Lo que sí
  da son cargo, función, sector, tamaño de empresa y ubicación.
- **YouTube mide otra cosa.** Su demografía es `viewerPercentage`: el porcentaje
  de *visualizaciones* por tramo, no cuántos suscriptores hay de cada edad. Es
  otra población y otra unidad que la de Instagram.

### Volumen de publicaciones

| Red | Publicaciones (12 meses) | Formatos presentes |
|---|---|---|
| Instagram | 10 | Reel (10) |
| YouTube | 4 | Short (4) |
| Facebook | 2 → **5 y subiendo** | Publicación |

Hoy es poco, pero **Facebook está en plena subida del histórico atrasado** y va a
seguir creciendo. Por eso el diseño no se ajusta al volumen actual: los umbrales
son dinámicos y los bloques declaran su tamaño de muestra, de forma que las
mismas pestañas ganen densidad solas conforme entren publicaciones, sin tocar
código.

### Métricas por publicación, por red

| | Instagram | YouTube | Facebook | LinkedIn |
|---|---|---|---|---|
| Visualizaciones | ✅ | ✅ | ⚠️ solo vídeo/reels | ✅ |
| Impresiones | ❌ | ❌ | ❌ retiradas | ✅ |
| Likes · comentarios · compartidos | ✅ | ✅ | ✅ | ✅ |
| Guardados | ✅ | ❌ | ❌ | ❌ |
| **Clics** | ❌ | ❌ | ✅ `post_clicks` | ✅ |
| **Reacciones por tipo** | ❌ | ❌ | ⏸️ existe, aplazado | ❌ |

Dos métricas nuevas que hay que añadir al esquema de publicaciones, ambas
verificadas contra la Página real:

- **`clics`** — la publican Facebook y LinkedIn. Es la más cercana a intención
  real que da el orgánico: mide quién quiso saber más, no quién pasó el dedo.
- **`reacciones_por_tipo`** — solo Facebook. Existe y responde, pero devuelve un
  DICCIONARIO, no un número, y el esquema de publicaciones es numérico.
  **Aplazado** (ver Fuera de alcance): con 0 reacciones en toda la Página, tocar
  el esquema no compensa todavía.

Las publicaciones estáticas de Facebook se quedan sin visualizaciones —la API no
las da— así que su casilla va a **nulo**, no a cero. Las de vídeo y reels sí las
traen (`post_video_views`, `blue_reels_play_count`).

### Lo que NO se puede hacer

- **Mejores horarios de publicación.** Los conectores truncan la marca temporal
  a la fecha (`timestamp[:10]`). Es recuperable con un cambio pequeño, pero con
  10 publicaciones el resultado sería ruido. **Queda fuera de este trabajo.**
- **Visualizaciones por publicación en Facebook.** El endpoint de insights de
  post no las devuelve. Su bloque de contenido se apoya en interacciones.

---

## Los cinco bloques de una pestaña de red

### 1 · Titular

Dos o tres frases derivadas del dato, no escritas a mano: métrica principal con
su variación, el mejor resultado del periodo y el punto de atención. Pensado
para copiarse en un correo sin abrir el dashboard.

Se genera con plantillas y datos, nunca con texto libre inventado. Si falta el
dato para una frase, esa frase no aparece.

### 2 · KPIs contra el periodo anterior

Tabla `Métrica · Periodo · Anterior · Δ`.

- El **periodo anterior** es el intervalo de la misma longitud inmediatamente
  antes de `desde`. Para 1–30 de julio, es 1–30 de junio.
- Sale del histórico acumulado (700+ días), así que funciona desde el primer día.
- **Las métricas que esa red no publica no aparecen en su tabla.** No salen en
  gris, ni a cero, ni con guion: no existen para esa red.
- La variación se muestra en % para métricas de flujo y en puntos porcentuales
  para tasas.
- **Si no hay datos del periodo anterior** —histórico que no llega tan atrás—
  las columnas `Anterior` y `Δ` muestran «—» para esa métrica. No se asume cero:
  un cero produciría un crecimiento del infinito por ciento. Si ninguna métrica
  tiene comparativa, la tabla se muestra sin esas dos columnas y con una nota de
  desde cuándo hay histórico.

### 3 · Evolución

El selector de métrica actual, **filtrado con `config.soporta_metrica()`** a lo
que esa red publica. La pestaña de Facebook no ofrecerá «Alcance» ni
«Impresiones»: ofrecer una métrica que siempre saldrá vacía es prometer algo que
no se va a cumplir.

### 4 · Contenido

- **Top 3** y **Bottom 3** por **tasa de engagement**
  (`interacciones / visualizaciones`), no por likes brutos. Ordenar por likes
  hace ganar siempre a la publicación más vista, que es una observación circular:
  «lo que más se vio es lo que más se vio».

  **Excepción de Facebook:** solo sus vídeos y reels traen visualizaciones, así
  que en las publicaciones estáticas no hay denominador y la tasa es nula. Su
  ranking se ordena por **interacciones absolutas**, y el bloque lo dice:
  «ordenado por interacciones; Facebook solo publica visualizaciones en vídeo».
  Nunca se mezclan en un mismo ranking publicaciones ordenadas por criterios
  distintos.

  El día que la mayoría de sus publicaciones sean vídeo, se puede reevaluar;
  el criterio se elige en un solo sitio para que ese cambio sea de una línea.

- **Rendimiento por formato**: Reel vs Carrusel vs Imagen · Short vs Vídeo.
  Es el bloque que responde «qué publico la semana que viene».

- **Listado completo**, ordenable, con **todas** las métricas que esa red
  publica de cada publicación: fecha, formato, título enlazado al original y
  sus métricas. Es la vista de trabajo: la que se mira para encontrar una
  publicación concreta, no para sacar una conclusión. Incluye las métricas que
  solo tiene esa red — guardados en Instagram, clics en Facebook y LinkedIn—,
  porque `config.SOPORTE_METRICA_POST` ya decide cuáles le corresponden.

**Umbral de muestra:** el bloque indica siempre sobre cuántas publicaciones se
calcula. Con menos de **6 publicaciones** en el periodo no se muestra el Bottom 3
—con 2 publicaciones, «la peor» es la segunda— y se dice por qué. El Top se
muestra siempre, recortado al número disponible.

El umbral es una constante en `config`, no un número repartido por el código:
con Facebook subiendo su histórico, el punto en el que estos bloques empiezan a
tener sentido se alcanzará solo, y ajustarlo debe ser cambiar una línea.

**Media por formato:** solo se muestra el formato que tenga al menos 3
publicaciones. Una media de una sola publicación no es una media, y presentarla
junto a otra de doce invita a compararlas como si pesaran igual.

### 5 · Audiencia

| Red | Dimensiones | Unidad declarada en el bloque |
|---|---|---|
| Instagram | edad, género, país, top ciudades | personas que te siguen |
| YouTube | edad, género, país | % de visualizaciones |
| Facebook | — | *aviso de retirada por Meta* |
| LinkedIn | cargo, función, sector, tamaño de empresa, ubicación | seguidores |

**La unidad se escribe dentro del bloque, no en una nota al pie.** Instagram
responde «cuánta gente eres»; YouTube, «qué perfil consume». No son la misma
pregunta y no comparten gráfico ni se suman.

Se muestra **la foto más reciente** disponible en o antes de `hasta`. La deriva
temporal de la audiencia no se dibuja todavía (no hay histórico suficiente); se
empieza a acumular ahora para poder hacerlo más adelante.

---

## Datos nuevos

### Captura

Una función de demografía por red en su conector, siguiendo el patrón existente:

| Red | Fuente |
|---|---|
| Instagram | `/{ig}/insights?metric=follower_demographics&period=lifetime&metric_type=total_value&breakdown={age\|gender\|city\|country}` |
| YouTube | Analytics API v2, `metrics=viewerPercentage&dimensions=ageGroup,gender` y `metrics=views&dimensions=country` |
| LinkedIn | `organizationalEntityFollowerStatistics`, desgloses por seniority, function, industry, staffCountRange y geo |
| Facebook | ninguna — la función no existe |

### Esquema

`data/historico_social/social_<red>_demografia.csv`

| Columna | Contenido |
|---|---|
| `fecha` | día de la captura (la demografía es una foto, no un flujo) |
| `red` | YouTube · Facebook · Instagram · LinkedIn |
| `dimension` | `edad` · `genero` · `pais` · `ciudad` · `cargo` · `funcion` · `sector` · `tamano_empresa` |
| `categoria` | el valor concreto: `45-54`, `F`, `ES`, `Barcelona, Cataluña` |
| `valor` | número |
| `unidad` | `seguidores` · `pct_visualizaciones` |

Clave de fusión: `(fecha, red, dimension, categoria)`. Se acumula con el mismo
`social_base.fusionar` que el resto: celda a celda, y un nulo nuevo nunca pisa un
dato ya capturado.

### Por qué se acumula desde el principio

Es la lección de los seguidores de Instagram: las APIs dan la foto de hoy y el
pasado no se reconstruye. Guardarlo ahora cuesta una tabla; no guardarlo hace
que la pregunta «¿ha cambiado nuestra audiencia?» no tenga respuesta nunca.

`snapshot_social.py` gana una fase de demografía, con la misma regla que ya
tiene: **llama a las funciones de API directamente, nunca a la cascada**, para
que un fallo no pueda escribir datos de ejemplo en el histórico.

---

## Reparto del código

La página tiene ~300 líneas. Añadirle cuatro pestañas de análisis la volvería
inmanejable, así que el trabajo se reparte:

| Módulo | Responsabilidad | Depende de |
|---|---|---|
| `src/connectors/{youtube,meta_organico,linkedin}.py` | traer la demografía cruda de su red | su API |
| `src/data/social_demografia.py` | esquema fijo, normalización, regla de unidades | `config` |
| `src/data/social_analisis.py` | comparativa contra periodo anterior, top/bottom, agregado por formato | `social` |
| `src/ui/social_red.py` | dibujar UNA pestaña de red | `social_analisis`, `social_demografia`, `components` |
| `pages/6_📣_Social_Orgánico.py` | orquestar pestañas | todo lo anterior |

`social_red.py` recibe la red y sus datos y no sabe nada de Streamlit más allá de
pintar; `social_analisis.py` no importa Streamlit en absoluto y se puede probar
con DataFrames sueltos.

## Reglas que no se rompen

Las que ya gobiernan la página, extendidas a lo nuevo:

1. **Nulo ≠ cero.** Una métrica que la red no publica va a NaN y se muestra «—».
   En las pestañas de red, además, directamente no aparece en su tabla de KPIs.
2. **No comparar unidades distintas.** La demografía de YouTube (% de
   visualizaciones) nunca comparte gráfico con la de Instagram (personas).
3. **Decir el tamaño de la muestra.** Todo ranking o media por formato indica
   sobre cuántas publicaciones se calcula.
4. **Nunca datos de ejemplo en el histórico.** El job llama a las funciones de
   API directamente.
5. **Escapar el HTML** de cualquier texto que venga de una API antes de pasarlo
   a `ui.tabla`.

## Cómo se comprueba

- **`social_analisis.py`**: comparativa de periodo con datos sintéticos —
  periodo anterior correcto, división por cero, periodo sin datos previos.
- **`social_demografia.py`**: normalización y regla de unidades; que una unidad
  incompatible no se pueda mezclar.
- **Umbral de muestra**: con 2 publicaciones no aparece Bottom 3; con 6 sí.
- **Página**: `streamlit.testing.AppTest` sobre las 7 páginas, más las 4
  pestañas de red, sin excepciones.
- **Captura real**: ejecutar el job y comprobar contra las cuentas conectadas
  que la demografía entra con las cifras que devuelve la API.

## Fuera de alcance

- **Mejores horarios de publicación** — requiere conservar la hora y hoy el
  volumen no lo justifica.
- **Deriva temporal de la audiencia** — se empieza a acumular ahora; se dibujará
  cuando haya meses que comparar.
- **Demografía de Facebook** — no existe.
- **Edad y género de LinkedIn** — no existen.
- **Desglose de reacciones de Facebook** — `post_reactions_by_type_total`
  funciona, pero es un diccionario y el esquema de publicaciones es numérico.
  Cuando la Página acumule reacciones de verdad, se decide si merece una
  columna propia o un bloque aparte.

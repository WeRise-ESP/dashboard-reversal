# Pestañas de análisis por red — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir a la página de Social Orgánico una pestaña por red con análisis en profundidad: KPIs contra el periodo anterior, evolución, rendimiento de publicaciones y demografía de audiencia.

**Architecture:** Tres módulos nuevos sin Streamlit (`social_analisis`, `social_demografia` y las funciones de demografía de los conectores) que se pueden probar con DataFrames sueltos, más un módulo de UI (`social_red`) que dibuja una pestaña. La página queda como orquestador. La demografía se captura con el job diario y se acumula en `data/historico_social/`, con la misma fusión celda a celda que el resto.

**Tech Stack:** Python 3.14, pandas, Streamlit, Plotly, pytest (nuevo).

**Spec:** [`docs/superpowers/specs/2026-07-30-pestanas-por-red-social-design.md`](../specs/2026-07-30-pestanas-por-red-social-design.md)

## Global Constraints

Estas reglas aplican a TODAS las tareas. Romper una es motivo de rechazo.

- **Nulo ≠ cero.** Una métrica que la red no publica va a `NaN`, nunca a 0. Lo declara `config.SOPORTE_METRICA_SOCIAL` / `SOPORTE_METRICA_POST` y lo impone `src/data/social.py`.
- **En la UI, `num_o_guion` / `pct_o_guion`, nunca `num()`** — `num()` devuelve "0" ante un nulo.
- **Nunca datos de ejemplo en el histórico.** El job llama a las funciones `_api_*` directamente, jamás a `obtener()` ni a `resolver`.
- **`social_analisis.py` y `social_demografia.py` NO importan streamlit.** Es lo que los hace testables.
- **Escapar el HTML** (`html.escape`) de cualquier texto que venga de una API antes de pasarlo a `ui.tabla`, que inyecta sin escapar.
- **No comparar unidades distintas.** La demografía de YouTube (`pct_visualizaciones`) nunca comparte gráfico con la de Instagram (`seguidores`).
- **Comentarios y docstrings en español**, como el resto del repo.
- **Un commit por tarea**, con el mensaje que indica cada una.
- Los tests se ejecutan con `.venv/bin/python -m pytest`.

---

### Task 1: Infraestructura de tests

El repo no tiene pytest ni carpeta de tests. Sin esto no se puede hacer TDD en las tareas siguientes.

**Files:**
- Create: `requirements-dev.txt`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tests/test_infraestructura.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nada
- Produces: `tests/conftest.py` pone la raíz del repo en `sys.path`, de modo que todos los tests posteriores pueden hacer `from src.data import ...`

- [ ] **Step 1: Crear requirements-dev.txt**

Va aparte de `requirements.txt` a propósito: Streamlit Cloud instala el de producción y no tiene por qué cargar pytest.

```
# Dependencias solo de desarrollo. Producción usa requirements.txt.
# Streamlit Cloud NO instala este fichero.
-r requirements.txt
pytest>=8.0
```

- [ ] **Step 2: Crear tests/__init__.py vacío y tests/conftest.py**

`tests/__init__.py` vacío. `tests/conftest.py`:

```python
"""Configuración común de los tests.

Pone la raíz del repo en sys.path para que los tests puedan importar `src.*`
sin instalar el proyecto como paquete.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
```

- [ ] **Step 3: Escribir el test que verifica la infraestructura**

`tests/test_infraestructura.py`:

```python
"""Comprueba que el arnés de tests puede importar el proyecto."""


def test_se_puede_importar_config():
    from src import config
    assert config.REDES_SOCIAL == ("YouTube", "Facebook", "Instagram", "LinkedIn")


def test_los_modulos_de_datos_no_importan_streamlit():
    """`social_analisis` y `social_demografia` deben ser probables sin Streamlit.

    Se comprueba sobre `social.py`, que ya cumple la regla, para que el test
    exista desde el principio y las tareas siguientes lo hereden.
    """
    import subprocess
    import sys

    codigo = (
        "import sys; sys.modules['streamlit'] = None;"
        "from src.data import social; print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
```

- [ ] **Step 4: Instalar y ejecutar**

Run: `.venv/bin/pip install -r requirements-dev.txt && .venv/bin/python -m pytest tests/ -v`
Expected: 2 tests PASS

- [ ] **Step 5: Añadir .pytest_cache al .gitignore**

Añadir al final de la sección "# Python" de `.gitignore`:

```
.pytest_cache/
```

- [ ] **Step 6: Commit**

```bash
git add requirements-dev.txt tests/ .gitignore
git commit -m "test: arnés de pytest para los módulos de datos

El repo no tenía tests. Se añade pytest en requirements-dev.txt, aparte del de
producción para que Streamlit Cloud no lo instale, y un conftest que pone la
raíz en sys.path.

Incluye un test que comprueba que los módulos de datos se pueden importar sin
streamlit: es la propiedad que los hace testables y la que las tareas
siguientes tienen que mantener."
```

---

### Task 2: Constantes de umbral y métrica `clics`

**Files:**
- Modify: `src/config.py` (bloque SOCIAL ORGÁNICO, tras `METRICAS_POST`)
- Test: `tests/test_config_social.py`

**Interfaces:**
- Consumes: nada
- Produces:
  - `config.MIN_PUBLICACIONES_BOTTOM: int = 6`
  - `config.MIN_PUBLICACIONES_FORMATO: int = 3`
  - `config.METRICAS_POST` gana la clave `"clics": "Clics"`
  - `config.SOPORTE_METRICA_POST["clics"] = {"Facebook", "LinkedIn"}`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_config_social.py`:

```python
from src import config


def test_clics_es_metrica_de_publicacion_de_facebook_y_linkedin():
    assert "clics" in config.METRICAS_POST
    assert config.soporta_metrica("clics", "Facebook", "post")
    assert config.soporta_metrica("clics", "LinkedIn", "post")


def test_instagram_y_youtube_no_publican_clics():
    """No los dan por API. Sondeado contra las cuentas reales el 30-jul-2026."""
    assert not config.soporta_metrica("clics", "Instagram", "post")
    assert not config.soporta_metrica("clics", "YouTube", "post")


def test_umbrales_de_muestra_definidos_en_config():
    """Los umbrales viven en un solo sitio: Facebook está subiendo histórico y
    el punto en que estos bloques tienen sentido se moverá."""
    assert config.MIN_PUBLICACIONES_BOTTOM >= 4
    assert config.MIN_PUBLICACIONES_FORMATO >= 2
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_config_social.py -v`
Expected: FAIL — `AttributeError: module 'src.config' has no attribute 'MIN_PUBLICACIONES_BOTTOM'`

- [ ] **Step 3: Añadir `clics` a METRICAS_POST**

En `src/config.py`, dentro de `METRICAS_POST`, tras `"compartidos": "Compartidos",`:

```python
    "clics": "Clics",
```

- [ ] **Step 4: Añadir el soporte de `clics`**

En `SOPORTE_METRICA_POST`, tras la línea de `"compartidos"`:

```python
    # Clics en la publicación. Los dan Facebook (`post_clicks`) y LinkedIn
    # (`clickCount`); Instagram y YouTube no. Verificado contra las cuentas
    # reales el 30-jul-2026. Es la métrica de orgánico más cercana a intención:
    # mide quién quiso saber más, no quién pasó el dedo.
    "clics": {"Facebook", "LinkedIn"},
```

- [ ] **Step 5: Añadir los umbrales**

Tras la constante `CACHE_TTL_SOCIAL`:

```python
# Umbrales de muestra de los bloques de análisis por red.
#
# Viven aquí y no repartidos por el código porque el volumen de publicaciones
# está creciendo (Facebook subiendo su histórico atrasado): el punto a partir
# del cual estos bloques dicen algo se va a mover, y moverlo debe ser cambiar
# una línea.
MIN_PUBLICACIONES_BOTTOM = 6   # por debajo, «la peor» es casi «la segunda»
MIN_PUBLICACIONES_FORMATO = 3  # una media de 1 publicación no es una media
```

- [ ] **Step 6: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 7: Commit**

```bash
git add src/config.py tests/test_config_social.py
git commit -m "config: métrica clics y umbrales de muestra

Facebook (post_clicks) y LinkedIn (clickCount) publican clics por publicación;
Instagram y YouTube no. Verificado contra las cuentas reales.

Los umbrales de muestra van a config en vez de repartidos por el código: el
volumen de publicaciones está creciendo y el punto a partir del cual un top/
bottom o una media por formato dicen algo se va a mover."
```

---

### Task 3: `social_analisis` — periodo anterior y comparativa de KPIs

**Files:**
- Create: `src/data/social_analisis.py`
- Test: `tests/test_social_analisis.py`

**Interfaces:**
- Consumes: `config.METRICAS_SOCIAL`, `config.soporta_metrica`, `src.data.social.interacciones`
- Produces:
  - `periodo_anterior(desde: date, hasta: date) -> tuple[date, date]`
  - `comparar_kpis(actual: pd.DataFrame, anterior: pd.DataFrame, red: str) -> pd.DataFrame` con columnas `metrica, etiqueta, actual, anterior, delta_pct`

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_social_analisis.py`:

```python
from datetime import date

import pandas as pd

from src.data import social, social_analisis as sa


def test_periodo_anterior_es_igual_de_largo_y_contiguo():
    d, h = sa.periodo_anterior(date(2026, 7, 1), date(2026, 7, 30))
    assert (d, h) == (date(2026, 6, 1), date(2026, 6, 30))


def test_periodo_anterior_de_un_solo_dia():
    d, h = sa.periodo_anterior(date(2026, 7, 15), date(2026, 7, 15))
    assert (d, h) == (date(2026, 7, 14), date(2026, 7, 14))


def _diario(red, fecha, **metricas):
    return social.normalizar_diario(pd.DataFrame([{"fecha": fecha, "red": red, **metricas}]))


def test_compara_y_calcula_la_variacion():
    act = _diario("Instagram", date(2026, 7, 1), visualizaciones=120)
    ant = _diario("Instagram", date(2026, 6, 1), visualizaciones=100)
    r = sa.comparar_kpis(act, ant, "Instagram").set_index("metrica")
    assert r.loc["visualizaciones", "actual"] == 120
    assert r.loc["visualizaciones", "anterior"] == 100
    assert r.loc["visualizaciones", "delta_pct"] == 20.0


def test_sin_periodo_anterior_la_variacion_es_nula_no_cero():
    """Un cero produciría un crecimiento del infinito por ciento."""
    act = _diario("Instagram", date(2026, 7, 1), visualizaciones=120)
    r = sa.comparar_kpis(act, social.esquema_diario_vacio(), "Instagram").set_index("metrica")
    assert pd.isna(r.loc["visualizaciones", "anterior"])
    assert pd.isna(r.loc["visualizaciones", "delta_pct"])


def test_omite_las_metricas_que_la_red_no_publica():
    """Facebook no tiene alcance: no debe aparecer en su tabla, ni a cero ni
    con guion. Para esa red esa métrica no existe."""
    act = _diario("Facebook", date(2026, 7, 1), visualizaciones=10)
    r = sa.comparar_kpis(act, social.esquema_diario_vacio(), "Facebook")
    assert "alcance" not in set(r["metrica"])
    assert "visualizaciones" in set(r["metrica"])


def test_solo_mira_la_red_pedida():
    act = pd.concat([
        _diario("Instagram", date(2026, 7, 1), visualizaciones=120),
        _diario("YouTube", date(2026, 7, 1), visualizaciones=999),
    ], ignore_index=True)
    r = sa.comparar_kpis(act, social.esquema_diario_vacio(), "Instagram").set_index("metrica")
    assert r.loc["visualizaciones", "actual"] == 120
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_social_analisis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data.social_analisis'`

- [ ] **Step 3: Crear el módulo**

`src/data/social_analisis.py`:

```python
"""
Análisis por red: comparativa contra el periodo anterior y rendimiento de
publicaciones.

Este módulo NO importa streamlit a propósito: así se puede probar con
DataFrames sueltos, sin levantar una app. Todo lo que devuelve son datos; de
pintarlos se encarga `src/ui/social_red.py`.
"""
from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from src import config


def periodo_anterior(desde: date, hasta: date) -> tuple[date, date]:
    """El intervalo de la MISMA longitud inmediatamente anterior a `desde`.

    Para 1–30 de julio devuelve 1–30 de junio. Se usa para dar contexto a los
    KPIs: un número sin el del periodo anterior no dice si va bien o mal.
    """
    dias = (hasta - desde).days
    fin = desde - timedelta(days=1)
    return fin - timedelta(days=dias), fin


def _total(diario: pd.DataFrame, red: str, metrica: str) -> float | None:
    """Suma de una métrica en un periodo, para una red. None si no hay dato.

    `min_count=1` es lo que mantiene la regla: si todas las casillas son nulas
    el resultado es nulo, no 0.
    """
    if diario is None or diario.empty or metrica not in diario.columns:
        return None
    d = diario[diario["red"] == red]
    if d.empty:
        return None
    total = d[metrica].sum(min_count=1)
    return None if pd.isna(total) else float(total)


def comparar_kpis(actual: pd.DataFrame, anterior: pd.DataFrame,
                  red: str) -> pd.DataFrame:
    """Tabla `metrica · etiqueta · actual · anterior · delta_pct` para una red.

    Solo incluye las métricas que ESA red publica: las demás no aparecen, ni a
    cero ni con guion. Para esa red, sencillamente no existen.

    `delta_pct` es nulo cuando no hay periodo anterior o cuando el anterior es
    cero: dividir por cero daría un crecimiento del infinito por ciento, que es
    peor que no decir nada.
    """
    filas = []
    for metrica, etiqueta in config.METRICAS_SOCIAL.items():
        if not config.soporta_metrica(metrica, red):
            continue
        act = _total(actual, red, metrica)
        ant = _total(anterior, red, metrica)
        delta = None
        if act is not None and ant not in (None, 0):
            delta = round((act - ant) / ant * 100, 1)
        filas.append({"metrica": metrica, "etiqueta": etiqueta,
                      "actual": act, "anterior": ant, "delta_pct": delta})
    return pd.DataFrame(filas)
```

- [ ] **Step 4: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/test_social_analisis.py -v`
Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/social_analisis.py tests/test_social_analisis.py
git commit -m "feat: comparativa de KPIs contra el periodo anterior

Un número sin el del mes pasado no dice si va bien o mal; es lo que convierte
la página en un informe.

Solo incluye las métricas que cada red publica: las demás no aparecen en su
tabla. Y sin periodo anterior la variación es NULA, no cero — un cero daría un
crecimiento del infinito por ciento.

El módulo no importa streamlit, para poder probarlo con DataFrames sueltos."
```

---

### Task 4: `social_analisis` — top/bottom y rendimiento por formato

**Files:**
- Modify: `src/data/social_analisis.py`
- Test: `tests/test_social_analisis.py` (añadir)

**Interfaces:**
- Consumes: `config.MIN_PUBLICACIONES_BOTTOM`, `config.MIN_PUBLICACIONES_FORMATO`, `src.data.social.tasa_engagement`, `src.data.social.interacciones`
- Produces:
  - `criterio_ranking(red: str) -> str` — `"engagement"` o `"interacciones"`
  - `ranking(posts: pd.DataFrame, red: str, n: int = 3, mejores: bool = True) -> pd.DataFrame`
  - `hay_muestra_para_bottom(posts: pd.DataFrame, red: str) -> bool`
  - `por_formato(posts: pd.DataFrame, red: str) -> pd.DataFrame` con columnas `tipo, n, visualizaciones_media, engagement_medio`

- [ ] **Step 1: Escribir los tests que fallan**

Añadir a `tests/test_social_analisis.py`:

```python
def _posts(red, filas):
    return social.normalizar_posts(pd.DataFrame([{"red": red, **f} for f in filas]))


def test_el_ranking_ordena_por_engagement_no_por_likes():
    """Ordenar por likes hace ganar siempre a la más vista, que es circular."""
    p = _posts("Instagram", [
        {"post_id": "muy_vista", "tipo": "Reel", "visualizaciones": 10000, "likes": 100},
        {"post_id": "muy_buena", "tipo": "Reel", "visualizaciones": 100, "likes": 50},
    ])
    r = sa.ranking(p, "Instagram", n=1, mejores=True)
    assert list(r["post_id"]) == ["muy_buena"]


def test_facebook_se_ordena_por_interacciones():
    """Solo sus vídeos traen visualizaciones, así que no hay denominador."""
    assert sa.criterio_ranking("Facebook") == "interacciones"
    assert sa.criterio_ranking("Instagram") == "engagement"
    p = _posts("Facebook", [
        {"post_id": "a", "tipo": "Publicación", "likes": 1, "comentarios": 0, "compartidos": 0},
        {"post_id": "b", "tipo": "Publicación", "likes": 9, "comentarios": 2, "compartidos": 1},
    ])
    r = sa.ranking(p, "Facebook", n=1, mejores=True)
    assert list(r["post_id"]) == ["b"]


def test_sin_muestra_no_hay_bottom():
    p = _posts("Facebook", [{"post_id": str(i), "tipo": "Publicación", "likes": i}
                            for i in range(2)])
    assert sa.hay_muestra_para_bottom(p, "Facebook") is False


def test_con_muestra_suficiente_si_hay_bottom():
    p = _posts("Facebook", [{"post_id": str(i), "tipo": "Publicación", "likes": i}
                            for i in range(config.MIN_PUBLICACIONES_BOTTOM)])
    assert sa.hay_muestra_para_bottom(p, "Facebook") is True


def test_por_formato_omite_los_formatos_con_pocas_publicaciones():
    """Una media de 1 publicación no es una media."""
    filas = [{"post_id": f"r{i}", "tipo": "Reel", "visualizaciones": 100, "likes": 10}
             for i in range(config.MIN_PUBLICACIONES_FORMATO)]
    filas.append({"post_id": "c1", "tipo": "Carrusel", "visualizaciones": 9999, "likes": 1})
    r = sa.por_formato(_posts("Instagram", filas), "Instagram")
    assert set(r["tipo"]) == {"Reel"}
    assert int(r.iloc[0]["n"]) == config.MIN_PUBLICACIONES_FORMATO
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_social_analisis.py -v`
Expected: FAIL — `AttributeError: module 'src.data.social_analisis' has no attribute 'ranking'`

- [ ] **Step 3: Implementar**

Añadir a `src/data/social_analisis.py` (tras `comparar_kpis`):

```python
# --------------------------------------------------------------------------- #
# Rendimiento de publicaciones
# --------------------------------------------------------------------------- #

def criterio_ranking(red: str) -> str:
    """Por qué se ordenan las publicaciones de esta red.

    Lo normal es la TASA de engagement: ordenar por likes brutos hace ganar
    siempre a la publicación más vista, que es una observación circular («lo
    que más se vio es lo que más se vio»).

    Facebook es la excepción: solo sus vídeos y reels traen visualizaciones, así
    que en las estáticas no hay denominador y la tasa sale nula. Sus
    publicaciones se ordenan por interacciones absolutas, y la UI lo dice.

    El criterio se decide AQUÍ y en ningún otro sitio: el día que la mayoría de
    las publicaciones de Facebook sean vídeo, cambiarlo es una línea.
    """
    return "interacciones" if red == "Facebook" else "engagement"


def _con_puntuacion(posts: pd.DataFrame, red: str) -> pd.DataFrame:
    """Añade la columna `puntuacion` con la que se ordena esa red."""
    from src.data import social

    d = posts[posts["red"] == red].copy()
    if d.empty:
        return d
    if criterio_ranking(red) == "engagement":
        d["puntuacion"] = social.tasa_engagement(d)
    else:
        d["puntuacion"] = social.interacciones(d)
    return d


def ranking(posts: pd.DataFrame, red: str, n: int = 3,
            mejores: bool = True) -> pd.DataFrame:
    """Las `n` mejores (o peores) publicaciones de una red.

    Las publicaciones sin puntuación se descartan: no se puede afirmar que una
    publicación sin datos sea la peor.
    """
    if posts is None or posts.empty:
        return posts if posts is not None else pd.DataFrame()
    d = _con_puntuacion(posts, red)
    if d.empty:
        return d
    d = d[d["puntuacion"].notna()]
    return d.sort_values("puntuacion", ascending=not mejores).head(n)


def hay_muestra_para_bottom(posts: pd.DataFrame, red: str) -> bool:
    """Si hay publicaciones suficientes para que «las peores» signifiquen algo.

    Con dos publicaciones, «la peor» es simplemente «la segunda».
    """
    if posts is None or posts.empty:
        return False
    return int((posts["red"] == red).sum()) >= config.MIN_PUBLICACIONES_BOTTOM


def por_formato(posts: pd.DataFrame, red: str) -> pd.DataFrame:
    """Media por tipo de publicación (Reel, Carrusel, Short, Vídeo…).

    Es el bloque que responde «qué publico la semana que viene». Solo aparecen
    los formatos con al menos `config.MIN_PUBLICACIONES_FORMATO` publicaciones:
    una media de una sola no es una media, y ponerla al lado de otra de doce
    invita a compararlas como si pesaran igual.
    """
    from src.data import social

    if posts is None or posts.empty:
        return pd.DataFrame(columns=["tipo", "n", "visualizaciones_media",
                                     "engagement_medio"])
    d = posts[posts["red"] == red].copy()
    if d.empty:
        return pd.DataFrame(columns=["tipo", "n", "visualizaciones_media",
                                     "engagement_medio"])
    d["_eng"] = social.tasa_engagement(d)
    g = d.groupby("tipo", dropna=False).agg(
        n=("post_id", "count"),
        visualizaciones_media=("visualizaciones", "mean"),
        engagement_medio=("_eng", "mean"),
    ).reset_index()
    return g[g["n"] >= config.MIN_PUBLICACIONES_FORMATO].sort_values(
        "n", ascending=False).reset_index(drop=True)
```

- [ ] **Step 4: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/social_analisis.py tests/test_social_analisis.py
git commit -m "feat: ranking de publicaciones y rendimiento por formato

El ranking ordena por TASA de engagement, no por likes brutos: ordenar por
likes hace ganar siempre a la publicación más vista, que es circular.

Facebook es la excepción y se ordena por interacciones absolutas, porque solo
sus vídeos traen visualizaciones y en las estáticas no hay denominador. El
criterio se decide en una sola función para que el día que eso cambie sea una
línea.

Los umbrales de muestra evitan las dos afirmaciones falsas más fáciles: «la
peor publicación» cuando solo hay dos, y una media por formato calculada sobre
una sola publicación."
```

---

### Task 5: `social_demografia` — esquema y regla de unidades

**Files:**
- Create: `src/data/social_demografia.py`
- Test: `tests/test_social_demografia.py`

**Interfaces:**
- Consumes: nada externo
- Produces:
  - `COLUMNAS: list[str]` = `["fecha", "red", "dimension", "categoria", "valor", "unidad"]`
  - `UNIDAD_POR_RED: dict[str, str]`
  - `esquema_vacio() -> pd.DataFrame`
  - `normalizar(df) -> pd.DataFrame`
  - `ultima_foto(df, red, hasta) -> pd.DataFrame`
  - `etiqueta_unidad(unidad: str) -> str`

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_social_demografia.py`:

```python
from datetime import date

import pandas as pd

from src.data import social_demografia as sd


def test_normalizar_deja_el_esquema_fijo():
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "2026-07-30", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": "145"},
    ]))
    assert list(d.columns) == sd.COLUMNAS
    assert d.loc[0, "valor"] == 145.0
    assert d.loc[0, "fecha"] == date(2026, 7, 30)


def test_la_unidad_se_deduce_de_la_red():
    """Instagram cuenta personas; YouTube, porcentaje de visualizaciones."""
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "2026-07-30", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145},
        {"fecha": "2026-07-30", "red": "YouTube", "dimension": "edad",
         "categoria": "45-54", "valor": 19.4},
    ]))
    u = dict(zip(d["red"], d["unidad"]))
    assert u["Instagram"] == "seguidores"
    assert u["YouTube"] == "pct_visualizaciones"


def test_etiqueta_de_unidad_es_legible():
    assert "seguidores" in sd.etiqueta_unidad("seguidores").lower()
    assert "%" in sd.etiqueta_unidad("pct_visualizaciones")


def test_ultima_foto_devuelve_solo_la_captura_mas_reciente():
    """La demografía es una foto, no una serie: mezclar dos capturas sumaría
    la misma persona dos veces."""
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "2026-07-01", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 100},
        {"fecha": "2026-07-30", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145},
    ]))
    f = sd.ultima_foto(d, "Instagram", date(2026, 7, 30))
    assert len(f) == 1
    assert f.iloc[0]["valor"] == 145


def test_ultima_foto_respeta_el_limite_de_fecha():
    d = sd.normalizar(pd.DataFrame([
        {"fecha": "2026-07-01", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 100},
        {"fecha": "2026-07-30", "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145},
    ]))
    f = sd.ultima_foto(d, "Instagram", date(2026, 7, 15))
    assert f.iloc[0]["valor"] == 100


def test_facebook_no_tiene_unidad_porque_no_tiene_demografia():
    assert "Facebook" not in sd.UNIDAD_POR_RED
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_social_demografia.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.data.social_demografia'`

- [ ] **Step 3: Crear el módulo**

`src/data/social_demografia.py`:

```python
"""
Esquema normalizado de la demografía de audiencia.

Formato largo: una fila por (fecha, red, dimensión, categoría). Es lo que
permite que redes con dimensiones distintas —Instagram da edad y género,
LinkedIn da cargo y sector— convivan en la misma tabla sin columnas vacías.

⚠️ LA UNIDAD NO ES LA MISMA EN TODAS LAS REDES, y es la trampa principal de
este módulo:

- Instagram cuenta PERSONAS que te siguen.
- YouTube da el PORCENTAJE de visualizaciones por tramo.

Son poblaciones distintas y magnitudes distintas. Un gráfico que las junte
está sumando peras y manzanas sin avisar, así que la unidad viaja pegada al
dato en su propia columna y la UI la escribe dentro del bloque.

- Facebook NO aparece: Meta retiró la demografía de Páginas en 2025. Los cinco
  nombres documentados responden «must be a valid insights metric».
- LinkedIn no publica edad ni género en ninguna versión de su API.
"""
from __future__ import annotations

from datetime import date

import pandas as pd

COLUMNAS = ["fecha", "red", "dimension", "categoria", "valor", "unidad"]

# Qué mide cada red. Facebook no está porque no publica demografía.
UNIDAD_POR_RED = {
    "Instagram": "seguidores",
    "YouTube": "pct_visualizaciones",
    "LinkedIn": "seguidores",
}

_ETIQUETAS = {
    "seguidores": "personas que te siguen",
    "pct_visualizaciones": "% de las visualizaciones",
}


def etiqueta_unidad(unidad: str) -> str:
    """Texto legible de la unidad, para escribirlo DENTRO del bloque."""
    return _ETIQUETAS.get(unidad, unidad)


def esquema_vacio() -> pd.DataFrame:
    return pd.DataFrame({c: pd.Series(dtype="object") for c in COLUMNAS})


def normalizar(df: pd.DataFrame) -> pd.DataFrame:
    """Deja el df en el esquema fijo, con tipos correctos y la unidad puesta.

    La unidad se deduce de la red y se PISA siempre: que la escriba un conector
    es opcional, que sea correcta no.
    """
    if df is None or df.empty:
        return esquema_vacio()

    d = df.copy()
    for c in COLUMNAS:
        if c not in d.columns:
            d[c] = pd.NA
    d = d[COLUMNAS]

    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce").dt.date
    d["valor"] = pd.to_numeric(d["valor"], errors="coerce")
    d["unidad"] = d["red"].map(UNIDAD_POR_RED)

    return d.reset_index(drop=True)


def ultima_foto(df: pd.DataFrame, red: str, hasta: date) -> pd.DataFrame:
    """La captura MÁS RECIENTE de una red, en o antes de `hasta`.

    La demografía es una foto acumulada, no un flujo: sumar dos capturas
    contaría a la misma persona dos veces. Por eso se toma una sola fecha.
    """
    if df is None or df.empty:
        return esquema_vacio()
    d = df[(df["red"] == red) & df["fecha"].notna()]
    d = d[d["fecha"] <= hasta]
    if d.empty:
        return esquema_vacio()
    return d[d["fecha"] == d["fecha"].max()].reset_index(drop=True)
```

- [ ] **Step 4: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 5: Commit**

```bash
git add src/data/social_demografia.py tests/test_social_demografia.py
git commit -m "feat: esquema de demografía de audiencia

Formato largo (fecha, red, dimension, categoria, valor, unidad) para que redes
con dimensiones distintas convivan sin columnas vacías: Instagram da edad y
género, LinkedIn da cargo y sector.

La unidad viaja pegada al dato porque NO es la misma: Instagram cuenta personas
que te siguen, YouTube da el porcentaje de visualizaciones por tramo. Son
poblaciones distintas, y un gráfico que las junte suma peras y manzanas.

`ultima_foto` toma una sola fecha: la demografía es acumulada, no un flujo, y
sumar dos capturas contaría a la misma persona dos veces."
```

---

### Task 6: Demografía de Instagram

**Files:**
- Modify: `src/connectors/meta_organico.py`
- Test: `tests/test_demografia_instagram.py`

**Interfaces:**
- Consumes: `meta_organico._get`, `_contexto_ig`, `_version`
- Produces: `meta_organico._api_ig_demografia(creds: dict, fecha: date) -> pd.DataFrame` en el esquema de `social_demografia`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_demografia_instagram.py`:

```python
"""La API se simula: estos tests comprueban la TRADUCCIÓN de su respuesta al
esquema, que es la parte con lógica. Contra la cuenta real se comprueba con
`scripts/verificar_social.py`.
"""
from datetime import date

from src.connectors import meta_organico as m
from src.data import social_demografia as sd


def _respuesta(breakdown, resultados):
    return {"data": [{"total_value": {"breakdowns": [{
        "results": [{"dimension_values": [k], "value": v}
                    for k, v in resultados.items()]}]}}]}


def test_traduce_los_desgloses_al_esquema(monkeypatch):
    respuestas = {
        "age": _respuesta("age", {"45-54": 145, "35-44": 107}),
        "gender": _respuesta("gender", {"F": 226, "M": 92}),
        "city": _respuesta("city", {"Barcelona, Cataluña": 42}),
        "country": _respuesta("country", {"ES": 399}),
    }
    monkeypatch.setattr(m, "_contexto_ig", lambda creds: ("IG1", "tok"))
    monkeypatch.setattr(m, "_get",
                        lambda v, ruta, tok, params: respuestas[params["breakdown"]])

    df = m._api_ig_demografia({}, date(2026, 7, 30))
    d = sd.normalizar(df)

    assert set(d["dimension"]) == {"edad", "genero", "ciudad", "pais"}
    edad = d[(d["dimension"] == "edad") & (d["categoria"] == "45-54")]
    assert edad.iloc[0]["valor"] == 145
    assert set(d["unidad"]) == {"seguidores"}
    assert set(d["fecha"]) == {date(2026, 7, 30)}


def test_un_desglose_que_falla_no_tumba_los_demas(monkeypatch):
    """Si Meta retira uno, los otros tres tienen que seguir entrando."""
    def _get(v, ruta, tok, params):
        if params["breakdown"] == "city":
            raise RuntimeError("(#100) not a valid metric")
        return _respuesta(params["breakdown"], {"X": 1})

    monkeypatch.setattr(m, "_contexto_ig", lambda creds: ("IG1", "tok"))
    monkeypatch.setattr(m, "_get", _get)

    d = sd.normalizar(m._api_ig_demografia({}, date(2026, 7, 30)))
    assert "ciudad" not in set(d["dimension"])
    assert {"edad", "genero", "pais"} <= set(d["dimension"])
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_demografia_instagram.py -v`
Expected: FAIL — `AttributeError: module has no attribute '_api_ig_demografia'`

- [ ] **Step 3: Implementar**

Añadir a `src/connectors/meta_organico.py`, al final de la sección de Instagram:

```python
# Desglose de la API -> nombre de dimensión del esquema.
_DESGLOSES_IG = {"age": "edad", "gender": "genero",
                 "city": "ciudad", "country": "pais"}


def _api_ig_demografia(creds: dict, fecha) -> pd.DataFrame:
    """Demografía de los seguidores de Instagram, en el esquema largo.

    `follower_demographics` es una métrica «lifetime» que exige
    `metric_type=total_value` y un `breakdown` por consulta: son cuatro
    llamadas, una por dimensión.

    Cada desglose va en su propio try: si Meta retira uno —ya se llevó por
    delante toda la demografía de Facebook— los otros tres tienen que seguir
    entrando. Lo que falle no aparece, y acaba como ausencia, no como cero.

    Verificado contra @reversal_institute el 30-jul-2026: 6 tramos de edad,
    3 de género, 45 ciudades y 6 países.
    """
    version = _version(creds)
    ig, token = _contexto_ig(creds)

    filas = []
    for desglose, dimension in _DESGLOSES_IG.items():
        try:
            r = _get(version, f"{ig}/insights", token, {
                "metric": "follower_demographics", "period": "lifetime",
                "metric_type": "total_value", "breakdown": desglose,
                "timeframe": "this_month"})
        except Exception:  # noqa: BLE001
            continue
        bloques = (r.get("data") or [{}])[0].get("total_value", {}).get("breakdowns", [])
        for res in (bloques[0].get("results", []) if bloques else []):
            valores = res.get("dimension_values") or []
            if not valores:
                continue
            filas.append({"fecha": fecha, "red": RED_IG, "dimension": dimension,
                          "categoria": valores[0], "valor": res.get("value")})
    return pd.DataFrame(filas)
```

- [ ] **Step 4: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 5: Comprobar contra la cuenta real**

Run:
```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from datetime import date
from src.connectors import meta_organico as m
from src.connectors.base import _leer_secreto
from src.data import social_demografia as sd
d = sd.normalizar(m._api_ig_demografia(_leer_secreto('social_meta'), date.today()))
print(d.groupby('dimension').size())
print(d[d.dimension=='edad'].to_string(index=False))"
```
Expected: 4 dimensiones, y en edad los 6 tramos con `45-54` como el mayor.

- [ ] **Step 6: Commit**

```bash
git add src/connectors/meta_organico.py tests/test_demografia_instagram.py
git commit -m "feat: demografía de seguidores de Instagram

follower_demographics exige metric_type=total_value y un breakdown por
consulta: cuatro llamadas, una por dimensión. Cada una en su propio try, para
que si Meta retira una —ya se llevó toda la demografía de Facebook— las otras
sigan entrando.

Verificado contra la cuenta real: 6 tramos de edad, 3 de género, 45 ciudades
y 6 países."
```

---

### Task 7: Demografía de YouTube

**Files:**
- Modify: `src/connectors/youtube.py`
- Test: `tests/test_demografia_youtube.py`

**Interfaces:**
- Consumes: `youtube._servicios`, `youtube._canal`
- Produces: `youtube._api_demografia(creds: dict, desde, hasta) -> pd.DataFrame`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_demografia_youtube.py`:

```python
from datetime import date

from src.connectors import youtube as yt
from src.data import social_demografia as sd


class _Reports:
    def __init__(self, respuestas):
        self._r = respuestas

    def query(self, **kw):
        clave = kw["dimensions"]
        datos = self._r[clave]

        class _Ej:
            def execute(self_inner):
                return datos
        return _Ej()


class _Analytics:
    def __init__(self, respuestas):
        self._r = respuestas

    def reports(self):
        return _Reports(self._r)


def test_traduce_edad_genero_y_pais(monkeypatch):
    respuestas = {
        "ageGroup,gender": {"rows": [["age45-54", "female", 19.4],
                                     ["age25-34", "male", 5.2]]},
        "country": {"rows": [["ES", 280], ["AR", 137]]},
    }
    monkeypatch.setattr(yt, "_servicios", lambda c: (_Analytics(respuestas), None))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC123")

    d = sd.normalizar(yt._api_demografia({}, date(2026, 7, 1), date(2026, 7, 30)))

    assert {"edad", "genero", "pais"} <= set(d["dimension"])
    edad = d[(d["dimension"] == "edad") & (d["categoria"] == "45-54")]
    assert round(float(edad.iloc[0]["valor"]), 1) == 19.4


def test_la_unidad_de_youtube_no_es_seguidores():
    """Su demografía es % de visualizaciones, no gente que te sigue."""
    assert sd.UNIDAD_POR_RED["YouTube"] == "pct_visualizaciones"


def test_quita_el_prefijo_age_de_los_tramos(monkeypatch):
    """La API devuelve 'age45-54'; el esquema guarda '45-54' para que coincida
    con los tramos de Instagram y se puedan poner en el mismo eje."""
    respuestas = {"ageGroup,gender": {"rows": [["age45-54", "female", 1.0]]},
                  "country": {"rows": []}}
    monkeypatch.setattr(yt, "_servicios", lambda c: (_Analytics(respuestas), None))
    monkeypatch.setattr(yt, "_canal", lambda c: "UC123")
    d = sd.normalizar(yt._api_demografia({}, date(2026, 7, 1), date(2026, 7, 30)))
    assert "45-54" in set(d["categoria"])
    assert not any(str(c).startswith("age") for c in d["categoria"])
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_demografia_youtube.py -v`
Expected: FAIL — `AttributeError: module has no attribute '_api_demografia'`

- [ ] **Step 3: Implementar**

Añadir a `src/connectors/youtube.py`:

```python
# Género de la API -> categoría del esquema, alineada con la de Instagram.
_GENERO_YT = {"female": "F", "male": "M", "user_specified": "U", "gender_other": "U"}


def _api_demografia(creds: dict, desde, hasta) -> pd.DataFrame:
    """Demografía de la audiencia de YouTube, en el esquema largo.

    ⚠️ Esto NO es la demografía de tus suscriptores: `viewerPercentage` es el
    porcentaje de VISUALIZACIONES por tramo en el periodo. Otra población y
    otra unidad que la de Instagram, que cuenta personas. `social_demografia`
    lo marca con la unidad `pct_visualizaciones` y la UI lo escribe en el
    bloque.

    Los tramos vienen como «age45-54»; se les quita el prefijo para que
    coincidan con los de Instagram y puedan compartir eje (nunca gráfico).
    """
    analytics, _ = _servicios(creds)
    canal = _canal(creds)
    ids = f"channel=={canal}" if canal else "channel==MINE"
    base = dict(ids=ids, startDate=str(desde), endDate=str(hasta))

    filas = []
    try:
        r = analytics.reports().query(
            **base, metrics="viewerPercentage", dimensions="ageGroup,gender").execute()
        por_edad: dict[str, float] = {}
        for tramo, genero, pct in (fila[:3] for fila in r.get("rows", [])):
            etiqueta = str(tramo).removeprefix("age")
            por_edad[etiqueta] = por_edad.get(etiqueta, 0.0) + float(pct)
            filas.append({"fecha": hasta, "red": RED, "dimension": "genero",
                          "categoria": _GENERO_YT.get(genero, "U"), "valor": pct})
        for etiqueta, pct in por_edad.items():
            filas.append({"fecha": hasta, "red": RED, "dimension": "edad",
                          "categoria": etiqueta, "valor": round(pct, 2)})
    except Exception:  # noqa: BLE001
        pass

    try:
        r = analytics.reports().query(
            **base, metrics="views", dimensions="country").execute()
        for pais, vistas in (fila[:2] for fila in r.get("rows", [])):
            filas.append({"fecha": hasta, "red": RED, "dimension": "pais",
                          "categoria": pais, "valor": vistas})
    except Exception:  # noqa: BLE001
        pass

    return pd.DataFrame(filas)
```

⚠️ El género se suma por tramo para obtener la edad total, porque la API los
devuelve cruzados. Los valores de `pais` son visualizaciones absolutas, no
porcentaje: la UI lo presenta como reparto relativo.

- [ ] **Step 4: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 5: Comprobar contra el canal real**

Run:
```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from datetime import date, timedelta
from src.connectors import youtube as yt
from src.connectors.base import _leer_secreto
from src.data import social_demografia as sd
h=date.today()-timedelta(days=2)
d = sd.normalizar(yt._api_demografia(_leer_secreto('youtube'), h-timedelta(days=90), h))
print(d.groupby('dimension').size()); print(d[d.dimension=='edad'].to_string(index=False))"
```
Expected: las tres dimensiones con datos.

- [ ] **Step 6: Commit**

```bash
git add src/connectors/youtube.py tests/test_demografia_youtube.py
git commit -m "feat: demografía de audiencia de YouTube

viewerPercentage es el porcentaje de VISUALIZACIONES por tramo, no la
composición de los suscriptores: otra población y otra unidad que la de
Instagram. Queda marcado con la unidad pct_visualizaciones.

La API devuelve edad y género cruzados; se suman por tramo para obtener la
edad total. Y se quita el prefijo 'age' para que los tramos coincidan con los
de Instagram y puedan compartir eje — nunca gráfico."
```

---

### Task 8: Demografía de LinkedIn

LinkedIn sigue sin acceso aprobado. La función se escribe ahora para que el día que llegue la credencial no haya que tocar nada, y se prueba con la respuesta simulada.

**Files:**
- Modify: `src/connectors/linkedin.py`
- Test: `tests/test_demografia_linkedin.py`

**Interfaces:**
- Consumes: `linkedin._token`, `_get`, `_org_urn`
- Produces: `linkedin._api_demografia(creds: dict) -> pd.DataFrame`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_demografia_linkedin.py`:

```python
from datetime import date

from src.connectors import linkedin as li
from src.data import social_demografia as sd


def test_traduce_los_desgloses_de_seguidores(monkeypatch):
    respuesta = {"elements": [{
        "followerCountsByStaffCountRange": [
            {"staffCountRange": "SIZE_11_TO_50", "followerCounts": {"organicFollowerCount": 12}}],
        "followerCountsByIndustry": [
            {"industry": "urn:li:industry:14", "followerCounts": {"organicFollowerCount": 30}}],
        "followerCountsByFunction": [
            {"function": "urn:li:function:14", "followerCounts": {"organicFollowerCount": 8}}],
        "followerCountsBySeniority": [
            {"seniority": "urn:li:seniority:6", "followerCounts": {"organicFollowerCount": 5}}],
        "followerCountsByGeoCountry": [
            {"geo": "urn:li:geo:105646813", "followerCounts": {"organicFollowerCount": 40}}],
    }]}
    monkeypatch.setattr(li, "_token", lambda creds: "tok")
    monkeypatch.setattr(li, "_org_urn", lambda creds: "urn:li:organization:123114024")
    monkeypatch.setattr(li, "_get", lambda ruta, creds, token, params=None: respuesta)

    d = sd.normalizar(li._api_demografia({}))

    assert {"tamano_empresa", "sector", "funcion", "cargo", "pais"} <= set(d["dimension"])
    assert d[d["dimension"] == "pais"].iloc[0]["valor"] == 40
    assert set(d["unidad"]) == {"seguidores"}


def test_linkedin_no_aporta_edad_ni_genero(monkeypatch):
    """Su API no los publica en ninguna versión. Si algún día aparecieran,
    este test falla y obliga a revisar el diseño en vez de colarlos."""
    monkeypatch.setattr(li, "_token", lambda creds: "tok")
    monkeypatch.setattr(li, "_org_urn", lambda creds: "urn:li:organization:1")
    monkeypatch.setattr(li, "_get", lambda ruta, creds, token, params=None: {"elements": []})
    d = sd.normalizar(li._api_demografia({}))
    assert "edad" not in set(d["dimension"])
    assert "genero" not in set(d["dimension"])
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_demografia_linkedin.py -v`
Expected: FAIL — `AttributeError: module has no attribute '_api_demografia'`

- [ ] **Step 3: Implementar**

Añadir a `src/connectors/linkedin.py`:

```python
# Campo de la respuesta -> (clave del elemento, dimensión del esquema).
_DESGLOSES_LI = {
    "followerCountsByStaffCountRange": ("staffCountRange", "tamano_empresa"),
    "followerCountsByIndustry": ("industry", "sector"),
    "followerCountsByFunction": ("function", "funcion"),
    "followerCountsBySeniority": ("seniority", "cargo"),
    "followerCountsByGeoCountry": ("geo", "pais"),
}


def _api_demografia(creds: dict) -> pd.DataFrame:
    """Demografía de los seguidores de la organización, en el esquema largo.

    ⚠️ LinkedIn NO publica edad ni género en ninguna versión de su API. Lo que
    da es profesional: cargo, función, sector, tamaño de empresa y país. Para
    una certificación dirigida a sanitarios eso es más útil que la edad, pero
    no es lo mismo y la UI no debe insinuar que sí.

    Los valores vienen como URN (`urn:li:industry:14`). Se guarda el URN tal
    cual: traducirlo a nombre legible exige otra llamada por cada uno, y la UI
    puede hacerlo cuando haya acceso real y se sepa el volumen.

    Estado: SIN VERIFICAR contra la organización real — la Community Management
    API está en revisión desde el 30-jul-2026.
    """
    token = _token(creds)
    org = _org_urn(creds)
    datos = _get("organizationalEntityFollowerStatistics", creds, token,
                 {"q": "organizationalEntity", "organizationalEntity": org})

    elementos = datos.get("elements") or []
    if not elementos:
        return pd.DataFrame()

    hoy = _date.today()
    filas = []
    for campo, (clave, dimension) in _DESGLOSES_LI.items():
        for item in elementos[0].get(campo, []):
            valor = (item.get("followerCounts") or {}).get("organicFollowerCount")
            if valor is None:
                continue
            filas.append({"fecha": hoy, "red": RED, "dimension": dimension,
                          "categoria": item.get(clave), "valor": valor})
    return pd.DataFrame(filas)
```

Y en las importaciones de `src/connectors/linkedin.py`, añadir:

```python
from datetime import date as _date
```

- [ ] **Step 4: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 5: Commit**

```bash
git add src/connectors/linkedin.py tests/test_demografia_linkedin.py
git commit -m "feat: demografía de seguidores de LinkedIn

Cargo, función, sector, tamaño de empresa y país. LinkedIn NO publica edad ni
género en ninguna versión de su API; hay un test que lo fija, de modo que si
algún día aparecieran obligue a revisar el diseño en vez de colarlos.

Los valores se guardan como URN: traducirlos exige una llamada por cada uno y
todavía no sabemos el volumen. Sin verificar contra la organización real: la
Community Management API sigue en revisión."
```

---

### Task 9: Métricas de publicación de Facebook — clics

`_insights_post_fb` sigue pidiendo `post_impressions_organic` y `post_impressions`, que Meta retiró: la función entra por el `except` en cada intento y devuelve `{}`. Y nadie captura `post_clicks`, que la Tarea 2 ya declaró como métrica.

**Files:**
- Modify: `src/connectors/meta_organico.py` (`_insights_post_fb`, `_api_fb_posts`)
- Test: `tests/test_posts_facebook.py`

**Interfaces:**
- Consumes: `meta_organico._get`
- Produces: `_insights_post_fb(version, post_id, token) -> dict` con las claves `visualizaciones`, `clics` y `reacciones_por_tipo`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_posts_facebook.py`:

```python
"""Traducción de los insights de publicación de Facebook.

Los nombres se sondearon contra la Página real el 30-jul-2026: toda la familia
post_impressions* está retirada; post_clicks, post_video_views y
post_reactions_by_type_total responden.
"""
from src.connectors import meta_organico as m


def _bloques(*pares):
    return {"data": [{"name": n, "values": [{"value": v}]} for n, v in pares]}


def test_captura_clics_y_reproducciones(monkeypatch):
    monkeypatch.setattr(m, "_get", lambda v, ruta, tok, params: _bloques(
        ("post_clicks", 17), ("post_video_views", 240)))
    out = m._insights_post_fb("v21.0", "p1", "tok")
    assert out["clics"] == 17
    assert out["visualizaciones"] == 240


def test_no_pide_metricas_retiradas(monkeypatch):
    """post_impressions* está retirada: pedirla hace que Meta rechace la
    llamada ENTERA y se pierdan también las métricas que sí existen."""
    pedidas = []

    def _get(v, ruta, tok, params):
        pedidas.append(params["metric"])
        return _bloques(("post_clicks", 1))

    monkeypatch.setattr(m, "_get", _get)
    m._insights_post_fb("v21.0", "p1", "tok")
    assert not any("post_impressions" in p for p in pedidas)


def test_una_metrica_que_falla_no_tumba_las_demas(monkeypatch):
    """Se piden de una en una: si Meta retira otra, el resto sigue entrando."""
    def _get(v, ruta, tok, params):
        if params["metric"] == "post_clicks":
            raise RuntimeError("(#100) not valid")
        return _bloques((params["metric"], 5))

    monkeypatch.setattr(m, "_get", _get)
    out = m._insights_post_fb("v21.0", "p1", "tok")
    assert "clics" not in out
    assert out["visualizaciones"] == 5
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_posts_facebook.py -v`
Expected: FAIL — `KeyError: 'clics'`

- [ ] **Step 3: Reescribir `_insights_post_fb`**

Sustituir la función entera en `src/connectors/meta_organico.py`:

```python
# Métrica de la API -> clave del esquema. VERIFICADAS contra la Página real el
# 30-jul-2026 sondeando una a una. Toda la familia `post_impressions*` está
# retirada, igual que a nivel de Página, así que ni se pide: incluirla haría
# que Meta rechazara la llamada entera y se perderían también las que sí
# funcionan.
_METRICAS_POST_FB = {
    "post_video_views": "visualizaciones",     # solo vídeo; en estáticas, nulo
    "blue_reels_play_count": "visualizaciones",  # reels
    "post_clicks": "clics",
}

# `post_reactions_by_type_total` existe y responde, pero devuelve un DICCIONARIO
# (me gusta / me encanta / me sorprende…), no un número. El esquema de
# publicaciones es numérico y `social.normalizar_posts` descarta lo que no está
# en él, así que incorporarlo exige tocar el esquema. Con 0 reacciones en toda
# la Página hoy, no compensa: queda anotado como fuera de alcance en el spec.


def _insights_post_fb(version: str, post_id: str, token: str) -> dict:
    """Métricas de UNA publicación de Facebook. {} si no se puede leer ninguna.

    Se piden de UNA EN UNA a propósito. Meta rechaza la petición completa si un
    solo nombre ya no existe, y esta familia de métricas la está podando a buen
    ritmo: pidiéndolas por separado, lo que se retire mañana se pierde solo a sí
    mismo. Lo que no responde no aparece en el dict, y acaba como NULO —nunca
    como cero— en el DataFrame.
    """
    out = {}
    for metrica, clave in _METRICAS_POST_FB.items():
        try:
            datos = _get(version, f"{post_id}/insights", token,
                         {"metric": metrica})
        except Exception:  # noqa: BLE001
            continue
        for bloque in datos.get("data", []):
            valores = bloque.get("values") or [{}]
            valor = valores[0].get("value")
            # `visualizaciones` la pueden llenar dos métricas (vídeo y reels):
            # gana la primera que traiga un valor real.
            if valor in (None, {}, 0) and clave in out:
                continue
            if valor is not None:
                out[clave] = valor
    return out
```

- [ ] **Step 4: Pasar `clics` al DataFrame de publicaciones**

En `_api_fb_posts`, donde se construye cada fila con los insights, añadir la columna `clics` junto a las demás métricas, para que `social.normalizar_posts` la recoja del esquema.

- [ ] **Step 5: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 6: Comprobar contra la Página real**

Run:
```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from datetime import date, timedelta
from src.connectors import meta_organico as m
from src.connectors.base import _leer_secreto
h=date.today(); d=h-timedelta(days=365)
p = m.obtener_posts_facebook(d,h).df
print(p[['fecha','tipo','likes','comentarios','compartidos','clics']].to_string(index=False))"
```
Expected: la columna `clics` con valores (0 es válido: son clics reales).

- [ ] **Step 7: Commit**

```bash
git add src/connectors/meta_organico.py tests/test_posts_facebook.py
git commit -m "fix: métricas de publicación de Facebook que sí existen

_insights_post_fb pedía post_impressions_organic y post_impressions, retiradas
por Meta igual que sus equivalentes de Página: la función entraba por el except
en los tres intentos y devolvía {} siempre. Las publicaciones de Facebook no
tenían métricas por eso, no por falta de permisos.

Ahora pide las que el sondeo confirmó —post_video_views, blue_reels_play_count,
post_clicks y post_reactions_by_type_total— y de UNA EN UNA: Meta rechaza la
llamada entera si un solo nombre ya no existe, y está podando esta familia a
buen ritmo. Pidiéndolas por separado, lo que se retire mañana se pierde solo a
sí mismo.

post_reactions_by_type_total se deja fuera: devuelve un diccionario, no un
número, y el esquema de publicaciones es numérico. Con 0 reacciones en toda la
Página, la cirugía no compensa todavía."
```

---

### Task 10: El job captura la demografía

**Files:**
- Modify: `scripts/snapshot_social.py`
- Modify: `src/connectors/base.py` (nada nuevo — se reutiliza `escribir_historico`)
- Test: `tests/test_snapshot_demografia.py`

**Interfaces:**
- Consumes: `_api_ig_demografia`, `youtube._api_demografia`, `linkedin._api_demografia`, `social_base.fusionar`, `base.escribir_historico`
- Produces:
  - `snapshot_social.FUENTES_DEMOGRAFIA: tuple`
  - `snapshot_social.capturar_demografia(fuente, desde, hasta) -> tuple[pd.DataFrame | None, str]`
  - Ficheros `data/historico_social/social_<red>_demografia.csv`

- [ ] **Step 1: Escribir el test que falla**

`tests/test_snapshot_demografia.py`:

```python
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from src.connectors import base as cbase
from src.connectors import social_base
from src.data import social_demografia as sd


@pytest.fixture
def historico_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(cbase, "HISTORICO_DIR", tmp_path)
    return tmp_path


def test_la_demografia_se_acumula_sin_perder_capturas(historico_temporal):
    """Dos capturas de días distintos deben convivir: es lo que permitirá ver
    la deriva de la audiencia dentro de unos meses."""
    ayer = sd.normalizar(pd.DataFrame([
        {"fecha": date(2026, 7, 29), "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 140}]))
    hoy = sd.normalizar(pd.DataFrame([
        {"fecha": date(2026, 7, 30), "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145}]))

    claves = ("fecha", "red", "dimension", "categoria")
    fusion = social_base.fusionar(ayer, hoy, claves)
    assert len(fusion) == 2
    assert set(fusion["valor"]) == {140, 145}


def test_una_recaptura_del_mismo_dia_corrige_sin_duplicar(historico_temporal):
    claves = ("fecha", "red", "dimension", "categoria")
    base = sd.normalizar(pd.DataFrame([
        {"fecha": date(2026, 7, 30), "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 140}]))
    nueva = sd.normalizar(pd.DataFrame([
        {"fecha": date(2026, 7, 30), "red": "Instagram", "dimension": "edad",
         "categoria": "45-54", "valor": 145}]))
    fusion = social_base.fusionar(base, nueva, claves)
    assert len(fusion) == 1
    assert fusion.iloc[0]["valor"] == 145


def test_sin_credenciales_no_escribe_nada(historico_temporal, monkeypatch):
    """La regla de oro del job: nunca datos inventados en el histórico."""
    import scripts.snapshot_social as snap
    monkeypatch.setattr(snap, "_leer_secreto", lambda s: None)
    fuente = snap.FUENTES_DEMOGRAFIA[0]
    df, motivo = snap.capturar_demografia(fuente, date(2026, 7, 1), date(2026, 7, 30))
    assert df is None
    assert "credenciales" in motivo
    assert list(Path(historico_temporal).glob("*.csv")) == []
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_snapshot_demografia.py -v`
Expected: FAIL — `AttributeError: module 'scripts.snapshot_social' has no attribute 'FUENTES_DEMOGRAFIA'`

- [ ] **Step 3: Añadir la fase de demografía al job**

En `scripts/snapshot_social.py`, tras la constante `FUENTES`:

```python
CLAVES_DEMOGRAFIA = ("fecha", "red", "dimension", "categoria")

# Demografía de audiencia. Facebook NO está: Meta retiró la demografía de
# Páginas y no hay sustituto. Cada entrada apunta, igual que arriba, a la
# función de API DIRECTA — nunca a la cascada, que caería a datos de ejemplo.
FUENTES_DEMOGRAFIA = (
    Fuente("Instagram", "social_meta", "social_instagram_demografia",
           lambda c, d, h: meta_organico._api_ig_demografia(c, h),
           "foto actual, sin histórico"),
    Fuente("YouTube", "youtube", "social_youtube_demografia",
           lambda c, d, h: youtube._api_demografia(c, d, h),
           "% de visualizaciones del periodo"),
    Fuente("LinkedIn", "linkedin", "social_linkedin_demografia",
           lambda c, d, h: linkedin._api_demografia(c),
           "foto actual, sin histórico"),
)
```

- [ ] **Step 4: Añadir `capturar_demografia` y `acumular_demografia`**

Tras la función `capturar`:

```python
def capturar_demografia(fuente: Fuente, desde: date,
                        hasta: date) -> tuple[pd.DataFrame | None, str]:
    """Pide la demografía de una red, ya normalizada.

    Mismo contrato que `capturar`: con df a None, `motivo` explica por qué se
    salta esa red. Nunca se inventa un sustituto.
    """
    creds = _leer_secreto(fuente.seccion)
    if not creds:
        return None, f"sin credenciales (falta [{fuente.seccion}] en secrets.toml)"
    try:
        bruto = fuente.fn_api(creds, desde, hasta)
    except Exception as e:  # noqa: BLE001
        return None, f"la API falló: {e}"
    if bruto is None or bruto.empty:
        return None, "la API no devolvió demografía"
    return social_demografia.normalizar(bruto), "ok"


def acumular_demografia(clave: str, nuevo: pd.DataFrame,
                        dry_run: bool) -> tuple[pd.DataFrame, int]:
    """Funde la foto de hoy sobre el histórico de demografía guardado."""
    previo_bruto = leer_historico(clave)
    previo = (social_demografia.normalizar(previo_bruto)
              if previo_bruto is not None and not previo_bruto.empty else None)

    fusion = fusionar(previo, nuevo, CLAVES_DEMOGRAFIA)
    fusion = fusion.sort_values(list(CLAVES_DEMOGRAFIA)).reset_index(drop=True)
    nuevas = len(fusion) - (0 if previo is None else len(previo))

    if not dry_run:
        escribir_historico(fusion, clave)
    return fusion, max(nuevas, 0)
```

Y en las importaciones del script, añadir `social_demografia`:

```python
from src.data import social, social_demografia  # noqa: E402
```

- [ ] **Step 5: Llamar a la fase nueva desde `main`**

En `main()`, tras el bucle de `fuentes` y antes del resumen final:

```python
    print("\nDemografía de audiencia:")
    for f in [x for x in FUENTES_DEMOGRAFIA if not args.red or x.red in args.red]:
        df, motivo = capturar_demografia(f, desde, hasta)
        if df is None:
            print(f"  ⏭  {f.red:<10} saltada — {motivo}")
            continue
        fusion, nuevas = acumular_demografia(f.clave, df, args.dry_run)
        dims = ", ".join(sorted(set(df["dimension"])))
        print(f"  ✓  {f.red:<10} +{nuevas} filas → {len(fusion)} en total ({dims})")
    print("  ·  Facebook   sin demografía: Meta la retiró de las Páginas")
```

- [ ] **Step 6: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 7: Ejecutar el job de verdad**

Run: `.venv/bin/python scripts/snapshot_social.py --dias 90`
Expected: Instagram y YouTube con filas de demografía; LinkedIn saltada por credenciales; Facebook con su nota.

- [ ] **Step 8: Commit**

```bash
git add scripts/snapshot_social.py tests/test_snapshot_demografia.py data/historico_social
git commit -m "feat: el job diario acumula la demografía de audiencia

Segunda fase del snapshot, con la misma regla que la primera: llama a las
funciones _api_* directamente, nunca a la cascada, para que un fallo no pueda
escribir datos de ejemplo en el histórico.

Se acumula desde el primer día por la lección de los seguidores de Instagram:
las APIs dan la foto de hoy y el pasado no se reconstruye. Hoy solo se enseña
la foto; cuando haya meses acumulados se podrá ver la deriva de la audiencia.

Facebook no tiene fase: Meta retiró su demografía y no hay sustituto."
```

---

### Task 11: `social_red` — bloques de titular, KPIs y evolución

**Files:**
- Create: `src/ui/social_red.py`
- Test: `tests/test_social_red.py`

**Interfaces:**
- Consumes: `social_analisis.comparar_kpis`, `config.soporta_metrica`, `ui.kpi`, `ui.linea_temporal`
- Produces:
  - `frases_titular(kpis: pd.DataFrame, red: str) -> list[str]`
  - `metricas_de_la_red(red: str) -> dict[str, str]`
  - `bloque_kpis(kpis: pd.DataFrame) -> None`
  - `bloque_evolucion(diario, red, key) -> None`

- [ ] **Step 1: Escribir los tests que fallan**

`tests/test_social_red.py`:

```python
import pandas as pd

from src import config
from src.ui import social_red as sr


def _kpis(filas):
    return pd.DataFrame(filas)


def test_el_selector_de_metricas_solo_ofrece_lo_que_la_red_publica():
    """Ofrecer una métrica que siempre saldrá vacía es prometer algo que no se
    va a cumplir. Facebook no tiene alcance ni impresiones."""
    fb = sr.metricas_de_la_red("Facebook")
    assert "alcance" not in fb
    assert "impresiones" not in fb
    assert "visualizaciones" in fb

    ig = sr.metricas_de_la_red("Instagram")
    assert "alcance" in ig
    assert "impresiones" not in ig


def test_el_titular_nombra_la_metrica_y_su_variacion():
    frases = sr.frases_titular(_kpis([
        {"metrica": "visualizaciones", "etiqueta": "Visualizaciones",
         "actual": 151551.0, "anterior": 135200.0, "delta_pct": 12.1},
    ]), "Instagram")
    texto = " ".join(frases)
    assert "Visualizaciones" in texto
    assert "12,1" in texto or "12.1" in texto


def test_el_titular_omite_las_frases_sin_dato():
    """Si falta el dato, la frase no aparece; no se rellena con texto vago."""
    frases = sr.frases_titular(_kpis([
        {"metrica": "visualizaciones", "etiqueta": "Visualizaciones",
         "actual": None, "anterior": None, "delta_pct": None},
    ]), "Instagram")
    assert frases == []


def test_el_titular_no_inventa_variacion_sin_periodo_anterior():
    frases = sr.frases_titular(_kpis([
        {"metrica": "visualizaciones", "etiqueta": "Visualizaciones",
         "actual": 100.0, "anterior": None, "delta_pct": None},
    ]), "Instagram")
    texto = " ".join(frases)
    assert "Visualizaciones" in texto
    assert "%" not in texto
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_social_red.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.ui.social_red'`

- [ ] **Step 3: Crear el módulo con los tres primeros bloques**

`src/ui/social_red.py`:

```python
"""
Dibuja UNA pestaña de red de la página de Social Orgánico.

Las cuatro redes comparten los mismos bloques y en el mismo orden, para que se
puedan comparar de memoria; lo que cambia es el contenido, porque cada API
ofrece cosas distintas. Donde una red no da algo, el bloque lo DICE en vez de
desaparecer o salir vacío: esa asimetría es información.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from src import config
from src.data import social_analisis as sa
from src.ui import components as ui
from src.ui.theme import num_o_guion, pct_o_guion


def metricas_de_la_red(red: str) -> dict[str, str]:
    """{metrica: etiqueta} de lo que ESA red publica.

    Filtra el selector para no ofrecer métricas que siempre saldrían vacías:
    Facebook no tiene alcance ni impresiones desde que Meta las retiró.
    """
    return {m: e for m, e in config.METRICAS_SOCIAL.items()
            if config.soporta_metrica(m, red)}


def _pct(x: float) -> str:
    """Porcentaje con coma decimal y signo explícito."""
    return f"{'+' if x > 0 else ''}{x:,.1f}".replace(".", ",") + "%"


def frases_titular(kpis: pd.DataFrame, red: str) -> list[str]:
    """Frases del titular, construidas con datos y plantillas.

    Nunca texto libre: si falta el dato de una frase, esa frase no aparece. Un
    titular que rellena huecos con vaguedades es peor que no tener titular.
    """
    if kpis is None or kpis.empty:
        return []

    frases = []
    principal = kpis[kpis["metrica"] == "visualizaciones"]
    if not principal.empty and pd.notna(principal.iloc[0]["actual"]):
        fila = principal.iloc[0]
        txt = f"{fila['etiqueta']}: {num_o_guion(fila['actual'])}"
        if pd.notna(fila["delta_pct"]):
            txt += f" ({_pct(float(fila['delta_pct']))} vs. periodo anterior)"
        frases.append(txt + ".")

    seguidores = kpis[kpis["metrica"] == "seguidores_nuevos"]
    if not seguidores.empty and pd.notna(seguidores.iloc[0]["actual"]):
        fila = seguidores.iloc[0]
        txt = f"{num_o_guion(fila['actual'])} seguidores nuevos"
        if pd.notna(fila["delta_pct"]):
            txt += f" ({_pct(float(fila['delta_pct']))})"
        frases.append(txt + ".")

    caidas = kpis[kpis["delta_pct"].notna() & (kpis["delta_pct"] < -20)]
    if not caidas.empty:
        peor = caidas.sort_values("delta_pct").iloc[0]
        frases.append(f"Atención: {peor['etiqueta'].lower()} cae "
                      f"{_pct(float(peor['delta_pct']))}.")
    return frases


def bloque_titular(kpis: pd.DataFrame, red: str) -> None:
    frases = frases_titular(kpis, red)
    if frases:
        ui.resumen_ejecutivo(" ".join(frases))


def bloque_kpis(kpis: pd.DataFrame) -> None:
    """Tabla `Métrica · Periodo · Anterior · Δ`.

    Usa `num_o_guion`, nunca `num()`: un nulo aquí significa «no hay dato del
    periodo anterior», y pintarlo como 0 diría que cayó a cero.
    """
    if kpis is None or kpis.empty:
        st.info("Sin métricas para esta red en el periodo.")
        return

    filas = [{
        "metrica": k["etiqueta"],
        "actual": num_o_guion(k["actual"]),
        "anterior": num_o_guion(k["anterior"]),
        "delta": "—" if pd.isna(k["delta_pct"]) else _pct(float(k["delta_pct"])),
    } for _, k in kpis.iterrows()]

    ui.tabla(pd.DataFrame(filas), [
        {"key": "metrica", "label": "Métrica", "align": "l"},
        {"key": "actual", "label": "Periodo", "align": "r"},
        {"key": "anterior", "label": "Anterior", "align": "r"},
        {"key": "delta", "label": "Δ", "align": "r"},
    ])

    if kpis["anterior"].isna().all():
        st.caption("No hay histórico del periodo anterior para comparar. "
                   "Se irá llenando conforme el job diario acumule días.")


def bloque_evolucion(diario: pd.DataFrame, red: str, key: str) -> None:
    from src.data import social

    metricas = metricas_de_la_red(red)
    if not metricas:
        st.info("Esta red no publica métricas diarias.")
        return

    etiquetas = {e: m for m, e in metricas.items()}
    elegida = st.selectbox("Métrica", list(etiquetas), key=key)
    serie = social.serie_diaria(diario[diario["red"] == red], etiquetas[elegida])
    if serie.empty:
        st.info(f"Sin datos de «{elegida}» en el periodo.")
        return
    ui.linea_temporal(serie, x="fecha", y="valor", color="red",
                      titulo=f"{elegida} por día", y_label=elegida,
                      simbolos=config.SIMBOLO_RED_SOCIAL)
```

- [ ] **Step 4: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 5: Commit**

```bash
git add src/ui/social_red.py tests/test_social_red.py
git commit -m "feat: bloques de titular, KPIs y evolución de una pestaña de red

El selector de métrica se filtra a lo que cada red publica: ofrecer 'Alcance'
en Facebook, que Meta retiró, es prometer algo que no se va a cumplir.

El titular se construye con plantillas y datos, nunca con texto libre: si falta
el dato de una frase, la frase no aparece. Un titular que rellena huecos con
vaguedades es peor que no tener titular."
```

---

### Task 12: `social_red` — bloques de contenido y audiencia

**Files:**
- Modify: `src/ui/social_red.py`
- Test: `tests/test_social_red.py` (añadir)

**Interfaces:**
- Consumes: `social_analisis.ranking`, `hay_muestra_para_bottom`, `por_formato`, `criterio_ranking`, `social_demografia.ultima_foto`, `etiqueta_unidad`
- Produces:
  - `bloque_contenido(posts, red) -> None`
  - `bloque_audiencia(demografia, red, hasta) -> None`
  - `pestana(red, diario, posts, demografia, desde, hasta) -> None`

- [ ] **Step 1: Escribir los tests que fallan**

Añadir a `tests/test_social_red.py`:

```python
from datetime import date

from src.data import social, social_demografia as sd


def test_el_texto_de_las_publicaciones_va_escapado():
    """`ui.tabla` inyecta HTML sin escapar y los títulos vienen de una API."""
    p = social.normalizar_posts(pd.DataFrame([{
        "red": "Instagram", "post_id": "1", "tipo": "Reel",
        "titulo": "<script>alert(1)</script>", "url": "https://x.test",
        "visualizaciones": 10, "likes": 1}]))
    filas = sr.filas_publicaciones(p, "Instagram")
    assert "<script>" not in filas.iloc[0]["titulo"]
    assert "&lt;script&gt;" in filas.iloc[0]["titulo"]


def test_la_url_no_http_no_se_convierte_en_enlace():
    p = social.normalizar_posts(pd.DataFrame([{
        "red": "Instagram", "post_id": "1", "tipo": "Reel",
        "titulo": "hola", "url": "javascript:alert(1)",
        "visualizaciones": 10, "likes": 1}]))
    filas = sr.filas_publicaciones(p, "Instagram")
    assert "javascript:" not in filas.iloc[0]["titulo"]


def test_el_aviso_de_criterio_dice_como_se_ordena_facebook():
    assert "interacciones" in sr.nota_criterio("Facebook").lower()
    assert "engagement" in sr.nota_criterio("Instagram").lower()


def test_la_audiencia_declara_su_unidad():
    """Instagram cuenta personas; YouTube, % de visualizaciones."""
    assert "sigue" in sr.nota_unidad("Instagram").lower()
    assert "%" in sr.nota_unidad("YouTube")
    assert sr.nota_unidad("Facebook") == ""
```

- [ ] **Step 2: Ejecutar y ver que falla**

Run: `.venv/bin/python -m pytest tests/test_social_red.py -v`
Expected: FAIL — `AttributeError: module has no attribute 'filas_publicaciones'`

- [ ] **Step 3: Implementar los bloques**

Añadir a `src/ui/social_red.py`:

```python
import html

from src.data import social_demografia as sd


def _enlace(titulo, url) -> str:
    """Título escapado, como enlace solo si la URL es http(s).

    `ui.tabla` inyecta HTML sin escapar y estos títulos vienen de una API, así
    que escapar aquí no es opcional. Y solo se aceptan esquemas http/https:
    un `javascript:` en un href sería ejecutable.
    """
    texto = html.escape(str(titulo or ""))
    u = str(url or "")
    if u.startswith(("http://", "https://")):
        return f'<a href="{html.escape(u)}" target="_blank">{texto}</a>'
    return texto


def filas_publicaciones(posts: pd.DataFrame, red: str) -> pd.DataFrame:
    """Publicaciones de una red listas para `ui.tabla`, con el texto escapado."""
    d = posts[posts["red"] == red].copy()
    if d.empty:
        return d
    d["titulo"] = [_enlace(t, u) for t, u in zip(d["titulo"], d["url"])]
    return d


def nota_criterio(red: str) -> str:
    """Explica por qué está ordenado así el ranking de esa red."""
    if sa.criterio_ranking(red) == "interacciones":
        return ("Ordenado por interacciones: Facebook solo publica "
                "visualizaciones en vídeo y reels, así que no hay denominador "
                "para calcular la tasa de engagement.")
    return "Ordenado por tasa de engagement (interacciones ÷ visualizaciones)."


def nota_unidad(red: str) -> str:
    """La unidad de la demografía, escrita DENTRO del bloque."""
    unidad = sd.UNIDAD_POR_RED.get(red)
    if not unidad:
        return ""
    if unidad == "pct_visualizaciones":
        return ("Estos porcentajes son de las **visualizaciones**, no de tus "
                "suscriptores: describen quién consume, no cuánta gente eres. "
                "No son comparables con los de Instagram.")
    return "Personas que te **siguen**."


def bloque_contenido(posts: pd.DataFrame, red: str) -> None:
    d = posts[posts["red"] == red]
    n = len(d)
    if n == 0:
        st.info("Sin publicaciones de esta red en el periodo.")
        return

    st.caption(f"{n} publicaciones en el periodo. {nota_criterio(red)}")

    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("**Mejores publicaciones**")
        top = sa.ranking(posts, red, n=3, mejores=True)
        st.dataframe(filas_publicaciones(top, red)[["fecha", "tipo", "titulo"]],
                     hide_index=True, width="stretch")
    with col_b:
        st.markdown("**Peores publicaciones**")
        if sa.hay_muestra_para_bottom(posts, red):
            bot = sa.ranking(posts, red, n=3, mejores=False)
            st.dataframe(filas_publicaciones(bot, red)[["fecha", "tipo", "titulo"]],
                         hide_index=True, width="stretch")
        else:
            st.info(f"Hacen falta al menos {config.MIN_PUBLICACIONES_BOTTOM} "
                    f"publicaciones para que «las peores» signifiquen algo. "
                    f"Ahora hay {n}.")

    formatos = sa.por_formato(posts, red)
    if not formatos.empty:
        st.markdown("**Rendimiento por formato**")
        ui.tabla(pd.DataFrame([{
            "tipo": f["tipo"], "n": num_o_guion(f["n"]),
            "vis": num_o_guion(f["visualizaciones_media"]),
            "eng": pct_o_guion(f["engagement_medio"]),
        } for _, f in formatos.iterrows()]), [
            {"key": "tipo", "label": "Formato", "align": "l"},
            {"key": "n", "label": "Publicaciones", "align": "r"},
            {"key": "vis", "label": "Visualizaciones (media)", "align": "r"},
            {"key": "eng", "label": "Engagement (media)", "align": "r"},
        ])
    else:
        st.caption(f"Ningún formato llega a {config.MIN_PUBLICACIONES_FORMATO} "
                   "publicaciones, que es el mínimo para que una media diga algo.")

    st.markdown("**Todas las publicaciones**")
    cols = ["fecha", "tipo", "titulo"] + [
        m for m in config.METRICAS_POST if config.soporta_metrica(m, red, "post")]
    st.dataframe(filas_publicaciones(d, red)[cols], hide_index=True, width="stretch")


def bloque_audiencia(demografia: pd.DataFrame, red: str, hasta) -> None:
    if red not in sd.UNIDAD_POR_RED:
        st.info("Facebook no publica demografía de audiencia: Meta retiró esas "
                "métricas de las Páginas en 2025 y no hay sustituto.")
        return

    foto = sd.ultima_foto(demografia, red, hasta)
    if foto.empty:
        st.info("Todavía no hay demografía capturada de esta red. La recoge "
                "`scripts/snapshot_social.py` en su ejecución diaria.")
        return

    st.caption(f"{nota_unidad(red)}  ·  Captura del {foto.iloc[0]['fecha']}.")

    for dimension in ("edad", "genero", "pais", "ciudad",
                      "cargo", "funcion", "sector", "tamano_empresa"):
        d = foto[foto["dimension"] == dimension]
        if d.empty:
            continue
        st.markdown(f"**{dimension.replace('_', ' ').capitalize()}**")
        ui.barras_horizontales(
            d.sort_values("valor", ascending=False).head(10),
            etiqueta_col="categoria", valor_col="valor",
            x_label=sd.etiqueta_unidad(str(d.iloc[0]["unidad"])))


def pestana(red: str, diario: pd.DataFrame, posts: pd.DataFrame,
            demografia: pd.DataFrame, kpis: pd.DataFrame, hasta) -> None:
    """Los cinco bloques de una red, siempre en el mismo orden."""
    bloque_titular(kpis, red)

    st.subheader("Rendimiento")
    bloque_kpis(kpis)

    st.subheader("Evolución")
    bloque_evolucion(diario, red, key=f"metrica_{red}")

    st.subheader("Contenido")
    bloque_contenido(posts, red)

    st.subheader("Audiencia")
    bloque_audiencia(demografia, red, hasta)
```

- [ ] **Step 4: Ejecutar los tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: todos PASS

- [ ] **Step 5: Commit**

```bash
git add src/ui/social_red.py tests/test_social_red.py
git commit -m "feat: bloques de contenido y audiencia de una pestaña de red

El listado escapa el HTML de los títulos —vienen de una API y ui.tabla inyecta
sin escapar— y solo convierte en enlace las URL http(s): un javascript: en un
href sería ejecutable.

El bloque de contenido declara siempre su tamaño de muestra y por qué está
ordenado como está. Oculta 'las peores' por debajo del umbral, en vez de
afirmar que la segunda de dos es la peor.

El de audiencia escribe la unidad DENTRO del bloque, porque Instagram cuenta
personas y YouTube porcentaje de visualizaciones, y Facebook dice explícitamente
que Meta retiró esas métricas."
```

---

### Task 13: Montar las pestañas en la página

**Files:**
- Modify: `pages/6_📣_Social_Orgánico.py`
- Modify: `src/data/loader.py`
- Test: manual con `streamlit.testing.AppTest`

**Interfaces:**
- Consumes: `social_red.pestana`, `social_analisis.periodo_anterior`, `comparar_kpis`
- Produces: `loader.cargar_social` devuelve además `demografia: pd.DataFrame` en `DatosSocial`

- [ ] **Step 1: Añadir la demografía al loader**

En `src/data/loader.py`, en `DatosSocial`, añadir el campo:

```python
    demografia: pd.DataFrame = None  # una fila por (fecha, red, dimension, categoria)
```

Y en `_cargar_social`, tras el bucle de fuentes:

```python
    # La demografía sale SOLO del histórico que acumula el job: son fotos
    # «lifetime» que no dependen del periodo elegido y no tiene sentido pedirlas
    # a la API en cada carga de página.
    demos = []
    for red in config.REDES_SOCIAL:
        bruto = leer_historico(f"social_{red.lower()}_demografia")
        if bruto is not None and not bruto.empty:
            demos.append(social_demografia.normalizar(bruto))
    demografia = (pd.concat(demos, ignore_index=True) if demos
                  else social_demografia.esquema_vacio())
```

Devolverla en la tupla y en `cargar_social`. Añadir las importaciones:

```python
from src.connectors.base import leer_historico
from src.data import social_demografia
```

- [ ] **Step 2: Envolver el contenido actual en la pestaña «Resumen»**

En `pages/6_📣_Social_Orgánico.py`, tras el bloque del aviso de mezcla (la
línea que cierra el `st.warning(...)`), insertar:

```python
tab_resumen, *tabs_red = st.tabs(["Resumen"] + list(config.REDES_SOCIAL))
```

Después hay que indentar bajo `with tab_resumen:` TODO lo que va desde
`ui.cabecera("Social orgánico", ...)` hasta el final del fichero actual.

Son ~250 líneas, así que **no lo hagas a mano**: usa un script que reindente
el rango exacto, y comprueba el resultado con `python -m py_compile` antes de
seguir.

```python
# Reindentación mecánica. Ajusta INICIO al número de línea de `ui.cabecera(`.
import pathlib
p = pathlib.Path("pages/6_📣_Social_Orgánico.py")
lineas = p.read_text().splitlines(keepends=True)
INICIO = next(i for i, l in enumerate(lineas) if l.startswith("ui.cabecera("))
cuerpo = ["    " + l if l.strip() else l for l in lineas[INICIO:]]
p.write_text("".join(lineas[:INICIO] + ["with tab_resumen:\n"] + cuerpo))
```

⚠️ Las funciones auxiliares definidas en el cuerpo de la página (`_enlace`,
etc.) quedarían dentro del `with`. Súbelas ANTES de la línea de `st.tabs`
para que sigan siendo de módulo, o el resto del fichero no las verá.

Verifica con: `.venv/bin/python -m py_compile "pages/6_📣_Social_Orgánico.py"`

- [ ] **Step 3: Añadir las pestañas de red**

Al final del fichero:

```python
# --------------------------------------------------------------------------- #
# Una pestaña por red
#
# Los KPIs del periodo anterior se piden con su propio rango: `cargar_social`
# está cacheada por (desde, hasta), así que esta segunda llamada reutiliza la
# caché entre pestañas en vez de repetir ocho llamadas a las APIs.
# --------------------------------------------------------------------------- #
d_ant, h_ant = social_analisis.periodo_anterior(desde, hasta)
datos_ant = loader.cargar_social(d_ant, h_ant)

for tab, red in zip(tabs_red, config.REDES_SOCIAL):
    with tab:
        if datos.origenes.get(red) == "sample":
            st.warning(
                f"**{red} está con datos de ejemplo.** Todo lo que veas en esta "
                "pestaña es inventado: sirve para comprobar la estructura, no "
                "para tomar decisiones."
            )
        kpis = social_analisis.comparar_kpis(datos.diario, datos_ant.diario, red)
        social_red.pestana(red, datos.diario, datos.posts,
                           datos.demografia, kpis, hasta)
```

Y añadir las importaciones al principio:

```python
from src.data import social_analisis
from src.ui import social_red
```

- [ ] **Step 4: Comprobar que las 7 páginas siguen corriendo**

Run:
```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from pathlib import Path
from streamlit.testing.v1 import AppTest
for p in [Path('Resumen_Total.py')] + sorted(Path('pages').glob('*.py')):
    at = AppTest.from_file(str(p), default_timeout=300).run()
    print(('OK ' if not at.exception else 'FALLO '), p.name,
          [e.value for e in at.exception][:1])"
```
Expected: 7 páginas OK, ninguna excepción.

- [ ] **Step 5: Comprobar que las pestañas de red se pintan**

Run:
```bash
.venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from streamlit.testing.v1 import AppTest
at = AppTest.from_file('pages/6_📣_Social_Orgánico.py', default_timeout=300).run()
assert not at.exception, [e.value for e in at.exception]
print('pestañas:', [t.label for t in at.tabs] if hasattr(at,'tabs') else 'n/d')
print('subheaders:', [s.value for s in at.subheader][:12])"
```
Expected: 5 pestañas y los subtítulos Rendimiento / Evolución / Contenido / Audiencia repetidos.

- [ ] **Step 6: Commit**

```bash
git add pages/ src/data/loader.py
git commit -m "feat: una pestaña de análisis por red en Social Orgánico

Resumen (la vista comparativa de siempre, intacta) más una pestaña por red con
los cinco bloques.

Los KPIs del periodo anterior se piden con una segunda llamada a
cargar_social, que está cacheada por rango: las cuatro pestañas comparten esa
carga en vez de repetir ocho llamadas a las APIs.

La demografía se lee solo del histórico que acumula el job: son fotos lifetime
que no dependen del periodo elegido, así que pedirlas en cada carga de página
sería gastar cuota para nada.

Cada pestaña avisa si esa red va con datos de ejemplo: en una vista dedicada a
una sola red, un dato inventado sin aviso es más peligroso todavía que en la
comparativa."
```

---

### Task 14: Documentación

**Files:**
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `data/historico_social/README.md`

- [ ] **Step 1: Añadir las trampas nuevas a CLAUDE.md**

En la sección «⚠️ Trampas NO obvias», añadir:

```markdown
- **La demografía NO mide lo mismo en cada red.** Instagram cuenta PERSONAS que
  te siguen; YouTube da el % de VISUALIZACIONES por tramo. Poblaciones y
  unidades distintas: `social_demografia` las marca con `unidad` y la UI la
  escribe dentro del bloque. Nunca comparten gráfico.
- **Facebook no tiene demografía ni impresiones por publicación.** Meta retiró
  `page_fans_*` y `post_impressions*`. Lo que sí da y nadie más: `post_clicks`
  y `post_reactions_by_type_total`. Por eso su ranking se ordena por
  interacciones y no por tasa de engagement (`social_analisis.criterio_ranking`).
- **LinkedIn no publica edad ni género.** Da cargo, función, sector, tamaño de
  empresa y país. Hay un test que lo fija.
- **Los umbrales de muestra están en `config`** (`MIN_PUBLICACIONES_BOTTOM`,
  `MIN_PUBLICACIONES_FORMATO`), no repartidos: el volumen está creciendo.
```

- [ ] **Step 2: Documentar las pestañas en README.md**

En la tabla de páginas, cambiar la fila de Social Orgánico:

```markdown
| **📣 Social Orgánico** | Resumen comparativo entre redes + **una pestaña por red** con KPIs contra el periodo anterior, evolución, rendimiento de publicaciones y demografía de audiencia. Solo alcance no pagado. |
```

Y añadir tras la sección del job diario:

```markdown
### Tests

```bash
pip install -r requirements-dev.txt
python -m pytest tests/ -v
```

Los módulos de datos (`social_analisis`, `social_demografia`) no importan
Streamlit a propósito: se prueban con DataFrames sueltos, sin levantar la app.
```

- [ ] **Step 3: Documentar los ficheros de demografía**

En `data/historico_social/README.md`, tras la lista de ficheros:

```markdown
Y la demografía de audiencia, en formato largo:

```
social_youtube_demografia.csv    social_instagram_demografia.csv
social_linkedin_demografia.csv
```

Columnas: `fecha` · `red` · `dimension` · `categoria` · `valor` · `unidad`.

⚠️ **`unidad` no es decorativa.** Instagram cuenta personas que te siguen
(`seguidores`); YouTube da el % de visualizaciones (`pct_visualizaciones`).
Sumar o comparar filas de unidades distintas no significa nada.

Facebook no aparece: Meta retiró la demografía de Páginas.
```

- [ ] **Step 4: Ejecutar la batería completa**

Run: `.venv/bin/python -m pytest tests/ -v` y el AppTest de las 7 páginas.
Expected: todo PASS.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md data/historico_social/README.md
git commit -m "docs: pestañas por red, demografía y sus trampas

Se documentan las cuatro trampas que costó descubrir: que la demografía no mide
lo mismo en cada red, que Facebook no tiene ni demografía ni impresiones por
publicación (pero sí clics y reacciones por tipo), que LinkedIn no publica edad
ni género, y que los umbrales de muestra viven en config porque el volumen está
creciendo."
```

---

## Resumen de tareas

| # | Tarea | Entregable comprobable |
|---|---|---|
| 1 | Infraestructura de tests | `pytest` corre y puede importar `src` |
| 2 | Constantes y métrica `clics` | Tests de config en verde |
| 3 | Comparativa de KPIs | Periodo anterior correcto, sin división por cero |
| 4 | Ranking y formatos | Umbrales respetados, Facebook por interacciones |
| 5 | Esquema de demografía | Unidades correctas, `ultima_foto` no mezcla capturas |
| 6 | Demografía de Instagram | 4 dimensiones contra la cuenta real |
| 7 | Demografía de YouTube | 3 dimensiones contra el canal real |
| 8 | Demografía de LinkedIn | Traducción probada con respuesta simulada |
| 9 | Métricas de publicación de Facebook | `clics` con valores reales |
| 10 | El job la acumula | CSV escritos, nada sin credenciales |
| 11 | Titular, KPIs, evolución | Selector filtrado por red |
| 12 | Contenido y audiencia | HTML escapado, unidad declarada |
| 13 | Pestañas en la página | 7 páginas sin excepciones, 5 pestañas |
| 14 | Documentación | Trampas registradas |

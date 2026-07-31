"""
Dibuja UNA pestaña de red de la página de Social Orgánico.

Las cuatro redes comparten los mismos bloques y en el mismo orden, para que se
puedan comparar de memoria; lo que cambia es el contenido, porque cada API
ofrece cosas distintas. Donde una red no da algo, el bloque lo DICE en vez de
desaparecer o salir vacío: esa asimetría es información.
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src import config
from src.data import social_analisis as sa
from src.data import social_demografia as sd
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
    """Porcentaje con coma decimal, punto de miles y signo explícito.

    El intercambio se hace en tres pasos con un carácter puente para que el
    punto acabe de separador de miles y la coma de decimal (convención
    española), sin que un paso pise al otro. A partir de ±1000% hacen falta
    los dos separadores: sin punto de miles, "+2.400,0%" saldría "+2,400,0%",
    con dos comas e ilegible.
    """
    txt = f"{x:,.1f}".replace(",", "·").replace(".", ",").replace("·", ".")
    return f"{'+' if x > 0 else ''}{txt}%"


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


@st.cache_data(ttl=900, show_spinner=False)
def _cuenta_conectada(red: str) -> dict:
    """Cuenta que ha autorizado la conexión, si la red la identifica.

    Solo TikTok: es la única que se autoriza por OAuth de la cuenta misma, así
    que el token puede apuntar a un titular equivocado sin que nada más lo
    delate. Meta va con token de Página y YouTube con el ID de canal de
    `config`, donde la cuenta es fija y no hay nada que confirmar.

    Cacheado 15 min: es una llamada extra a la API y el nombre no cambia.
    """
    if red != "TikTok":
        return {}
    from src.connectors import tiktok

    return tiktok.cuenta()


def bloque_cuenta(red: str) -> None:
    """Una línea con la cuenta conectada. Silenciosa si la red no la da."""
    datos = _cuenta_conectada(red)
    nombre = datos.get("nombre")
    if not nombre:
        return
    # Sin negritas ni markdown alrededor del nombre: viene de una API y un
    # asterisco o un guion bajo descolocarían el renderizado.
    st.caption(f"Cuenta conectada: {nombre} · "
               f"{num_o_guion(datos.get('seguidores'))} seguidores")


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

    # Los valores viajan como NÚMEROS para que la tabla se pueda ordenar; el
    # formateo lo pone `column_config`. Ordenar por Δ es lo que responde «qué se
    # ha caído más este periodo», que es media razón de ser de esta tabla.
    # Se usa `etiqueta` (el nombre legible) y NO se renombra a `metrica`: el df
    # ya trae una columna con ese nombre —la clave interna— y renombrar dejaba
    # dos columnas iguales, que revientan al serializar a Arrow.
    ui.tabla_ordenable(kpis, [
        {"key": "etiqueta", "label": "Métrica"},
        {"key": "actual", "label": "Periodo", "tipo": "numero"},
        {"key": "anterior", "label": "Anterior", "tipo": "numero"},
        {"key": "delta_pct", "label": "Δ %", "tipo": "decimal",
         "ayuda": "Variación frente al periodo anterior. Vacío = no hay "
                  "histórico con el que comparar."},
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


def _texto_seguro(v):
    """Escapa un valor para HTML, dejando pasar los nulos intactos.

    `ui.tabla` inyecta HTML sin escapar, así que cualquier texto que venga de
    datos (no de una plantilla fija de la app) tiene que pasar por aquí antes
    de llegar a ella. Un nulo se deja tal cual para que `ui.tabla` lo siga
    pintando como celda vacía en vez de convertirlo en el texto "nan"/"NaT".
    """
    return v if pd.isna(v) else html.escape(str(v))


def filas_publicaciones(posts: pd.DataFrame, red: str) -> pd.DataFrame:
    """Publicaciones de una red listas para `ui.tabla_ordenable`.

    El texto va CRUDO, sin escapar, y las métricas siguen siendo NÚMEROS. Las
    dos cosas son requisito de `st.dataframe`, que es lo que da la ordenación
    por encabezado:

    - No interpreta HTML, así que escapar aquí solo conseguiría que se viera un
      `&#x27;` por cada apóstrofo de un pie de foto. Y como no lo interpreta,
      tampoco hay nada que inyectar: la protección viene de que el destino no
      renderiza, no de escapar antes.
    - Ordenar exige números de verdad. Formateados como texto, «1.000» quedaría
      antes que «9»; por eso el formateo se delega a `column_config`.

    La fecha se convierte a datetime para que ordene cronológicamente y no
    alfabéticamente, que con el formato dd/mm/aaaa daría un orden absurdo.
    """
    d = posts[posts["red"] == red].copy()
    if d.empty:
        return d
    d["fecha"] = pd.to_datetime(d["fecha"], errors="coerce")
    return d


_COLUMNAS_PUBLICACIONES_BASE = [
    {"key": "fecha", "label": "Fecha", "tipo": "fecha", "ancho": "small"},
    {"key": "tipo", "label": "Formato", "ancho": "small"},
    {"key": "titulo", "label": "Publicación", "ancho": "large"},
    {"key": "url", "label": "Ver", "tipo": "enlace", "texto_enlace": "Abrir",
     "ancho": "small"},
]


def _columnas_publicaciones(metricas: list[str] | None = None) -> list[dict]:
    """Columnas para `ui.tabla_ordenable` de una tabla de publicaciones.

    El enlace va en columna propia en vez de envolver el título porque
    `LinkColumn` solo sabe mostrar un texto fijo o uno extraído de la propia
    URL, no el valor de otra columna. A cambio, el título queda como texto y se
    puede ordenar alfabéticamente.
    """
    columnas = list(_COLUMNAS_PUBLICACIONES_BASE)
    for m in metricas or []:
        columnas.append({"key": m, "label": config.METRICAS_POST.get(m, m),
                         "tipo": "numero"})
    return columnas


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
        return ("Estos son % de las **visualizaciones**, no de tus "
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
        ui.tabla_ordenable(filas_publicaciones(top, red), _columnas_publicaciones())
    with col_b:
        st.markdown("**Peores publicaciones**")
        if sa.hay_muestra_para_bottom(posts, red):
            bot = sa.ranking(posts, red, n=3, mejores=False)
            ui.tabla_ordenable(filas_publicaciones(bot, red),
                               _columnas_publicaciones())
        else:
            st.info(f"Hacen falta al menos {config.MIN_PUBLICACIONES_BOTTOM} "
                    f"publicaciones para que «las peores» signifiquen algo. "
                    f"Ahora hay {n}.")

    formatos = sa.por_formato(posts, red)
    if not formatos.empty:
        st.markdown("**Rendimiento por formato**")
        ui.tabla_ordenable(formatos.rename(columns={
            "visualizaciones_media": "vis", "engagement_medio": "eng"}), [
            {"key": "tipo", "label": "Formato"},
            {"key": "n", "label": "Publicaciones", "tipo": "numero"},
            {"key": "vis", "label": "Visualizaciones (media)", "tipo": "numero"},
            {"key": "eng", "label": "Engagement (media)", "tipo": "porcentaje"},
        ])
    else:
        st.caption(f"Ningún formato llega a {config.MIN_PUBLICACIONES_FORMATO} "
                   "publicaciones, que es el mínimo para que una media diga algo.")

    st.markdown("**Todas las publicaciones**")
    metricas = [m for m in config.METRICAS_POST if config.soporta_metrica(m, red, "post")]
    ui.tabla_ordenable(filas_publicaciones(d, red), _columnas_publicaciones(metricas))
    st.caption(
        "Pulsa el encabezado de cualquier columna para ordenar. Una celda "
        "**vacía** significa que esa red no publica ese dato por API; un **0** "
        "es un cero real."
    )


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
    bloque_cuenta(red)
    bloque_titular(kpis, red)

    st.subheader("Rendimiento")
    bloque_kpis(kpis)

    st.subheader("Evolución")
    bloque_evolucion(diario, red, key=f"metrica_{red}")

    st.subheader("Contenido")
    bloque_contenido(posts, red)

    st.subheader("Audiencia")
    bloque_audiencia(demografia, red, hasta)

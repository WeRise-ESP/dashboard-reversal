"""Página: Social orgánico — YouTube, Facebook, Instagram y LinkedIn.

Métricas de cuenta y de cada publicación, sin nada de pago.

⚠️ Regla que gobierna toda esta página: cuando una red NO publica una métrica se
muestra "—", nunca 0, y los agregados dicen qué redes quedan fuera. Ver la nota
al pie de la página y `src/config.py` (SOPORTE_METRICA_SOCIAL).
"""
from __future__ import annotations

import html

import pandas as pd
import streamlit as st

from src import config
from src.data import loader, social
from src.data import social_analisis
from src.ui import components as ui
from src.ui import social_red
from src.ui.theme import aplicar_tema, num, num_o_guion, pct_o_guion

st.set_page_config(page_title="Social orgánico · Reversal", page_icon="📣",
                   layout="wide")
aplicar_tema()

desde, hasta, etq = ui.selector_periodo()

# El periodo anterior se resuelve AQUÍ, antes que el actual, y no al final del
# fichero (donde se usa). `social_base.resolver` guarda en disco la última
# respuesta de la API (`guardar_cache`) y esa caché NO está indexada por rango:
# guarda una ventana por conector, la que se haya resuelto en ÚLTIMO lugar. Si
# `datos_ant` se resolviera después de `datos` —como ocurría antes—, los
# parquet se quedarían con la ventana VIEJA: el primer nivel de reserva de la
# cascada apuntando a un rango sin intersección con lo que el usuario mira.
# Resolviendo el periodo anterior primero, es `datos` quien escribe último y
# la caché en disco queda alineada con la pantalla.
d_ant, h_ant = social_analisis.periodo_anterior(desde, hasta)
datos_ant = loader.cargar_social(d_ant, h_ant)

datos = loader.cargar_social(desde, hasta)
ui.aviso_origenes(
    datos.origenes,
    nota=f"Social se refresca cada {config.CACHE_TTL_SOCIAL // 60} min. "
         "Cada red se resuelve por separado: API → caché → CSV → ejemplo.",
)

def _enlace(titulo: str, url: str) -> str:
    """Título escapado, como enlace si la URL es http(s).

    `ui.tabla` inserta el valor en el HTML sin escapar, así que el escapado se
    hace aquí: los textos vienen de las APIs y pueden traer <, & o comillas.
    """
    texto = html.escape(str(titulo or ""))
    u = str(url or "")
    if not u.startswith(("http://", "https://")):
        return texto
    return (f'<a href="{html.escape(u, quote=True)}" target="_blank" '
            f'rel="noopener noreferrer" style="color:inherit;">{texto}</a>')


def _frase_soporte(etiqueta: str, metrica: str, ambito: str = "diario") -> str:
    """«Impresiones: sin dato en YouTube ni Instagram.» / «…: las 4 redes.»

    Se usa «sin dato en» y no «no la publican» para que la frase valga con
    métricas de cualquier género (impresiones, mensajes, guardados) sin fallar la
    concordancia.
    """
    fuera = config.redes_sin_metrica(metrica, ambito)
    if not fuera:
        return f"{etiqueta}: las 4 redes."
    listado = (fuera[0] if len(fuera) == 1
               else ", ".join(fuera[:-1]) + f" ni {fuera[-1]}")
    return f"{etiqueta}: sin dato en {listado}."


# Una pestaña «Resumen» (la vista comparativa de siempre) más una por red.
# Las funciones auxiliares de arriba quedan a propósito FUERA de este punto en
# adelante: si estuvieran después de `st.tabs`, reindentarlas bajo
# `with tab_resumen:` las dejaría de ser de módulo y el resto del fichero
# (y `social_red.py`) no las vería.
tab_resumen, *tabs_red = st.tabs(["Resumen"] + list(config.REDES_SOCIAL))

with tab_resumen:
    ui.cabecera("Social orgánico",
                f"YouTube · Facebook · Instagram · LinkedIn — solo alcance no pagado · {etq}")

    # ⚠️ Aviso de mezcla. Si unas redes traen datos reales y otras siguen con
    # ejemplo, los gráficos y el ranking comparan cifras inventadas con cifras
    # ciertas, y la de ejemplo puede salir la primera. En una página cuyo objetivo
    # es decidir en qué red invertir, eso es peor que no enseñar nada: el badge del
    # sidebar lo dice, pero nadie mira el sidebar antes que el gráfico.
    _ejemplo = [r for r, o in datos.origenes.items() if o == "sample"]
    _reales = [r for r, o in datos.origenes.items() if o != "sample"]
    if _ejemplo and _reales:
        st.warning(
            f"**{', '.join(_ejemplo)}** {'sigue' if len(_ejemplo) == 1 else 'siguen'} "
            f"con **datos de ejemplo**, mientras que {', '.join(_reales)} "
            f"{'trae' if len(_reales) == 1 else 'traen'} datos reales. "
            "Las comparativas entre redes y el ranking de publicaciones mezclan "
            "unos con otros: no uses esta página para comparar "
            f"{'esa red' if len(_ejemplo) == 1 else 'esas redes'} con el resto "
            "hasta que tenga sus credenciales."
        )

    diario = datos.diario
    posts = datos.posts

    if diario.empty and posts.empty:
        st.warning("No hay datos de social para el periodo seleccionado.")
        st.stop()

    # --------------------------------------------------------------------------- #
    # Bloque 1 — KPIs comparables entre las 4 redes
    # --------------------------------------------------------------------------- #
    st.subheader("Resumen del periodo")

    vis, _ = social.total_comparable(diario, "visualizaciones")
    seg, _ = social.total_comparable(diario, "seguidores_nuevos")
    inter = social.interacciones(diario).sum(min_count=1)
    inter = None if pd.isna(inter) else float(inter)
    tasa = (inter / vis) if (vis and inter is not None) else None

    c1, c2, c3, c4 = st.columns(4)
    ui.kpi(c1, "Visualizaciones", num_o_guion(vis),
           "Métrica comparable entre redes")
    ui.kpi(c2, "Nuevos seguidores", num_o_guion(seg), "Suma de las 4 redes")
    ui.kpi(c3, "Interacciones", num_o_guion(inter), "Likes + comentarios + compartidos")
    ui.kpi(c4, "Tasa de engagement", pct_o_guion(tasa, 2),
           "Interacciones / visualizaciones",
           estado="ok" if (tasa or 0) >= 0.03 else "warn")

    st.caption(
        "Se usa **visualizaciones** y no impresiones porque Instagram dejó de "
        "publicar impresiones el 21-abr-2025: es la única base que dan las 4 redes."
    )

    st.divider()

    # --------------------------------------------------------------------------- #
    # Bloque 2 — Detalle por red
    # --------------------------------------------------------------------------- #
    st.subheader("Por red")

    por_red = social.totales_por_red(diario)
    if por_red.empty:
        st.info("Sin métricas de cuenta en el periodo.")
    else:
        columnas = [
            {"key": "red", "label": "Red"},
            {"key": "seguidores_total", "label": "Seguidores", "tipo": "numero"},
            {"key": "seguidores_nuevos", "label": "Nuevos", "tipo": "numero"},
            {"key": "visualizaciones", "label": "Visualiz.", "tipo": "numero"},
            {"key": "impresiones", "label": "Impresiones", "tipo": "numero"},
            {"key": "alcance", "label": "Alcance", "tipo": "numero"},
            {"key": "likes", "label": "Likes", "tipo": "numero"},
            {"key": "comentarios", "label": "Coment.", "tipo": "numero"},
            {"key": "compartidos", "label": "Compart.", "tipo": "numero"},
            {"key": "mensajes", "label": "Mensajes", "tipo": "numero"},
        ]
        ui.tabla_ordenable(por_red, columnas)
        st.caption(
            "Pulsa un encabezado para ordenar. Una celda **vacía** significa que "
            "**esa red no publica ese dato por API**, no que "
            f"valga cero. {_frase_soporte('Impresiones', 'impresiones')} "
            f"{_frase_soporte('Mensajes', 'mensajes')} Además, ninguna red atribuye "
            "los mensajes a una publicación concreta."
        )

    st.divider()

    # --------------------------------------------------------------------------- #
    # Bloque 3 — Evolución diaria
    # --------------------------------------------------------------------------- #
    col_izq, col_der = st.columns([0.55, 0.45])

    with col_izq:
        st.subheader("Evolución diaria")
        etiquetas = {v: k for k, v in config.METRICAS_SOCIAL.items()}
        elegida = st.selectbox("Métrica", list(config.METRICAS_SOCIAL.values()),
                               index=list(config.METRICAS_SOCIAL).index(
                                   config.METRICA_COMPARABLE))
        metrica = etiquetas[elegida]
        serie = social.serie_diaria(diario, metrica)
        if serie.empty:
            st.info(f"Ninguna red publica «{elegida}» en el periodo.")
        else:
            ui.linea_temporal(serie, x="fecha", y="valor", color="red",
                              titulo=f"{elegida} por día", y_label=elegida,
                              simbolos=config.SIMBOLO_RED_SOCIAL)
            fuera = config.redes_sin_metrica(metrica)
            if fuera:
                st.caption(
                    f"No se dibujan {', '.join(fuera)}: no publican esta métrica. "
                    "Se omiten en vez de pintarlas a cero, que haría parecer que no "
                    "rinden cuando lo que ocurre es que no informan."
                )

    with col_der:
        st.subheader("Seguidores ganados")
        crec = social.crecimiento_seguidores(diario)
        if crec.empty:
            st.info("Sin datos de seguidores en el periodo.")
        else:
            ui.linea_temporal(crec, x="fecha", y="acumulado", color="red",
                              titulo="Acumulado en el periodo", y_label="Seguidores",
                              simbolos=config.SIMBOLO_RED_SOCIAL)
            st.caption(
                "Acumulado de nuevos seguidores, no el total absoluto: los totales "
                "de cada red son de órdenes distintos y en un mismo gráfico aplastan "
                "a las redes pequeñas."
            )

    st.divider()

    # --------------------------------------------------------------------------- #
    # Bloque 4 — Publicaciones
    # --------------------------------------------------------------------------- #
    st.subheader("Publicaciones")

    if posts.empty:
        st.info("Sin publicaciones en el periodo.")
    else:
        p = posts.copy()
        p["interacciones"] = social.interacciones(p)
        p["engagement"] = social.tasa_engagement(p)

        f1, f2, f3 = st.columns([0.34, 0.34, 0.32])
        redes_disp = [r for r in config.REDES_SOCIAL if r in set(p["red"])]
        sel_redes = f1.multiselect("Redes", redes_disp, default=redes_disp)
        orden_opciones = {
            "Visualizaciones": "visualizaciones",
            "Interacciones": "interacciones",
            "Tasa de engagement": "engagement",
            "Más reciente": "fecha",
        }
        sel_orden = f2.selectbox("Ordenar por", list(orden_opciones))
        top_n = f3.selectbox("Mostrar", [10, 25, 50, "Todas"], index=1)

        vista = p[p["red"].isin(sel_redes)] if sel_redes else p.iloc[0:0]
        vista = vista.sort_values(orden_opciones[sel_orden], ascending=False,
                                  na_position="last")
        total_filtradas = len(vista)
        if top_n != "Todas":
            vista = vista.head(int(top_n))

        # Sin `html.escape` y con la fecha como datetime: el destino es
        # `st.dataframe`, que no interpreta HTML (así que escapar solo enseñaría
        # las entidades) y ordena las fechas cronológicamente si son fechas de
        # verdad, no cadenas dd/mm/aaaa.
        vista = vista.assign(
            fecha=pd.to_datetime(vista["fecha"], errors="coerce"))

        ui.tabla_ordenable(vista, [
            {"key": "red", "label": "Red", "ancho": "small"},
            {"key": "fecha", "label": "Fecha", "tipo": "fecha", "ancho": "small"},
            {"key": "tipo", "label": "Formato", "ancho": "small"},
            {"key": "titulo", "label": "Publicación", "ancho": "large"},
            {"key": "url", "label": "Ver", "tipo": "enlace",
             "texto_enlace": "Abrir", "ancho": "small"},
            {"key": "visualizaciones", "label": "Visualiz.", "tipo": "numero"},
            {"key": "visualizaciones_totales", "label": "Visualiz. totales",
             "tipo": "numero",
             "ayuda": "Contador público acumulado desde que se publicó. Solo "
                      "YouTube lo da aparte; en el resto, las métricas por "
                      "publicación ya son acumuladas."},
            {"key": "impresiones", "label": "Impresiones", "tipo": "numero"},
            {"key": "likes", "label": "Likes", "tipo": "numero"},
            {"key": "comentarios", "label": "Coment.", "tipo": "numero"},
            {"key": "compartidos", "label": "Compart.", "tipo": "numero"},
            {"key": "clics", "label": "Clics", "tipo": "numero"},
            {"key": "guardados", "label": "Guardados", "tipo": "numero"},
            {"key": "engagement", "label": "Engagement", "tipo": "porcentaje"},
        ])

        if top_n != "Todas" and total_filtradas > len(vista):
            st.caption(f"Mostrando {len(vista)} de {num(total_filtradas)} "
                       "publicaciones del filtro. Cambia «Mostrar» para ver más.")

        st.caption(
            f"{_frase_soporte('Guardados', 'guardados', 'post')} "
            f"{_frase_soporte('Impresiones', 'impresiones', 'post')} "
            "El engagement se calcula sobre visualizaciones."
        )

        # Ranking visual por red: qué red concentra el alcance del periodo.
        st.write("")
        r1, r2 = st.columns(2)
        top_vis = (p.groupby("red", as_index=False)["visualizaciones"]
                   .sum(min_count=1).dropna()
                   .sort_values("visualizaciones", ascending=False))
        ui.tarjeta_ranking(r1, "Visualizaciones por red", top_vis, "red",
                           "visualizaciones",
                           nota="Suma de las publicaciones del periodo")
        top_int = (p.groupby("red", as_index=False)["interacciones"]
                   .sum(min_count=1).dropna()
                   .sort_values("interacciones", ascending=False))
        ui.tarjeta_ranking(r2, "Interacciones por red", top_int, "red",
                           "interacciones",
                           nota="Likes + comentarios + compartidos")

    # --------------------------------------------------------------------------- #
    # Nota metodológica
    # --------------------------------------------------------------------------- #
    st.divider()
    with st.expander("Nota metodológica — qué mide cada red y qué no es comparable"):
        st.markdown(
            """
    **Los «—» son deliberados.** Cada red publica un conjunto distinto de métricas.
    Un guion significa *esta red no da este dato por API*; un 0 significaría *la red
    lo da y vale cero*. Confundirlos haría que un total agregado saliera bajo y que
    las comparativas entre redes mintieran, justo la decisión que este panel apoya.

    | Métrica | Quién NO la da | Por qué |
    |---|---|---|
    | **Impresiones** | Instagram, YouTube | Meta la retiró el 21-abr-2025 (Graph v22.0) y la sustituyó por *views*. En YouTube Analytics API no está confirmada para reportes de canal. |
    | **Alcance** | YouTube | No existe el concepto de alcance único de canal. |
    | **Mensajes** | YouTube, Instagram, LinkedIn | Solo Facebook expone conversaciones nuevas, y requiere el permiso `pages_messaging`. **Ninguna red atribuye mensajes a una publicación.** |
    | **Guardados** | Todas menos Instagram | Solo Instagram publica `saved`. |

    **Histórico.** Las APIs no van igual de atrás: YouTube da todo, Facebook ~2 años,
    LinkedIn 12 meses e Instagram es el caso extremo (seguidores solo 30 días, y
    *views* con histórico limitado). Lo anterior solo se puede cubrir con los exports
    CSV de cada plataforma, que este panel lee como fuente de primera clase.

    **Likes y comentarios de Facebook e Instagram** se agregan por día de
    **publicación**, igual que hace Business Suite. No equivale a «interacciones
    recibidas ese día» en publicaciones antiguas.

    **Todo lo de esta página es orgánico.** Las métricas de pago están en las páginas
    de Google Ads y Meta Ads.
            """
        )

# --------------------------------------------------------------------------- #
# Una pestaña por red
#
# `datos_ant` (el periodo anterior, para los KPIs con variación) ya se resolvió
# arriba, junto al selector de periodo — ver el comentario de allí sobre por
# qué el orden importa para la caché en disco. `cargar_social` está cacheada
# por (desde, hasta) con `st.cache_data`, así que esa caché EN MEMORIA sí se
# reutiliza entre pestañas dentro del mismo rerun; lo que no se reutiliza es la
# llamada a las APIs cuando el usuario cambia de periodo: cada rango nuevo
# cuesta 16 resoluciones de conector (8 del periodo actual + 8 del anterior),
# no 8.
# --------------------------------------------------------------------------- #
for tab, red in zip(tabs_red, config.REDES_SOCIAL):
    with tab:
        if datos.origenes.get(red) == "sample":
            st.warning(
                f"**{red} está con datos de ejemplo.** Todo lo que veas en esta "
                "pestaña es inventado: sirve para comprobar la estructura, no "
                "para tomar decisiones."
            )
        kpis = social_analisis.comparar_kpis(
            datos.diario, datos_ant.diario, red,
            posts=datos.posts, posts_anterior=datos_ant.posts)
        social_red.pestana(red, datos.diario, datos.posts,
                           datos.demografia, kpis, hasta)

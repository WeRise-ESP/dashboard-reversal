from datetime import date

import pandas as pd

from src import config
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


def test_una_red_sin_serie_diaria_saca_los_kpis_de_sus_publicaciones():
    """TikTok no tiene serie diaria de flujo, así que la tabla de Rendimiento
    salía entera vacía al lado de una lista de vídeos con sus números a la
    vista. El total sale de sumar publicaciones."""
    from datetime import date

    import pandas as pd

    from src import config
    from src.data import social_analisis as sa

    assert "TikTok" in config.REDES_SIN_SERIE_DIARIA

    diario = pd.DataFrame([{"fecha": date(2026, 7, 31), "red": "TikTok",
                            "seguidores_total": 13}])
    posts = pd.DataFrame([
        {"red": "TikTok", "post_id": "a", "visualizaciones": 249, "likes": 1,
         "comentarios": 0, "compartidos": 0},
        {"red": "TikTok", "post_id": "b", "visualizaciones": 1039, "likes": 20,
         "comentarios": 0, "compartidos": 8},
    ])

    k = sa.comparar_kpis(diario, diario.iloc[:0], "TikTok",
                         posts=posts, posts_anterior=posts.iloc[:0])
    fila = k[k["metrica"] == "visualizaciones"].iloc[0]
    assert fila["actual"] == 1288, "debería sumar las visualizaciones de los 2"
    assert k[k["metrica"] == "compartidos"].iloc[0]["actual"] == 8


def test_las_redes_con_serie_diaria_no_cambian():
    """El total de las demás sigue saliendo del diario aunque se le pasen
    publicaciones: mezclarlo cambiaría el significado de la métrica."""
    from datetime import date

    import pandas as pd

    from src.data import social_analisis as sa

    diario = pd.DataFrame([{"fecha": date(2026, 7, 30), "red": "YouTube",
                            "visualizaciones": 100}])
    posts = pd.DataFrame([{"red": "YouTube", "post_id": "x",
                           "visualizaciones": 99999}])

    k = sa.comparar_kpis(diario, diario.iloc[:0], "YouTube",
                         posts=posts, posts_anterior=posts.iloc[:0])
    assert k[k["metrica"] == "visualizaciones"].iloc[0]["actual"] == 100

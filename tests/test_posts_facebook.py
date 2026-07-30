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


def test_publicacion_estatica_no_deja_visualizaciones_a_cero(monkeypatch):
    """Regresión: una publicación ESTÁTICA no es vídeo ni reel. Verificado
    contra la Página real el 30-jul-2026: `post_video_views` responde 0 para
    ella en vez de fallar la llamada. Ese 0 significa «esta métrica no aplica
    aquí», no «cero reproducciones» — la especificación dice literal que «su
    casilla va a nulo, no a cero». Escribirlo falsearía la tabla de
    publicaciones, la media por formato y metería a Facebook en el ranking de
    visualizaciones de la pestaña Resumen con un 0 en vez de dejarlo fuera."""
    monkeypatch.setattr(m, "_get", lambda v, ruta, tok, params: _bloques(
        ("post_video_views", 0)))
    out = m._insights_post_fb("v21.0", "p1", "tok")
    assert "visualizaciones" not in out


def test_cero_clics_si_se_conserva(monkeypatch):
    """A diferencia de las visualizaciones, 0 clics es un dato real: nadie ha
    hecho clic. Debe conservarse, no descartarse como si fuera "sin dato"."""
    monkeypatch.setattr(m, "_get", lambda v, ruta, tok, params: _bloques(
        ("post_clicks", 0)))
    out = m._insights_post_fb("v21.0", "p1", "tok")
    assert out["clics"] == 0


def test_until_se_pide_con_un_dia_de_mas(monkeypatch):
    """`until` de Graph API es EXCLUSIVO: apunta al comienzo de ese día.

    Pasar `until=hasta` descarta todo lo publicado el último día del rango —que
    casi siempre es hoy—, y el fallo se cura solo al día siguiente, así que
    parece un retraso de Meta en vez de un error nuestro. Verificado contra la
    Página real el 30-jul-2026.
    """
    from datetime import date

    pedidos = {}

    def _get(version, ruta, token, params=None):
        if ruta.endswith("/published_posts"):
            pedidos.update(params or {})
            return {"data": []}
        return {"data": []}

    monkeypatch.setattr(m, "_token_pagina", lambda creds: ("PAGE1", "tok"))
    monkeypatch.setattr(m, "_get", _get)

    m._api_fb_posts({}, date(2026, 7, 1), date(2026, 7, 30))

    assert pedidos["since"] == "2026-07-01"
    assert pedidos["until"] == "2026-07-31", (
        "until debe ir un día por delante de `hasta`, o se pierde el último día"
    )


def test_los_reels_se_distinguen_de_los_videos_normales():
    """Graph devuelve `media_type=video` tanto para un reel como para una subida
    normal; lo que los separa es el permalink. Sin esa distinción, el bloque de
    rendimiento por formato es inútil justo en la red donde hoy se publica casi
    solo en reel."""
    reel = {"permalink_url": "https://www.facebook.com/reel/1361733375923350/",
            "attachments": {"data": [{"media_type": "video"}]}}
    video = {"permalink_url": "https://www.facebook.com/1234/posts/5678",
             "attachments": {"data": [{"media_type": "video"}]}}
    assert m._tipo_post_fb(reel) == "Reel"
    assert m._tipo_post_fb(video) == "Vídeo"


def test_el_formato_sale_del_media_type():
    def _p(media):
        return {"permalink_url": "https://www.facebook.com/1/posts/2",
                "attachments": {"data": [{"media_type": media}]}}
    assert m._tipo_post_fb(_p("photo")) == "Imagen"
    assert m._tipo_post_fb(_p("album")) == "Carrusel"
    assert m._tipo_post_fb(_p("link")) == "Enlace"


def test_sin_adjuntos_no_revienta():
    assert m._tipo_post_fb({}) == "Publicación"
    assert m._tipo_post_fb({"attachments": {"data": []}}) == "Publicación"

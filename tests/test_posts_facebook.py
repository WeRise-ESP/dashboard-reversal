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

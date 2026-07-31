"""Conector de TikTok.

Verificado el 31-jul-2026 contra la cuenta real (@reversal.institute, vía el
sandbox de la app). Estos tests fijan la TRADUCCIÓN de la respuesta al esquema
y, sobre todo, los dos detalles que la documentación no decía: que `user/info/`
es GET mientras `video/list/` es POST, y que no hay altas de seguidores por día.
"""
from datetime import date, timedelta

import pandas as pd

from src.connectors import tiktok as tt


def _video(vid, dias_atras, **extra):
    ts = int(pd.Timestamp(date.today() - timedelta(days=dias_atras)).timestamp())
    return {"id": vid, "create_time": ts, "title": f"t{vid}",
            "share_url": f"https://tiktok.com/@x/video/{vid}", **extra}


def test_el_diario_devuelve_una_sola_foto_no_una_serie(monkeypatch):
    """La Display API no publica series diarias: devuelve el estado ACTUAL.
    Por eso el diario es UNA fila, y la serie se construye acumulando fotos en
    el histórico con el job. Si esto devolviera varias filas, alguien habría
    inventado datos que la API no da."""
    monkeypatch.setattr(tt, "_token", lambda c: "tok")
    monkeypatch.setattr(tt, "_peticion",
                        lambda metodo, ruta, token, campos, cuerpo=None:
                        {"user": {"follower_count": 412, "likes_count": 9000}})

    df = tt._api_diario({}, date(2026, 7, 1), date(2026, 7, 31))
    assert len(df) == 1
    assert df.iloc[0]["seguidores_total"] == 412
    assert df.iloc[0]["fecha"] == date(2026, 7, 31)


def test_el_diario_no_mete_totales_de_cuenta_en_columnas_de_flujo(monkeypatch):
    """`likes_count` es el total histórico de la cuenta, no los likes del día.
    Ponerlo en la columna `likes` dispararía cualquier suma del periodo."""
    monkeypatch.setattr(tt, "_token", lambda c: "tok")
    monkeypatch.setattr(tt, "_peticion",
                        lambda metodo, ruta, token, campos, cuerpo=None:
                        {"user": {"follower_count": 412, "likes_count": 9000}})

    df = tt._api_diario({}, date(2026, 7, 1), date(2026, 7, 31))
    assert "likes" not in df.columns or pd.isna(df.iloc[0].get("likes"))


def test_los_videos_se_filtran_por_fecha_y_se_corta_al_salir_del_rango(monkeypatch):
    """Vienen del más nuevo al más viejo, así que en cuanto aparece uno anterior
    a `desde` se deja de paginar en vez de recorrer el canal entero."""
    paginas = [
        {"videos": [_video("a", 1, view_count=100), _video("b", 5, view_count=50)],
         "cursor": 1, "has_more": True},
        {"videos": [_video("c", 400, view_count=10)], "cursor": 2, "has_more": True},
        {"videos": [_video("d", 500)], "cursor": 3, "has_more": True},
    ]
    pedidas = []

    def _peticion(metodo, ruta, token, campos, cuerpo=None):
        pedidas.append(cuerpo)
        return paginas[len(pedidas) - 1]

    monkeypatch.setattr(tt, "_token", lambda c: "tok")
    monkeypatch.setattr(tt, "_peticion", _peticion)

    hasta = date.today()
    df = tt._api_posts({}, hasta - timedelta(days=30), hasta)
    assert list(df["post_id"]) == ["a", "b"]
    assert len(pedidas) == 2, "debería cortar al ver el vídeo antiguo, no seguir"


def test_un_error_dentro_del_cuerpo_se_detecta(monkeypatch):
    """TikTok devuelve HTTP 200 con el error DENTRO del JSON, así que
    `raise_for_status` no basta."""
    class _R:
        status_code = 200
        content = b"x"
        headers = {"content-type": "application/json"}

        def json(self):
            return {"error": {"code": "access_token_invalid",
                              "message": "token caducado"}}

        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.request", lambda *a, **k: _R())
    try:
        tt._peticion("GET", "user/info/", "tok", "campos")
    except RuntimeError as e:
        assert "access_token_invalid" in str(e)
    else:
        raise AssertionError("un error con HTTP 200 debe lanzar excepción")


def test_user_info_va_por_get_y_video_list_por_post(monkeypatch):
    """El método NO es uniforme en la Display API, y equivocarlo devuelve un
    404 en texto plano que parece un problema de scopes. Comprobado contra la
    API real el 31-jul-2026."""
    metodos = {}

    class _R:
        status_code = 200
        content = b"{}"
        headers = {"content-type": "application/json"}

        def json(self):
            return {"data": {"user": {"follower_count": 13}},
                    "error": {"code": "ok"}}

        def raise_for_status(self):
            pass

    def _request(metodo, url, **k):
        metodos[url.rsplit("/v2/", 1)[-1]] = metodo
        return _R()

    monkeypatch.setattr("requests.request", _request)
    monkeypatch.setattr(tt, "_token", lambda c: "tok")

    tt._api_diario({}, date.today(), date.today())
    assert metodos["user/info/"] == "GET"


def test_una_respuesta_que_no_es_json_da_un_error_legible(monkeypatch):
    """El 404 de un método equivocado llega en text/plain; sin este control
    revienta con «Expecting value: line 1 column 1», que no dice nada."""
    class _R:
        status_code = 404
        content = b"Unsupported path(Janus)"
        text = "Unsupported path(Janus)"
        headers = {"content-type": "text/plain; charset=utf-8"}

        def json(self):
            raise ValueError("Expecting value: line 1 column 1 (char 0)")

        def raise_for_status(self):
            pass

    monkeypatch.setattr("requests.request", lambda *a, **k: _R())
    try:
        tt._peticion("POST", "user/info/", "tok", "campos")
    except RuntimeError as e:
        assert "Unsupported path" in str(e) and "404" in str(e)
    else:
        raise AssertionError("una respuesta no-JSON debe dar un error legible")


def test_tiktok_da_metricas_de_video_pero_no_altas_de_seguidores():
    """Sondeado el 31-jul-2026 contra @reversal.institute: las cuatro métricas
    de vídeo responden en 10 de 10, pero la Display API solo publica el
    `follower_count` ACTUAL. `seguidores_nuevos` no existe, y restar dos fotos
    consecutivas del histórico daría un número que la API nunca ha dicho."""
    from src import config

    # Los DOS ámbitos: el mapa de post es una tabla aparte, y tenerlo solo en
    # el de diario dejaba las publicaciones a nulo aunque la API sí respondiera.
    for m in ("visualizaciones", "likes", "comentarios", "compartidos"):
        for ambito in ("diario", "post"):
            assert config.soporta_metrica(m, "TikTok", ambito), (
                f"{m} de TikTok ({ambito}) responde en la API real y debería "
                "estar soportada"
            )
    assert not config.soporta_metrica("seguidores_nuevos", "TikTok"), (
        "la Display API no da altas de seguidores por día, solo el total actual"
    )

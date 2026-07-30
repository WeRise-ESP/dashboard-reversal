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

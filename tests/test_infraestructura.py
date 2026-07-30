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

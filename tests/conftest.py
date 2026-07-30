"""Configuración común de los tests.

Pone la raíz del repo en sys.path para que los tests puedan importar `src.*`
sin instalar el proyecto como paquete.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

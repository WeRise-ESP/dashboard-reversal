"""
Job DIARIO que acumula el histórico de social orgánico.

    python scripts/snapshot_social.py            # últimos 30 días de cada red
    python scripts/snapshot_social.py --dias 400 # relleno inicial hacia atrás
    python scripts/snapshot_social.py --dry-run  # enseña qué haría, no escribe

Escribe `data/historico_social/social_<red>_diario.csv`, que `social_base.
resolver` funde por DEBAJO de lo que devuelva la API. Cada ejecución fusiona
sobre lo que ya había: nunca borra un día capturado.

## Por qué existe

Las APIs solo responden de su ventana, y la de Instagram son **30 días** de
seguidores. Lo que caiga fuera y no esté guardado aquí no se recupera: no es que
sea trabajoso, es que Meta ya no lo tiene. Cada día sin ejecutar este job es un
día de Instagram perdido de forma definitiva. Facebook aguanta ~2 años y
LinkedIn 12 meses; YouTube da todo el histórico y es el único que no corre prisa.

## ⚠️ NO usa la cascada de los conectores, y es a propósito

Llama a las funciones `_api_*` directamente en vez de a `obtener()`. `obtener()`
pasa por `resolver`, que ante un fallo cae a datos de EJEMPLO — y unos datos
inventados escritos aquí se volverían «histórico real» para siempre, mezclados
con los de verdad y sin forma de distinguirlos. Si una red no tiene credenciales
o su API falla, este job la salta y lo dice; no escribe nada.

## Regla de los nulos

Se aplica `social.normalizar_diario` a lo que devuelve la API, así que una
métrica que la red no publica sale como celda VACÍA en el CSV, nunca como 0.
La fusión respeta lo mismo: un nulo nuevo jamás pisa un valor ya guardado.

## Puesta en marcha (cron diario a las 04:00)

    0 4 * * * cd /ruta/a/Dashboard && .venv/bin/python scripts/snapshot_social.py

Necesita `.streamlit/secrets.toml` con las secciones `[youtube]`,
`[social_meta]` y/o `[linkedin]`. Las redes sin credencial se saltan, así que se
puede arrancar el cron con una sola red configurada y añadir las demás después.

⚠️ Streamlit Cloud NO ejecuta este job: allí no hay cron. El histórico llega a
la app desplegada porque el CSV se commitea y se hace push (`data/
historico_social/` sí va a git, a diferencia de `data/cache/`).
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from src import config  # noqa: E402
from src.connectors import linkedin, meta_organico, youtube  # noqa: E402
from src.connectors.base import (  # noqa: E402
    HISTORICO_DIR,
    _leer_secreto,
    escribir_historico,
    leer_historico,
)
from src.connectors.social_base import fusionar  # noqa: E402
from src.data import social  # noqa: E402

CLAVES = ("fecha", "red")

# Ventana por defecto. 30 días es el máximo que da Instagram y sobra de margen
# para que los datos que llegan tarde (Meta corrige hasta ~48 h) se recapturen.
DIAS_POR_DEFECTO = 30


@dataclass(frozen=True)
class Fuente:
    red: str
    seccion: str    # sección de secrets.toml
    clave: str      # nombre del fichero de histórico
    fn_api: Callable[[dict, date, date], pd.DataFrame]
    limite: str     # hasta dónde llega su API hacia atrás (para el mensaje)


# Se apunta a las funciones privadas `_api_*` a conciencia: ver el aviso de la
# cabecera. Si alguna se renombra, este script falla de forma ruidosa al
# importar, que es justo lo que se quiere.
FUENTES = (
    Fuente("YouTube", "youtube", "social_youtube_diario",
           youtube._api_diario, "histórico completo"),
    Fuente("Facebook", "social_meta", "social_facebook_diario",
           meta_organico._api_fb_diario, "~2 años"),
    Fuente("Instagram", "social_meta", "social_instagram_diario",
           meta_organico._api_ig_diario, "seguidores: 30 días"),
    Fuente("LinkedIn", "linkedin", "social_linkedin_diario",
           linkedin._api_diario, "12 meses"),
)

# Todas las métricas de social son recuentos. Se guardan como enteros nullable
# para que el CSV lleve "128" y no "128.0", y el nulo siga siendo celda vacía.
_COLUMNAS_ENTERAS = tuple(config.METRICAS_SOCIAL) + ("seguidores_total",)


def _a_enteros(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    for col in _COLUMNAS_ENTERAS:
        if col in d.columns:
            d[col] = pd.to_numeric(d[col], errors="coerce").round().astype("Int64")
    return d


def capturar(fuente: Fuente, desde: date, hasta: date) -> tuple[pd.DataFrame | None, str]:
    """Pide a la API de `fuente` su tabla diaria, ya normalizada.

    Devuelve (df, motivo). Con df a None, `motivo` explica por qué se salta esta
    red — nunca se inventa un sustituto.
    """
    creds = _leer_secreto(fuente.seccion)
    if not creds:
        return None, f"sin credenciales (falta [{fuente.seccion}] en secrets.toml)"

    try:
        bruto = fuente.fn_api(creds, desde, hasta)
    except Exception as e:  # noqa: BLE001
        return None, f"la API falló: {e}"

    if bruto is None or bruto.empty:
        return None, "la API no devolvió filas para el periodo"

    return social.normalizar_diario(bruto), "ok"


def acumular(clave: str, nuevo: pd.DataFrame,
             dry_run: bool) -> tuple[pd.DataFrame, int, int]:
    """Funde `nuevo` sobre el histórico guardado y lo reescribe.

    Devuelve (fusion, filas_nuevas, filas_actualizadas).
    """
    previo_bruto = leer_historico(clave)
    previo = (social.normalizar_diario(previo_bruto)
              if previo_bruto is not None and not previo_bruto.empty else None)

    fusion = fusionar(previo, nuevo, CLAVES)
    fusion = (fusion.sort_values(list(CLAVES), na_position="last")
                    .reset_index(drop=True))

    antes = 0 if previo is None else len(previo)
    nuevas = len(fusion) - antes
    actualizadas = len(nuevo) - nuevas

    if not dry_run:
        escribir_historico(_a_enteros(fusion), clave)
    return fusion, nuevas, max(actualizadas, 0)


def _rango(args) -> tuple[date, date]:
    hasta = date.fromisoformat(args.hasta) if args.hasta else date.today()
    desde = (date.fromisoformat(args.desde) if args.desde
             else hasta - timedelta(days=args.dias))
    if desde > hasta:
        raise SystemExit(f"Rango inválido: {desde} es posterior a {hasta}.")
    return desde, hasta


def main() -> int:
    p = argparse.ArgumentParser(
        description="Acumula el histórico diario de social orgánico.")
    p.add_argument("--dias", type=int, default=DIAS_POR_DEFECTO,
                   help=f"días hacia atrás desde hoy (por defecto {DIAS_POR_DEFECTO}). "
                        "Para el relleno inicial, tira todo lo atrás que aguante "
                        "cada API; las que no lleguen simplemente devolverán menos.")
    p.add_argument("--desde", help="fecha inicial YYYY-MM-DD (ignora --dias)")
    p.add_argument("--hasta", help="fecha final YYYY-MM-DD (por defecto, hoy)")
    p.add_argument("--red", action="append", choices=[f.red for f in FUENTES],
                   help="limita a una red (repetible)")
    p.add_argument("--dry-run", action="store_true",
                   help="no escribe nada; solo informa de lo que haría")
    args = p.parse_args()

    desde, hasta = _rango(args)
    fuentes = [f for f in FUENTES if not args.red or f.red in args.red]

    print(f"Snapshot social {desde} → {hasta}"
          f"{'  [DRY RUN, no se escribe]' if args.dry_run else ''}")
    print(f"Destino: {HISTORICO_DIR}\n")

    capturadas = saltadas = 0
    for f in fuentes:
        df, motivo = capturar(f, desde, hasta)
        if df is None:
            print(f"  ⏭  {f.red:<10} saltada — {motivo}")
            saltadas += 1
            continue

        fusion, nuevas, actualizadas = acumular(f.clave, df, args.dry_run)
        fechas = pd.to_datetime(fusion["fecha"], errors="coerce").dropna()
        cobertura = (f"{fechas.min().date()} → {fechas.max().date()}"
                     if len(fechas) else "sin fechas")
        print(f"  ✓  {f.red:<10} +{nuevas} días nuevos, {actualizadas} actualizados "
              f"→ {len(fusion)} en total ({cobertura})")
        capturadas += 1

    print(f"\n{capturadas} red(es) capturadas, {saltadas} saltadas.")
    if saltadas:
        print("Las redes saltadas NO se han tocado: su histórico sigue intacto.")
        for f in fuentes:
            if not _leer_secreto(f.seccion):
                print(f"  · {f.red}: la API da {f.limite}. "
                      "Cuanto más tarde se conecte, más histórico se pierde.")
    # Sin ninguna red capturada el job no ha hecho su trabajo: hay que enterarse
    # desde el cron, así que sale con código de error.
    return 0 if capturadas else 1


if __name__ == "__main__":
    raise SystemExit(main())

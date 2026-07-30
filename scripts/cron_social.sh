#!/bin/bash
#
# Job diario de social orgánico, pensado para cron.
#
#   crontab -e   ->   0 4 * * * /Users/misael/Documents/Reversal/Dashboard/scripts/cron_social.sh
#
# Hace tres cosas, en este orden:
#   1. Captura las métricas del día y la demografía (snapshot_social.py).
#   2. Si el histórico ha cambiado, lo commitea.
#   3. Lo sube, para que el dashboard desplegado lo vea.
#
# El paso 3 es el que cierra el circuito: sin él, el histórico crece en este
# Mac y producción se queda congelada. Se puede desactivar poniendo PUSH=0.
#
# Solo toca `data/historico_social/`. Nunca commitea código, ni la caché, ni
# nada más: si hay cambios sin guardar en el repo, este job los ignora.
#
# Por qué existe: la API de Instagram solo devuelve 30 días de seguidores. Lo
# que no se capture dentro de esa ventana no se recupera nunca, ni con exports.
# Cada día que este job no corre es un día perdido de forma definitiva.

set -uo pipefail

PUSH=${PUSH:-1}
REPO="/Users/misael/Documents/Reversal/Dashboard"
PY="$REPO/.venv/bin/python"
LOG="$REPO/data/cron_social.log"

# cron arranca con un PATH mínimo y sin las variables del shell interactivo.
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

cd "$REPO" || exit 1
exec >> "$LOG" 2>&1
echo "───────────────────────────────────────────── $(date '+%Y-%m-%d %H:%M:%S')"

if [ ! -x "$PY" ]; then
    echo "✗ No existe el intérprete $PY — ¿se ha movido o borrado el .venv?"
    exit 1
fi

# --- 1. Capturar ---------------------------------------------------------- #
# `snapshot_social.py` sale con 1 si NINGUNA red se pudo capturar. Eso sí es un
# fallo que hay que ver; que falte una red concreta (LinkedIn sin credenciales)
# es normal y sale con 0.
"$PY" scripts/snapshot_social.py
CAPTURA=$?
if [ $CAPTURA -ne 0 ]; then
    echo "✗ La captura falló (código $CAPTURA). No se commitea nada."
    exit $CAPTURA
fi

# --- 2. Commitear, solo si hay algo nuevo ---------------------------------- #
if git diff --quiet -- data/historico_social/; then
    echo "· Sin cambios en el histórico: nada que commitear."
    exit 0
fi

git add data/historico_social/
git commit -q -m "datos: histórico de social orgánico $(date '+%Y-%m-%d')

Captura automática de scripts/cron_social.sh." || {
    echo "✗ Falló el commit."
    exit 1
}
echo "✓ Commiteado $(git log --oneline -1)"

# --- 3. Subir -------------------------------------------------------------- #
if [ "$PUSH" != "1" ]; then
    echo "· PUSH=0: commiteado en local, sin subir."
    exit 0
fi

if git push origin main; then
    echo "✓ Subido. Streamlit Cloud redesplegará solo."
else
    echo "✗ Falló el push. El commit está en local; súbelo a mano."
    echo "  Si es por credenciales, ejecuta 'git push' una vez desde la terminal."
    exit 1
fi

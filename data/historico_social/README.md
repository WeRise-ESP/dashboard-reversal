# Histórico acumulado de social orgánico

Lo que va escribiendo `scripts/snapshot_social.py` cada día. **No se edita a
mano**: para meter datos a mano está `data/import_social/`.

```
social_youtube_diario.csv   social_facebook_diario.csv
social_instagram_diario.csv social_linkedin_diario.csv
```

Mismo esquema que los CSV de `import_social` (`fecha` · `red` · `impresiones` ·
`visualizaciones` · `alcance` · `seguidores_nuevos` · `seguidores_total` ·
`likes` · `comentarios` · `compartidos` · `mensajes`).

Estos ficheros **sí van a git**: son métricas agregadas sin datos personales, y
es la única vía por la que el histórico llega a la app desplegada (Streamlit
Cloud no ejecuta el job).

Y la demografía de audiencia, en formato largo:

```
social_youtube_demografia.csv    social_instagram_demografia.csv
social_linkedin_demografia.csv
```

Columnas: `fecha` · `red` · `dimension` · `categoria` · `valor` · `unidad`.

⚠️ **`unidad` no es decorativa.** Instagram cuenta personas que te siguen
(`seguidores`); YouTube da el % de visualizaciones (`pct_visualizaciones`).
Sumar o comparar filas de unidades distintas no significa nada.

Facebook no aparece: Meta retiró la demografía de Páginas.

## En qué se diferencia de `import_social/`

Los dos guardan histórico, pero entran de forma distinta:

| | `import_social/` | `historico_social/` (esto) |
|---|---|---|
| Quién lo llena | una persona, con exports de la plataforma | el job, con la API |
| Cómo entra | **nivel de la cascada**: solo se usa si no hay API ni caché | **suelo**: se funde SIEMPRE por debajo del nivel que gane |
| Badge | «CSV importado» | «Histórico propio» (solo si no hay nada mejor) |

Esa diferencia es el motivo de que exista este directorio en vez de reutilizar
el otro. El día que llegue el token de Meta, la API devolverá 30 días de
Instagram; si el histórico fuese un nivel de la cascada quedaría tapado justo
cuando empieza a valer. Como suelo, la API manda en las fechas que cubre y esto
rellena todo lo anterior. Lo implementa `social_base.resolver`.

## Reglas

- **Una celda vacía es un nulo**, no un cero. Ver la nota de `config.
  SOPORTE_METRICA_SOCIAL`.
- **El job nunca borra**: fusiona celda a celda y un valor nuevo nulo no pisa
  uno ya capturado (`social_base.fusionar`).
- **Nunca escribe datos de ejemplo**: llama a las APIs directamente, sin pasar
  por la cascada, precisamente para que un fallo no cuele datos inventados aquí.

## Uso

```bash
python scripts/snapshot_social.py --dry-run   # ver qué haría
python scripts/snapshot_social.py             # últimos 30 días
python scripts/snapshot_social.py --dias 730  # relleno inicial
```

Ponlo en cron **el día que llegue la primera credencial**, no después: la
ventana de seguidores de Instagram son 30 días y lo que caiga fuera no se
recupera.

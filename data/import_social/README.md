# Exports CSV de redes sociales

Aquí van los datos de social orgánico que **las APIs no pueden dar hacia atrás**.
Es el tercer nivel de la cascada de los conectores: *API → caché → **CSV** →
ejemplo*, así que un fichero aquí se muestra como dato real (badge «CSV
importado») aunque no haya credenciales configuradas.

Estos CSV **sí se suben a git** (a diferencia de `data/cache/`): son métricas
agregadas, sin datos personales, y es la única forma de que la app desplegada
muestre histórico real antes de tener las APIs conectadas.

## Por qué esto es urgente

Las APIs no llegan igual de atrás:

| Red | Histórico por API |
|---|---|
| YouTube | Completo |
| Facebook | ~2 años |
| LinkedIn | 12 meses |
| **Instagram** | **Seguidores: 30 días.** `views`: limitado |

Lo que quede fuera de esas ventanas y no esté aquí **se pierde de forma
definitiva**. En Instagram, cada día que pasa sin capturar es un día perdido.

## Nombres de fichero

Cada conector busca su fichero por nombre exacto:

```
social_youtube_diario.csv     social_youtube_posts.csv
social_facebook_diario.csv    social_facebook_posts.csv
social_instagram_diario.csv   social_instagram_posts.csv
social_linkedin_diario.csv    social_linkedin_posts.csv
```

## Columnas

**`*_diario.csv`** — una fila por día:

`fecha` (YYYY-MM-DD) · `red` · `impresiones` · `visualizaciones` · `alcance` ·
`seguidores_nuevos` · `seguidores_total` · `likes` · `comentarios` ·
`compartidos` · `mensajes`

**`*_posts.csv`** — una fila por publicación:

`red` · `post_id` · `fecha` · `tipo` · `titulo` · `url` · `miniatura` ·
`impresiones` · `visualizaciones` · `likes` · `comentarios` · `compartidos` ·
`guardados`

Faltar columnas no rompe nada: las que no estén se rellenan a nulo. El valor de
`red` debe ser exactamente `YouTube`, `Facebook`, `Instagram` o `LinkedIn`.

## Deja las casillas vacías, no las pongas a cero

Si una red no publica una métrica, **deja la celda vacía**. No escribas `0`: un
cero significa «la red lo mide y vale cero», y falsearía los totales y las
comparativas entre redes.

Da igual si te equivocas: `src/data/social.py` vuelve a poner a nulo cualquier
métrica que la red no publique según `config.SOPORTE_METRICA_SOCIAL`. Pero no
puede adivinar lo contrario, así que no rellenes huecos a mano.

## De dónde salen los exports

- **YouTube Studio** → Analytics → Avanzado → Exportar (por día y por vídeo)
- **Meta Business Suite** → [Insights](https://business.facebook.com/latest/insights/)
  → Exportar (Página **e** Instagram, por día y por publicación)
- **LinkedIn Analytics** → Actualizaciones / Seguidores / Visitantes → Exportar XLS

Los exports vienen con los nombres de columna de cada plataforma, no con los de
arriba: hay que renombrarlos al esquema de esta ficha.

"""
Genera el REFRESH TOKEN de TikTok para la cuenta de Reversal.

    python scripts/tiktok_refresh_token.py <CLIENT_KEY>

El Client Secret NO se pasa como argumento: se pide por teclado sin mostrarlo,
porque un secreto en la línea de comandos acaba en el historial del shell y en
cualquier captura de la terminal. Para automatizar, TIKTOK_CLIENT_SECRET.

Requisitos previos, en la app de developers.tiktok.com:

  1. Products: **Login Kit** y **Display API** concedidos.
  2. Scopes: `user.info.basic`, `user.info.profile`, `user.info.stats`,
     `video.list`.
  3. Login Kit → *Redirect URI* → añade EXACTAMENTE:
         http://localhost:8766/callback
     TikTok la compara carácter a carácter, igual que LinkedIn.

     ⚠️ Si TikTok RECHAZA una URI de localhost —lo hace en algunas
     configuraciones, a diferencia de LinkedIn y Google—, registra una URL
     https tuya que no haga nada (por ejemplo
     https://reversal.institute/tiktok-callback), pásala con --redirect, y
     cuando el navegador acabe ahí copia el `code=` de la barra de direcciones
     y pégalo con --code. El script acepta las dos vías.

Al ejecutarlo se imprime una URL: ábrela con la cuenta que administra el TikTok
de Reversal y acepta.

⚠️ El refresh token de TikTok dura **365 días** y el access token 24 h. El
conector canjea el refresh en cada carga, así que lo único que hay que renovar
—una vez al año— es lo que genera este script.
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets as _secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

AUTORIZAR = "https://www.tiktok.com/v2/auth/authorize/"
TOKEN = "https://open.tiktokapis.com/v2/oauth/token/"

SCOPES_POR_DEFECTO = "user.info.basic,user.info.profile,user.info.stats,video.list"

_RESPUESTA = b"""<!doctype html><meta charset="utf-8">
<body style="font-family:system-ui;padding:3rem;text-align:center">
<h2>Listo</h2><p>Ya puedes cerrar esta pestana y volver a la terminal.</p></body>"""


class _Recoge(BaseHTTPRequestHandler):
    """Servidor de un solo uso que captura el `code` del callback."""

    resultado: dict = {}

    def do_GET(self):  # noqa: N802
        query = urllib.parse.urlparse(self.path).query
        _Recoge.resultado = {k: v[0] for k, v in
                             urllib.parse.parse_qs(query).items()}
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(_RESPUESTA)

    def log_message(self, *_):
        pass


def _canjear(client_key: str, client_secret: str, code: str,
             redirect: str) -> int:
    r = requests.post(
        TOKEN,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": urllib.parse.unquote(code),
            "grant_type": "authorization_code",
            "redirect_uri": redirect,
        },
        timeout=60,
    )
    datos = r.json() if r.content else {}
    refresh = datos.get("refresh_token")
    if not refresh:
        print(f"\n✗ TikTok no devolvió refresh_token ({r.status_code}).")
        print(f"  Respuesta: {str(datos)[:400]}")
        print("  → Si dice que faltan scopes, revisa que Login Kit y Display "
              "API estén CONCEDIDOS (no solo solicitados) en la pestaña de "
              "productos de la app.")
        return 1

    print("\n" + "=" * 68)
    print("✅ Pega esto en .streamlit/secrets.toml:")
    print("=" * 68)
    print("[tiktok]")
    print(f'client_key    = "{client_key}"')
    # No lo imprimimos (acabaría en el historial de la terminal), pero el
    # marcador tiene que cantar: un "…" se pega tal cual sin darse cuenta.
    print('client_secret = "PEGA_AQUI_EL_CLIENT_SECRET"   # el que acabas '
          'de teclear; NO lo dejes así')
    print(f'refresh_token = "{refresh}"')
    print("=" * 68)
    dias = int(datos.get("refresh_expires_in", 0)) // 86400
    if dias:
        print(f"\n⚠️ El refresh token caduca en {dias} días. Ponte un aviso.")
    print("\nDespués: python scripts/verificar_social.py --red TikTok")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Refresh token de TikTok.")
    p.add_argument("client_key")
    p.add_argument("--redirect", default="http://localhost:8766/callback",
                   help="la redirect URI EXACTA registrada en Login Kit")
    p.add_argument("--scopes", default=SCOPES_POR_DEFECTO)
    p.add_argument("--code",
                   help="pega aquí el `code` de la barra de direcciones si tu "
                        "redirect URI no es de localhost y no se puede recoger "
                        "automáticamente")
    args = p.parse_args()

    # Solo se pide cuando de verdad hace falta: construir la URL de
    # autorización no usa el secreto, y hacerlo teclear de más invita a
    # dejarlo escrito en un sitio peor.
    def secreto() -> str:
        s = os.environ.get("TIKTOK_CLIENT_SECRET") or getpass.getpass(
            "Client Secret (no se muestra al teclear): ").strip()
        if not s:
            raise SystemExit("✗ Sin Client Secret no se puede canjear el código.")
        return s

    # Vía manual: el usuario ya tiene el código de una redirect externa.
    if args.code:
        return _canjear(args.client_key, secreto(), args.code, args.redirect)

    estado = _secrets.token_urlsafe(16)
    url = f"{AUTORIZAR}?" + urllib.parse.urlencode({
        "client_key": args.client_key,
        "response_type": "code",
        "scope": args.scopes,
        "redirect_uri": args.redirect,
        "state": estado,
    })

    print(">>> ABRE ESTA URL CON LA CUENTA QUE ADMINISTRA EL TIKTOK:\n")
    print(url + "\n")

    # TikTok rechaza las redirect URI de localhost y exige HTTPS, así que la
    # vía normal es la manual: el código se copia de la barra de direcciones.
    # Imprimimos la URL ANTES de comprobarlo; si no, no habría forma de
    # obtener el código.
    partes = urllib.parse.urlparse(args.redirect)
    if partes.scheme != "http" or partes.hostname not in ("localhost", "127.0.0.1"):
        print(f"La redirect URI ({args.redirect}) no apunta a este equipo, así "
              "que el código hay que recogerlo a mano:\n"
              "  1. Abre la URL de arriba y autoriza.\n"
              f"  2. Aterrizarás en {args.redirect}?code=…&state=…\n"
              f"  3. Comprueba que el state es exactamente: {estado}\n"
              "  4. Copia el valor de `code` (todo, hasta el & siguiente) y "
              "vuelve a ejecutar este script añadiendo:\n"
              f"       --redirect {args.redirect} --code <el code>\n"
              "     El código caduca en pocos minutos: no lo dejes reposar.")
        return 0

    client_secret = secreto()
    print(f"Esperando el callback en {args.redirect} …")

    servidor = HTTPServer((partes.hostname, partes.port or 80), _Recoge)
    servidor.handle_request()
    servidor.server_close()
    datos = _Recoge.resultado

    if "error" in datos:
        print(f"\n✗ TikTok ha rechazado la autorización: {datos.get('error')} — "
              f"{datos.get('error_description', '')}")
        return 1
    if datos.get("state") != estado:
        print("\n✗ El `state` no coincide: descarto la respuesta por seguridad.")
        return 1
    if "code" not in datos:
        print(f"\n✗ No ha llegado ningún código. Respuesta: {datos}")
        return 1

    return _canjear(args.client_key, client_secret, datos["code"], args.redirect)


if __name__ == "__main__":
    raise SystemExit(main())

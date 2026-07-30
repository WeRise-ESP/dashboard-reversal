"""
Genera el REFRESH TOKEN de LinkedIn para la página de Reversal Institute.

    python scripts/linkedin_refresh_token.py 77hl0lbpekgnae

El Client Secret NO se pasa como argumento: el script lo pide por teclado sin
mostrarlo. Un secreto en la línea de comandos acaba en el historial del shell,
en la lista de procesos y en cualquier captura de pantalla de la terminal.
Si necesitas automatizarlo, usa la variable de entorno LINKEDIN_CLIENT_SECRET.

Requisitos previos, en la app de LinkedIn (linkedin.com/developers/apps):

  1. Pestaña *Settings* → página verificada contra Reversal Institute.
  2. Pestaña *Products* → **Community Management API** concedida.
     ⚠️ Tiene que ser el ÚNICO producto: LinkedIn ni siquiera deja pedirla si
     hay otro producto concedido o una solicitud pendiente. Si te equivocas,
     no hay vuelta atrás: toca app nueva y volver a verificar la página.
     Señal de que aún no está: en *Auth* → *OAuth 2.0 scopes* pone
     «No permissions added».
  3. Pestaña *Auth* → *Authorized redirect URLs*. Por defecto el script usa
         http://localhost:8765/callback
     pero si ya tienes registrada otra, pásala tal cual con --redirect y no
     hace falta tocar nada en LinkedIn:
         --redirect http://localhost:3000/auth/callback

     ⚠️ LinkedIn compara la URL carácter a carácter. «The redirect_uri does not
     match the registered value» significa que hay alguna diferencia, por
     pequeña que sea: http vs https, localhost vs 127.0.0.1, una barra final
     de más, otro puerto, u otra ruta. Copia y pega, no la escribas a mano.

Al ejecutarlo se imprime una URL: ábrela con una cuenta **administradora de la
página de Reversal Institute** y acepta. El script recoge la respuesta, canjea
el código y escupe la sección [linkedin] lista para pegar en secrets.toml.

Los scopes son de solo lectura sobre vuestra propia página.

⚠️ El refresh token de LinkedIn dura **12 meses** y el access token 60 días. El
conector canjea el refresh en cada carga, así que lo único que hay que renovar
—una vez al año— es lo que genera este script. Apúntalo en el calendario: el
día que caduque, LinkedIn deja de dar datos sin más aviso.
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets as _secrets
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

AUTORIZAR = "https://www.linkedin.com/oauth/v2/authorization"
TOKEN = "https://www.linkedin.com/oauth/v2/accessToken"

# Lectura de la actividad y de las estadísticas de la propia organización.
SCOPES_POR_DEFECTO = "r_organization_social rw_organization_admin"

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

    def log_message(self, *_):  # silencia el log del servidor
        pass


def main() -> int:
    p = argparse.ArgumentParser(description="Refresh token de LinkedIn.")
    p.add_argument("client_id")
    p.add_argument("--redirect", default="http://localhost:8765/callback",
                   help="la redirect URL EXACTA que tengas en la pestaña Auth "
                        "de la app (por defecto http://localhost:8765/callback)")
    p.add_argument("--scopes", default=SCOPES_POR_DEFECTO)
    args = p.parse_args()

    client_secret = os.environ.get("LINKEDIN_CLIENT_SECRET") or getpass.getpass(
        "Client Secret (no se muestra al teclear): ").strip()
    if not client_secret:
        print("✗ Sin Client Secret no se puede canjear el código.")
        return 1

    redirect = args.redirect
    partes = urllib.parse.urlparse(redirect)
    if partes.scheme != "http" or partes.hostname not in ("localhost", "127.0.0.1"):
        print(f"✗ --redirect tiene que apuntar a este equipo para poder recoger "
              f"la respuesta, y ser http://localhost:… o http://127.0.0.1:…\n"
              f"  Has pasado: {redirect}")
        return 1
    puerto = partes.port or 80

    estado = _secrets.token_urlsafe(16)
    url = f"{AUTORIZAR}?" + urllib.parse.urlencode({
        "response_type": "code",
        "client_id": args.client_id,
        "redirect_uri": redirect,
        "state": estado,
        "scope": args.scopes,
    })

    print(">>> ABRE ESTA URL CON UNA CUENTA ADMIN DE LA PÁGINA:\n")
    print(url + "\n")
    print(f"Esperando el callback en {redirect} …")

    servidor = HTTPServer((partes.hostname, puerto), _Recoge)
    servidor.handle_request()
    servidor.server_close()
    datos = _Recoge.resultado

    if "error" in datos:
        print(f"\n✗ LinkedIn ha rechazado la autorización: "
              f"{datos.get('error')} — {datos.get('error_description', '')}")
        # LinkedIn usa los dos nombres para lo mismo según el caso, y ninguno
        # dice lo que de verdad pasa: que el producto no está concedido.
        if datos.get("error") in ("invalid_scope_error", "unauthorized_scope_error"):
            print(f"  Scopes pedidos: {args.scopes}")
            print("  → La app NO tiene concedida la Community Management API.")
            print("    Pestaña Products → Community Management API → Request "
                  "access. Hasta que no aparezca concedida, estos scopes no "
                  "existen para la app y el OAuth falla aquí siempre.")
            print("    ⚠️ No añadas ningún otro producto para «probar»: "
                  "Community Management tiene que ser el ÚNICO, y si metes "
                  "otro al lado la app queda inservible.")
        return 1
    if datos.get("state") != estado:
        print("\n✗ El `state` no coincide: descarto la respuesta por seguridad.")
        return 1
    if "code" not in datos:
        print(f"\n✗ No ha llegado ningún código. Respuesta: {datos}")
        return 1

    r = requests.post(TOKEN, data={
        "grant_type": "authorization_code",
        "code": datos["code"],
        "client_id": args.client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect,
    }, timeout=60)
    if r.status_code != 200:
        print(f"\n✗ Fallo al canjear el código ({r.status_code}): {r.text[:300]}")
        return 1

    t = r.json()
    refresh = t.get("refresh_token")
    if not refresh:
        print("\n✗ LinkedIn no ha devuelto refresh_token, solo access_token.")
        print("  → Pasa cuando la app no tiene un producto que los conceda. "
              "Confirma que Community Management API está APROBADA (no solo "
              "solicitada) en la pestaña Products.")
        print(f"  → El access token dura {t.get('expires_in', '?')} s; no sirve "
              "para un job diario.")
        return 1

    print("\n" + "=" * 68)
    print("✅ Pega esto en .streamlit/secrets.toml:")
    print("=" * 68)
    print("[linkedin]")
    print(f'client_id       = "{args.client_id}"')
    print('client_secret   = "…"   # el que acabas de teclear')
    print(f'refresh_token   = "{refresh}"')
    print('organization_id = "123114024"   # ya está en config.py; opcional aquí')
    print('version         = "202506"')
    print("=" * 68)
    dias = int(t.get("refresh_token_expires_in", 0)) // 86400
    if dias:
        print(f"\n⚠️ El refresh token caduca en {dias} días. Ponte un aviso.")
    print("\nDespués: python scripts/verificar_social.py --red LinkedIn")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

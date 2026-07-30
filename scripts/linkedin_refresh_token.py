"""
Genera el REFRESH TOKEN de LinkedIn para la página de Reversal Institute.

    python scripts/linkedin_refresh_token.py <CLIENT_ID> <CLIENT_SECRET>

Requisitos previos, en la app **ReversalLinkd** (linkedin.com/developers/apps):

  1. Pestaña *Settings* → página verificada.  ✅ hecho el 30-jul-2026
  2. Pestaña *Products* → **Community Management API** concedida.
     ⚠️ Tiene que ser el ÚNICO producto de la app: no convive con Marketing
     Developer Platform. Si añades otro, la app queda inservible.
  3. Pestaña *Auth* → *Authorized redirect URLs* → añade EXACTAMENTE:
         http://localhost:8765/callback
     LinkedIn compara la URL carácter a carácter; si no coincide, el login
     falla con redirect_uri_mismatch antes de pedirte permiso siquiera.

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
import secrets as _secrets
import sys
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
    p.add_argument("client_secret")
    p.add_argument("--puerto", type=int, default=8765,
                   help="debe coincidir con la redirect URL registrada (8765)")
    p.add_argument("--scopes", default=SCOPES_POR_DEFECTO)
    args = p.parse_args()

    redirect = f"http://localhost:{args.puerto}/callback"
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

    servidor = HTTPServer(("localhost", args.puerto), _Recoge)
    servidor.handle_request()
    servidor.server_close()
    datos = _Recoge.resultado

    if "error" in datos:
        print(f"\n✗ LinkedIn ha rechazado la autorización: "
              f"{datos.get('error')} — {datos.get('error_description', '')}")
        if datos.get("error") == "unauthorized_scope_error":
            print("  → La app todavía no tiene concedida la Community "
                  "Management API, o no incluye estos scopes.")
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
        "client_secret": args.client_secret,
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
    print(f'client_secret   = "{args.client_secret}"')
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

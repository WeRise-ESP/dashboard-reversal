"""
Genera el REFRESH TOKEN de Google Ads (para dejar el dashboard en vivo).

Dos formas de usarlo:

  A) Con client_id y client_secret directamente (recomendado):
        python scripts/google_ads_refresh_token.py <CLIENT_ID> <CLIENT_SECRET>

  B) Con el JSON del cliente OAuth (si lo descargaste al crearlo):
        python scripts/google_ads_refresh_token.py <ruta/al/client_secret.json>

Requisitos:
  - Un cliente OAuth de tipo "App de escritorio" en Google Cloud Console.
    (Si el secreto está enmascarado, pulsa "+ Add secret" para generar uno
     nuevo y cópialo; el Client ID completo está arriba en la ficha del cliente.)

Al ejecutarlo se abre el navegador: inicia sesión con una cuenta que TENGA
acceso a la cuenta de Google Ads 2970533333 y acepta los permisos. El script
imprime el refresh_token para pegar en .streamlit/secrets.toml [google_ads].
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/adwords"]


def _flow_desde_args():
    args = sys.argv[1:]
    if len(args) == 1 and args[0].endswith(".json"):
        return InstalledAppFlow.from_client_secrets_file(args[0], SCOPES)
    if len(args) == 2:
        client_id, client_secret = args
        config = {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost"],
            }
        }
        return InstalledAppFlow.from_client_config(config, SCOPES)
    print("Uso:")
    print("  python scripts/google_ads_refresh_token.py <CLIENT_ID> <CLIENT_SECRET>")
    print("  python scripts/google_ads_refresh_token.py <client_secret.json>")
    sys.exit(1)


def main():
    flow = _flow_desde_args()
    creds = flow.run_local_server(
        port=0, open_browser=False, prompt="consent",
        authorization_prompt_message=">>> ABRE ESTA URL PARA AUTORIZAR:\n{url}\n",
    )

    print("\n" + "=" * 60)
    print("✅ REFRESH TOKEN generado. Cópialo a secrets.toml [google_ads]:")
    print("=" * 60)
    print(f'refresh_token = "{creds.refresh_token}"')
    print(f'client_id     = "{creds.client_id}"')
    print(f'client_secret = "{creds.client_secret}"')
    print("=" * 60)


if __name__ == "__main__":
    main()

"""
Genera el REFRESH TOKEN de YouTube (canal de Reversal Institute).

    python scripts/youtube_refresh_token.py <CLIENT_ID> <CLIENT_SECRET>
    python scripts/youtube_refresh_token.py <ruta/al/client_secret.json>

Requisitos previos, en el proyecto de Google Cloud donde ya vive GA4:
  1. Habilitar **YouTube Data API v3** y **YouTube Analytics API**.
     https://console.cloud.google.com/apis/library/youtube.googleapis.com
     https://console.cloud.google.com/apis/library/youtubeanalytics.googleapis.com
  2. Crear un cliente OAuth de tipo **App de escritorio**.
     https://console.cloud.google.com/apis/credentials

⚠️ Al abrir la URL, inicia sesión con la cuenta **PROPIETARIA del canal**. La
YouTube Analytics API no admite service account —a diferencia de GA4—, así que
el refresh token queda ligado a esa persona: si un día pierde el acceso al
canal, el conector deja de funcionar y hay que regenerarlo con otra cuenta.

Los scopes son de SOLO LECTURA: no permiten publicar, editar ni borrar nada.
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",  # métricas
    "https://www.googleapis.com/auth/youtube.readonly",       # canal y vídeos
]


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
    print("  python scripts/youtube_refresh_token.py <CLIENT_ID> <CLIENT_SECRET>")
    print("  python scripts/youtube_refresh_token.py <client_secret.json>")
    sys.exit(1)


def main():
    flow = _flow_desde_args()
    creds = flow.run_local_server(
        port=0, open_browser=False, prompt="consent",
        authorization_prompt_message=">>> ABRE ESTA URL CON LA CUENTA DUEÑA DEL CANAL:\n{url}\n",
    )

    canal = ""
    try:
        from googleapiclient.discovery import build
        items = (build("youtube", "v3", credentials=creds, cache_discovery=False)
                 .channels().list(part="snippet", mine=True).execute()
                 .get("items", []))
        if items:
            canal = items[0]["id"]
            print(f"\nCanal autorizado: «{items[0]['snippet']['title']}» ({canal})")
    except Exception as e:  # noqa: BLE001
        print(f"\n(No se ha podido leer el canal automáticamente: {e})")

    print("\n" + "=" * 68)
    print("✅ Pega esto en .streamlit/secrets.toml:")
    print("=" * 68)
    print("[youtube]")
    print(f'client_id     = "{creds.client_id}"')
    print(f'client_secret = "{creds.client_secret}"')
    print(f'refresh_token = "{creds.refresh_token}"')
    print(f'channel_id    = "{canal}"' if canal else 'channel_id    = ""  # UC... de youtube.com/account_advanced')
    print("=" * 68)
    print("\nDespués: python scripts/verificar_social.py --red YouTube")


if __name__ == "__main__":
    main()

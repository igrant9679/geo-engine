"""Google sign-in for Search Console + Drive/Docs.

One-time:  python google_auth.py   (opens a browser; sign in with the Google account
that the clients add to Search Console and that will own the client Google Docs).
"""
from common import DATA, ENGINE

SCOPES = [
    "https://www.googleapis.com/auth/webmasters",   # Search Console read + sitemap submit + URL inspection
    "https://www.googleapis.com/auth/drive.file",   # only files/folders this app creates
]
TOKEN = DATA / "google_token.json"
CLIENT_SECRET = ENGINE / "google_client_secret.json"


def creds():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    c = Credentials.from_authorized_user_file(str(TOKEN), SCOPES) if TOKEN.exists() else None
    if c and c.expired and c.refresh_token:
        c.refresh(Request())
        TOKEN.write_text(c.to_json(), encoding="utf-8")
    if not c or not c.valid:
        raise SystemExit("Google token missing or revoked. Run: python google_auth.py")
    return c


def service(name, version):
    from googleapiclient.discovery import build
    return build(name, version, credentials=creds(), cache_discovery=False)


if __name__ == "__main__":
    from google_auth_oauthlib.flow import InstalledAppFlow

    DATA.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    c = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    TOKEN.write_text(c.to_json(), encoding="utf-8")
    print(f"Saved {TOKEN}")

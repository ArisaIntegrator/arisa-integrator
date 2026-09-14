import os
import secrets
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse

load_dotenv()

app = FastAPI(
    title="Arisa Integrator",
    version="0.1.0",
)

CLIENT_ID = os.getenv("ALLEGRO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ALLEGRO_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ALLEGRO_REDIRECT_URI")
USER_AGENT = os.getenv("ALLEGRO_USER_AGENT")

ALLEGRO_AUTH_URL = "https://allegro.pl.allegrosandbox.pl/auth/oauth/authorize"
ALLEGRO_TOKEN_URL = "https://allegro.pl.allegrosandbox.pl/auth/oauth/token"
ALLEGRO_API_URL = "https://api.allegro.pl.allegrosandbox.pl"

oauth_state = None
access_token = None
connected_user = None


@app.get("/", response_class=HTMLResponse)
async def home():
    if connected_user:
        status = f"""
        <p style="color:#4ade80;font-size:18px;">
            Allegro: połączone ✓
        </p>
        <p>Konto: <strong>{connected_user.get("login", "nieznane")}</strong></p>
        """
    else:
        status = """
        <p>Allegro: niepołączone</p>
        <a href="/allegro/login">
            <button>Połącz Allegro</button>
        </a>
        """

    return f"""
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Arisa Integrator</title>

        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #111827;
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}

            .panel {{
                background: #1f2937;
                padding: 50px;
                border-radius: 16px;
                text-align: center;
                width: 420px;
            }}

            .version {{
                color: #9ca3af;
                margin-bottom: 35px;
            }}

            button {{
                padding: 14px 28px;
                font-size: 16px;
                border: 0;
                border-radius: 8px;
                cursor: pointer;
            }}
        </style>
    </head>

    <body>
        <div class="panel">
            <h1>Arisa Integrator</h1>
            <div class="version">DEV 0.1.0</div>
            {status}
        </div>
    </body>
    </html>
    """


@app.get("/allegro/login")
async def allegro_login():
    global oauth_state

    if not CLIENT_ID or not CLIENT_SECRET:
        return HTMLResponse(
            "Brakuje danych Allegro w pliku .env.",
            status_code=500,
        )

    oauth_state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": oauth_state,
    }

    url = f"{ALLEGRO_AUTH_URL}?{urlencode(params)}"

    return RedirectResponse(url)


@app.get("/allegro/callback")
async def allegro_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    error_description: str | None = None,
):
    global access_token
    global connected_user

    if error:
        return HTMLResponse(
            f"""
            <h2>Błąd autoryzacji Allegro</h2>
            <p><strong>{error}</strong></p>
            <p>{error_description or "Brak dodatkowego opisu."}</p>
            """,
            status_code=400,
        )

    if not code:
        return HTMLResponse(
            "Allegro nie zwróciło kodu autoryzacyjnego.",
            status_code=400,
        )

    if not state or state != oauth_state:
        return HTMLResponse(
            "Nieprawidłowy parametr OAuth state.",
            status_code=400,
        )

    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            ALLEGRO_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": REDIRECT_URI,
            },
            auth=(CLIENT_ID, CLIENT_SECRET),
            headers={
                "User-Agent": USER_AGENT,
            },
        )

    if token_response.status_code != 200:
        return HTMLResponse(
            f"""
            <h2>Nie udało się pobrać tokena</h2>
            <p>HTTP {token_response.status_code}</p>
            <pre>{token_response.text}</pre>
            """,
            status_code=500,
        )

    tokens = token_response.json()
    access_token = tokens["access_token"]

    async with httpx.AsyncClient() as client:
        me_response = await client.get(
            f"{ALLEGRO_API_URL}/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.allegro.public.v1+json",
                "User-Agent": USER_AGENT,
            },
        )

    if me_response.status_code != 200:
        return HTMLResponse(
            f"""
            <h2>Token działa, ale nie udało się odczytać konta</h2>
            <p>HTTP {me_response.status_code}</p>
            <pre>{me_response.text}</pre>
            """,
            status_code=500,
        )

    connected_user = me_response.json()

    return RedirectResponse("/")
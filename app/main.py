from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(
    title="Arisa Integrator",
    version="0.1.0"
)


@app.get("/", response_class=HTMLResponse)
async def home():
    return """
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Arisa Integrator</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #111827;
                color: white;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }

            .panel {
                background: #1f2937;
                padding: 50px;
                border-radius: 16px;
                text-align: center;
                width: 420px;
            }

            .version {
                color: #9ca3af;
                margin-bottom: 35px;
            }

            button {
                padding: 14px 28px;
                font-size: 16px;
                border: 0;
                border-radius: 8px;
                cursor: pointer;
            }
        </style>
    </head>

    <body>
        <div class="panel">
            <h1>Arisa Integrator</h1>
            <div class="version">DEV 0.1.0</div>
            <p>Allegro: niepołączone</p>
            <button>Połącz Allegro</button>
        </div>
    </body>
    </html>
    """
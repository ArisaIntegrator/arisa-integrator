from html import escape
import os
import secrets
from urllib.parse import urlencode

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse


# ==================================================
# KONFIGURACJA
# ==================================================

load_dotenv()

app = FastAPI(
    title="Arisa Integrator",
    version="0.1.2",
)

CLIENT_ID = os.getenv("ALLEGRO_CLIENT_ID")
CLIENT_SECRET = os.getenv("ALLEGRO_CLIENT_SECRET")
REDIRECT_URI = os.getenv("ALLEGRO_REDIRECT_URI")
USER_AGENT = os.getenv("ALLEGRO_USER_AGENT")

ALLEGRO_AUTH_URL = (
    "https://allegro.pl.allegrosandbox.pl/auth/oauth/authorize"
)

ALLEGRO_TOKEN_URL = (
    "https://allegro.pl.allegrosandbox.pl/auth/oauth/token"
)

ALLEGRO_API_URL = (
    "https://api.allegro.pl.allegrosandbox.pl"
)


# ==================================================
# TYMCZASOWY STAN APLIKACJI
# Później tokeny przeniesiemy do bazy danych
# ==================================================

oauth_state = None
access_token = None
connected_user = None
picking_progress = {}


# ==================================================
# FUNKCJE POMOCNICZE
# ==================================================

def allegro_headers():
    return {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.allegro.public.v1+json",
        "User-Agent": USER_AGENT,
    }


def safe(value, default="—"):
    if value is None or value == "":
        return escape(str(default))

    return escape(str(value))


# ==================================================
# STRONA GŁÓWNA
# ==================================================

@app.get("/", response_class=HTMLResponse)
async def home():

    if connected_user:

        login = safe(
            connected_user.get("login"),
            "nieznane",
        )

        status = f"""
        <p class="connected">
            Allegro: połączone ✓
        </p>

        <p>
            Konto:
            <strong>{login}</strong>
        </p>

        <a href="/orders">
            <button>
                Zamówienia
            </button>
        </a>
        """

    else:

        status = """
        <p>
            Allegro: niepołączone
        </p>

        <a href="/allegro/login">
            <button>
                Połącz Allegro
            </button>
        </a>
        """

    return f"""
    <!DOCTYPE html>

    <html lang="pl">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Arisa Integrator
        </title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                min-height: 100vh;

                display: flex;
                align-items: center;
                justify-content: center;

                background: #111827;
                color: white;

                font-family: Arial, sans-serif;
            }}

            .panel {{
                width: 430px;

                padding: 50px;

                background: #1f2937;

                border-radius: 16px;

                text-align: center;
            }}

            h1 {{
                margin-top: 0;
            }}

            .version {{
                color: #9ca3af;

                margin-bottom: 35px;
            }}

            .connected {{
                color: #4ade80;
                font-size: 18px;
            }}

            button {{
                margin-top: 18px;

                padding: 14px 28px;

                border: 0;
                border-radius: 8px;

                background: #f3f4f6;
                color: #111827;

                font-size: 16px;

                cursor: pointer;
            }}

            button:hover {{
                background: white;
            }}

            a {{
                text-decoration: none;
            }}

        </style>

    </head>

    <body>

        <div class="panel">

            <h1>
                Arisa Integrator
            </h1>

            <div class="version">
                DEV 0.1.2
            </div>

            {status}

        </div>

    </body>

    </html>
    """


# ==================================================
# LOGOWANIE ALLEGRO
# ==================================================

@app.get("/allegro/login")
async def allegro_login():

    global oauth_state

    if (
        not CLIENT_ID
        or not CLIENT_SECRET
        or not REDIRECT_URI
        or not USER_AGENT
    ):

        return HTMLResponse(
            """
            <h2>
                Brakuje konfiguracji Allegro
                w pliku .env.
            </h2>
            """,
            status_code=500,
        )

    oauth_state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": oauth_state,
    }

    authorization_url = (
        f"{ALLEGRO_AUTH_URL}?"
        f"{urlencode(params)}"
    )

    return RedirectResponse(
        authorization_url
    )


# ==================================================
# CALLBACK OAUTH
# ==================================================

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
            <h2>
                Błąd autoryzacji Allegro
            </h2>

            <p>
                <strong>
                    {safe(error)}
                </strong>
            </p>

            <p>
                {safe(error_description)}
            </p>
            """,
            status_code=400,
        )

    if not code:

        return HTMLResponse(
            """
            Allegro nie zwróciło
            kodu autoryzacyjnego.
            """,
            status_code=400,
        )

    if (
        not state
        or state != oauth_state
    ):

        return HTMLResponse(
            """
            Nieprawidłowy parametr OAuth state.
            """,
            status_code=400,
        )

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        token_response = await client.post(
            ALLEGRO_TOKEN_URL,

            data={
                "grant_type":
                    "authorization_code",

                "code":
                    code,

                "redirect_uri":
                    REDIRECT_URI,
            },

            auth=(
                CLIENT_ID,
                CLIENT_SECRET,
            ),

            headers={
                "User-Agent":
                    USER_AGENT,
            },
        )

    if token_response.status_code != 200:

        return HTMLResponse(
            f"""
            <h2>
                Nie udało się pobrać tokena
            </h2>

            <p>
                HTTP
                {token_response.status_code}
            </p>

            <pre>
                {escape(token_response.text)}
            </pre>
            """,
            status_code=500,
        )

    tokens = token_response.json()

    access_token = tokens.get(
        "access_token"
    )

    if not access_token:

        return HTMLResponse(
            """
            <h2>
                Allegro nie zwróciło
                access tokena.
            </h2>
            """,
            status_code=500,
        )

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        me_response = await client.get(
            f"{ALLEGRO_API_URL}/me",
            headers=allegro_headers(),
        )

    if me_response.status_code != 200:

        return HTMLResponse(
            f"""
            <h2>
                Nie udało się odczytać konta
            </h2>

            <p>
                HTTP
                {me_response.status_code}
            </p>

            <pre>
                {escape(me_response.text)}
            </pre>
            """,
            status_code=500,
        )

    connected_user = (
        me_response.json()
    )

    return RedirectResponse("/")


# ==================================================
# LISTA ZAMÓWIEŃ
# ==================================================

@app.get(
    "/orders",
    response_class=HTMLResponse
)
async def orders():

    if not access_token:

        return HTMLResponse(
            """
            <h2>
                Brak aktywnego połączenia
                z Allegro.
            </h2>

            <a href="/">
                Powrót
            </a>
            """,
            status_code=401,
        )

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        response = await client.get(
            (
                f"{ALLEGRO_API_URL}"
                "/order/checkout-forms"
            ),

            headers=allegro_headers(),

            params={
                "limit": 100,
            },
        )

    if response.status_code != 200:

        return HTMLResponse(
            f"""
            <h2>
                Nie udało się pobrać zamówień
            </h2>

            <p>
                HTTP
                {response.status_code}
            </p>

            <pre>
                {escape(response.text)}
            </pre>
            """,
            status_code=500,
        )

    data = response.json()

    checkout_forms = (
        data.get("checkoutForms")
        or []
    )

    cards = []

    for order in checkout_forms:

        order_id_raw = str(
            order.get(
                "id",
                ""
            )
        )

        order_id = safe(
            order_id_raw
        )

        order_status = safe(
            order.get("status")
        )

        buyer = (
            order.get("buyer")
            or {}
        )

        buyer_login = safe(
            buyer.get("login")
        )

        fulfillment = (
            order.get("fulfillment")
            or {}
        )

        fulfillment_status = safe(
            fulfillment.get("status")
        )

        delivery = (
            order.get("delivery")
            or {}
        )

        delivery_method = (
            delivery.get("method")
            or {}
        )

        delivery_name = safe(
            delivery_method.get("name")
        )

        summary = (
            order.get("summary")
            or {}
        )

        total_to_pay = (
            summary.get("totalToPay")
            or {}
        )

        total_amount = safe(
            total_to_pay.get("amount")
        )

        total_currency = safe(
            total_to_pay.get("currency"),
            "",
        )

        items_html = ""

        for item in (
            order.get("lineItems")
            or []
        ):

            offer = (
                item.get("offer")
                or {}
            )

            product_name = safe(
                offer.get("name"),
                "Produkt",
            )

            quantity = safe(
                item.get("quantity"),
                "0",
            )

            items_html += f"""
            <div class="item">

                <strong>
                    {product_name}
                </strong>

                <strong>
                    {quantity} szt.
                </strong>

            </div>
            """

        cards.append(
            f"""
            <div class="order-card">

                <div class="order-top">

                    <div>

                        <div class="order-title">
                            Zamówienie
                        </div>

                        <div class="order-id">
                            {order_id}
                        </div>

                    </div>

                    <div class="price">
                        {total_amount}
                        {total_currency}
                    </div>

                </div>

                <div class="info-row">

                    Kupujący:

                    <strong>
                        {buyer_login}
                    </strong>

                </div>

                <div class="info-row">

                    Status zamówienia:

                    <strong>
                        {order_status}
                    </strong>

                </div>

                <div class="info-row">

                    Status realizacji:

                    <strong>
                        {fulfillment_status}
                    </strong>

                </div>

                <div class="info-row">

                    Dostawa:

                    <strong>
                        {delivery_name}
                    </strong>

                </div>

                <div class="products">

                    {items_html}

                </div>

                <a
                    href="/orders/{order_id_raw}"
                >

                    <button>
                        Otwórz zamówienie
                    </button>

                </a>

            </div>
            """
        )

    if not cards:

        cards.append(
            """
            <div class="empty">

                Brak zamówień
                na koncie Allegro.

            </div>
            """
        )

    orders_html = "".join(cards)

    return f"""
    <!DOCTYPE html>

    <html lang="pl">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Zamówienia - Arisa Integrator
        </title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;

                padding: 40px 20px;

                background: #111827;

                color: white;

                font-family:
                    Arial,
                    sans-serif;
            }}

            .container {{
                max-width: 1000px;

                margin: auto;
            }}

            .back {{
                color: #9ca3af;

                text-decoration: none;
            }}

            h1 {{
                margin-top: 30px;

                margin-bottom: 30px;
            }}

            .order-card {{
                background: #1f2937;

                padding: 25px;

                border-radius: 14px;

                margin-bottom: 20px;
            }}

            .order-top {{
                display: flex;

                justify-content:
                    space-between;

                gap: 20px;

                margin-bottom: 25px;
            }}

            .order-title {{
                font-size: 20px;

                font-weight: bold;
            }}

            .order-id {{
                color: #9ca3af;

                font-size: 13px;

                margin-top: 6px;
            }}

            .price {{
                font-size: 22px;

                font-weight: bold;
            }}

            .info-row {{
                margin: 9px 0;
            }}

            .products {{
                margin-top: 22px;
                margin-bottom: 20px;

                border-top:
                    1px solid #374151;

                border-bottom:
                    1px solid #374151;
            }}

            .item {{
                display: flex;

                align-items: center;

                justify-content:
                    space-between;

                gap: 20px;

                padding: 15px 0;
            }}

            button {{
                padding: 12px 20px;

                border: 0;

                border-radius: 8px;

                cursor: pointer;
            }}

            .empty {{
                background: #1f2937;

                padding: 25px;

                border-radius: 14px;
            }}

        </style>

    </head>

    <body>

        <div class="container">

            <a
                class="back"
                href="/"
            >
                ← Powrót
            </a>

            <h1>
                Zamówienia
            </h1>

            {orders_html}

        </div>

    </body>

    </html>
    """


# ==================================================
# SZCZEGÓŁY ZAMÓWIENIA
# ==================================================

@app.get(
    "/orders/{order_id}",
    response_class=HTMLResponse
)
async def order_details(
    order_id: str
):

    if not access_token:

        return HTMLResponse(
            """
            <h2>
                Brak aktywnego połączenia
                z Allegro.
            </h2>

            <a href="/">
                Powrót
            </a>
            """,
            status_code=401,
        )

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        response = await client.get(
            (
                f"{ALLEGRO_API_URL}"
                f"/order/checkout-forms/{order_id}"
            ),

            headers=allegro_headers(),
        )

    if response.status_code == 404:

        return HTMLResponse(
            """
            <h2>
                Nie znaleziono zamówienia.
            </h2>

            <a href="/orders">
                Powrót
            </a>
            """,
            status_code=404,
        )

    if response.status_code != 200:

        return HTMLResponse(
            f"""
            <h2>
                Nie udało się pobrać
                zamówienia
            </h2>

            <p>
                HTTP
                {response.status_code}
            </p>

            <pre>
                {escape(response.text)}
            </pre>
            """,
            status_code=500,
        )

    order = response.json()

    # ----------------------------------------------
    # KUPUJĄCY
    # ----------------------------------------------

    buyer = (
        order.get("buyer")
        or {}
    )

    buyer_login = safe(
        buyer.get("login")
    )

    buyer_email = safe(
        buyer.get("email")
    )

    buyer_phone = safe(
        buyer.get("phoneNumber")
    )

    buyer_first_name = safe(
        buyer.get("firstName")
    )

    buyer_last_name = safe(
        buyer.get("lastName")
    )

    # ----------------------------------------------
    # STATUS
    # ----------------------------------------------

    order_status = safe(
        order.get("status")
    )

    fulfillment = (
        order.get("fulfillment")
        or {}
    )

    fulfillment_status = safe(
        fulfillment.get("status")
    )

    # ----------------------------------------------
    # DOSTAWA
    # ----------------------------------------------

    delivery = (
        order.get("delivery")
        or {}
    )

    delivery_method = (
        delivery.get("method")
        or {}
    )

    delivery_name = safe(
        delivery_method.get("name")
    )

    delivery_cost = (
        delivery.get("cost")
        or {}
    )

    delivery_cost_amount = safe(
        delivery_cost.get("amount"),
        "0.00",
    )

    delivery_cost_currency = safe(
        delivery_cost.get("currency"),
        "",
    )

    address = (
        delivery.get("address")
        or {}
    )

    address_first_name = safe(
        address.get("firstName")
    )

    address_last_name = safe(
        address.get("lastName")
    )

    address_street = safe(
        address.get("street")
    )

    address_city = safe(
        address.get("city")
    )

    address_zip = safe(
        address.get("zipCode")
    )

    address_phone = safe(
        address.get("phoneNumber")
    )

    pickup_point = (
        delivery.get("pickupPoint")
        or {}
    )

    pickup_id = safe(
        pickup_point.get("id")
    )

    pickup_name = safe(
        pickup_point.get("name")
    )

    pickup_description = safe(
        pickup_point.get("description")
    )

    # ----------------------------------------------
    # FAKTURA
    # ----------------------------------------------

    invoice = (
        order.get("invoice")
        or {}
    )

    invoice_required = (
        invoice.get("required")
        is True
    )

    invoice_text = (
        "TAK"
        if invoice_required
        else "NIE"
    )

    # ----------------------------------------------
    # WIADOMOŚĆ KUPUJĄCEGO
    # ----------------------------------------------

    message_to_seller = safe(
        order.get("messageToSeller")
    )

    # ----------------------------------------------
    # PODSUMOWANIE
    # ----------------------------------------------

    summary = (
        order.get("summary")
        or {}
    )

    total_to_pay = (
        summary.get("totalToPay")
        or {}
    )

    total_amount = safe(
        total_to_pay.get("amount")
    )

    total_currency = safe(
        total_to_pay.get("currency"),
        "",
    )

    # ----------------------------------------------
    # PRODUKTY
    # ----------------------------------------------

    product_rows = []

    for item in (
        order.get("lineItems")
        or []
    ):

        offer = (
            item.get("offer")
            or {}
        )

        product_name = safe(
            offer.get("name"),
            "Produkt",
        )

        quantity = safe(
            item.get("quantity"),
            "0",
        )

        price = (
            item.get("price")
            or {}
        )

        price_amount = safe(
            price.get("amount")
        )

        price_currency = safe(
            price.get("currency"),
            "",
        )

        external = (
            offer.get("external")
            or {}
        )

        sku = safe(
            external.get("id")
        )

        product_rows.append(
            f"""
            <div class="product-row">

                <div>

                    <div class="product-name">
                        {product_name}
                    </div>

                    <div class="sku">
                        SKU: {sku}
                    </div>

                </div>

                <div class="product-right">

                    <strong>
                        {quantity} szt.
                    </strong>

                    <div>
                        {price_amount}
                        {price_currency}
                    </div>

                </div>

            </div>
            """
        )

    products_html = "".join(
        product_rows
    )

    return f"""
    <!DOCTYPE html>

    <html lang="pl">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Szczegóły zamówienia
        </title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;

                padding: 40px 20px;

                background: #111827;

                color: white;

                font-family:
                    Arial,
                    sans-serif;
            }}

            .container {{
                max-width: 1000px;

                margin: auto;
            }}

            .back {{
                color: #9ca3af;

                text-decoration: none;
            }}

            h1 {{
                margin-top: 30px;
            }}

            .order-id {{
                color: #9ca3af;

                margin-bottom: 30px;
            }}

            .grid {{
                display: grid;

                grid-template-columns:
                    repeat(
                        2,
                        minmax(0, 1fr)
                    );

                gap: 20px;
            }}

            .card {{
                background: #1f2937;

                border-radius: 14px;

                padding: 25px;
            }}

            .card-wide {{
                grid-column:
                    1 / -1;
            }}

            h2 {{
                margin-top: 0;

                font-size: 20px;
            }}

            .row {{
                margin: 10px 0;
            }}

            .label {{
                color: #9ca3af;
            }}

            .product-row {{
                display: flex;

                justify-content:
                    space-between;

                gap: 20px;

                padding: 16px 0;

                border-bottom:
                    1px solid #374151;
            }}

            .product-row:last-child {{
                border-bottom: 0;
            }}

            .product-name {{
                font-weight: bold;
            }}

            .sku {{
                color: #9ca3af;

                font-size: 12px;

                margin-top: 5px;
            }}

            .product-right {{
                text-align: right;
            }}

            .total {{
                font-size: 28px;

                font-weight: bold;

                margin-top: 10px;
            }}

            .action {{
                width: 100%;

                padding: 16px;

                border: 0;

                border-radius: 10px;

                font-size: 17px;

                cursor: pointer;

                background: #f3f4f6;

                color: #111827;
            }}

            .action:hover {{
                background: white;
            }}

            @media (
                max-width: 700px
            ) {{

                .grid {{
                    grid-template-columns:
                        1fr;
                }}

                .card-wide {{
                    grid-column:
                        auto;
                }}

            }}

        </style>

    </head>

    <body>

        <div class="container">

            <a
                class="back"
                href="/orders"
            >
                ← Zamówienia
            </a>

            <h1>
                Zamówienie
            </h1>

            <div class="order-id">
                {safe(order_id)}
            </div>

            <div class="grid">

                <div class="card">

                    <h2>
                        Status
                    </h2>

                    <div class="row">

                        <span class="label">
                            Zamówienie:
                        </span>

                        <strong>
                            {order_status}
                        </strong>

                    </div>

                    <div class="row">

                        <span class="label">
                            Realizacja:
                        </span>

                        <strong>
                            {fulfillment_status}
                        </strong>

                    </div>

                </div>

                <div class="card">

                    <h2>
                        Kupujący
                    </h2>

                    <div class="row">
                        {buyer_login}
                    </div>

                    <div class="row">
                        {buyer_first_name}
                        {buyer_last_name}
                    </div>

                    <div class="row">
                        {buyer_email}
                    </div>

                    <div class="row">
                        {buyer_phone}
                    </div>

                </div>

                <div class="card card-wide">

                    <h2>
                        Produkty
                    </h2>

                    {products_html}

                </div>

                <div class="card">

                    <h2>
                        Dostawa
                    </h2>

                    <div class="row">

                        <strong>
                            {delivery_name}
                        </strong>

                    </div>

                    <div class="row">

                        {address_first_name}
                        {address_last_name}

                    </div>

                    <div class="row">
                        {address_street}
                    </div>

                    <div class="row">
                        {address_zip}
                        {address_city}
                    </div>

                    <div class="row">
                        {address_phone}
                    </div>

                    <hr>

                    <div class="row">

                        <span class="label">
                            Punkt odbioru:
                        </span>

                        <strong>
                            {pickup_id}
                        </strong>

                    </div>

                    <div class="row">
                        {pickup_name}
                    </div>

                    <div class="row">
                        {pickup_description}
                    </div>

                </div>

                <div class="card">

                    <h2>
                        Dokument
                    </h2>

                    <div class="row">

                        <span class="label">
                            Faktura:
                        </span>

                        <strong>
                            {invoice_text}
                        </strong>

                    </div>

                    <div class="row">

                        <span class="label">
                            Wiadomość kupującego:
                        </span>

                    </div>

                    <div class="row">
                        {message_to_seller}
                    </div>

                </div>

                <div class="card card-wide">

                    <h2>
                        Podsumowanie
                    </h2>

                    <div class="row">

                        Dostawa:
                        {delivery_cost_amount}
                        {delivery_cost_currency}

                    </div>

                    <div class="total">

                        Razem:
                        {total_amount}
                        {total_currency}

                    </div>

                </div>

                <div class="card card-wide">
                    <button
                        class="action"
                        onclick="window.location.href='/orders/{order_id}/picking'"
                    >
                         Rozpocznij kompletowanie

                    </button>

                </div>

            </div>

        </div>

    </body>

    </html>
    """
# ==================================================
# KOMPLETOWANIE ZAMÓWIENIA
# ==================================================

@app.get(
    "/orders/{order_id}/picking",
    response_class=HTMLResponse
)
async def picking(
    order_id: str
):

    if not access_token:

        return HTMLResponse(
            """
            <h2>
                Brak aktywnego połączenia z Allegro.
            </h2>

            <a href="/">
                Powrót
            </a>
            """,
            status_code=401,
        )

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        response = await client.get(
            (
                f"{ALLEGRO_API_URL}"
                f"/order/checkout-forms/{order_id}"
            ),
            headers=allegro_headers(),
        )

    if response.status_code != 200:

        return HTMLResponse(
            f"""
            <h2>
                Nie udało się pobrać zamówienia
            </h2>

            <p>
                HTTP {response.status_code}
            </p>

            <pre>
                {escape(response.text)}
            </pre>
            """,
            status_code=500,
        )

    order = response.json()

    products = []

    order_progress = picking_progress.setdefault(
        order_id,
        {}
    )

    total_required = 0
    total_collected = 0

    for item_index, item in enumerate(
        order.get("lineItems") or []
    ):

        offer = (
            item.get("offer")
            or {}
        )

        product_name = safe(
            offer.get("name"),
            "Produkt",
        )

        required_quantity = int(
            item.get("quantity") or 0
        )

        collected_quantity = min(
            int(
                order_progress.get(
                    item_index,
                    0
                )
            ),
            required_quantity,
        )

        total_required += required_quantity
        total_collected += collected_quantity

        external = (
            offer.get("external")
            or {}
        )

        sku = safe(
            external.get("id")
        )

        products.append(
            f"""
            <div class="product">

                <div>

                    <div class="product-name">
                        {product_name}
                    </div>

                    <div class="sku">
                        SKU: {sku}
                    </div>

                </div>

                <div class="quantity">
                    Zebrano:
                    <strong>
                        {collected_quantity}
                        /
                        {required_quantity}
                    </strong>
                </div>

                <form
                    method="post"
                    action="/orders/{order_id}/picking/confirm/{item_index}"
                >

                    <button
                        type="submit"
                        class="confirm"
                        {"disabled" if collected_quantity >=  required_quantity else""}
                    >
                        {
                         "✓ Skompletowane"
                            if collected_quantity >= required_quantity
                            else "Potwierdź ręcznie"
                        }
                    
                    </button>
                </form>

            </div>
            """
        )

    products_html = "".join(products)
    if total_required > 0:

        progress_percent = int(
            (
                total_collected
                / total_required
            )
            * 100
        )

    else:

        progress_percent = 0

    return f"""
    <!DOCTYPE html>

    <html lang="pl">

    <head>

        <meta charset="UTF-8">

        <meta
            name="viewport"
            content="width=device-width, initial-scale=1.0"
        >

        <title>
            Kompletowanie - Arisa Integrator
        </title>

        <style>

            * {{
                box-sizing: border-box;
            }}

            body {{
                margin: 0;
                padding: 40px 20px;

                background: #111827;
                color: white;

                font-family: Arial, sans-serif;
            }}

            .container {{
                max-width: 900px;
                margin: auto;
            }}

            .back {{
                color: #9ca3af;
                text-decoration: none;
            }}

            h1 {{
                margin-top: 30px;
                margin-bottom: 5px;
            }}

            .order-id {{
                color: #9ca3af;
                margin-bottom: 30px;
            }}

            .scan-box {{
                background: #1f2937;

                padding: 25px;

                border-radius: 14px;

                margin-bottom: 20px;
            }}

            .scan-box input {{
                width: 100%;

                padding: 16px;

                margin-top: 10px;

                border: 1px solid #374151;

                border-radius: 8px;

                background: #111827;
                color: white;

                font-size: 18px;
            }}

            .product {{
                background: #1f2937;

                padding: 22px;

                border-radius: 14px;

                margin-bottom: 15px;

                display: grid;

                grid-template-columns:
                    1fr auto auto;

                align-items: center;

                gap: 20px;
            }}

            .product-name {{
                font-size: 18px;
                font-weight: bold;
            }}

            .sku {{
                color: #9ca3af;

                font-size: 12px;

                margin-top: 5px;
            }}

            .quantity {{
                white-space: nowrap;
            }}

            .confirm {{
                padding: 12px 18px;

                border: 0;

                border-radius: 8px;

                cursor: pointer;
            }}
            .confirm:disabled {{
                opacity: 0.6;
                cursor: default;
            }}
            .progress {{
                background: #1f2937;

                padding: 25px;

                border-radius: 14px;

                margin-top: 25px;
            }}

            .bar {{
                height: 14px;

                background: #374151;

                border-radius: 20px;

                overflow: hidden;

                margin-top: 12px;
            }}

            .bar-fill {{
                width: {progress_percent}%;

                height: 100%;

                background: #f3f4f6;
            }}

            @media (
                max-width: 700px
            ) {{

                .product {{
                    grid-template-columns:
                        1fr;
                }}

            }}

        </style>

    </head>

    <body>

        <div class="container">

            <a
                class="back"
                href="/orders/{order_id}"
            >
                ← Zamówienie
            </a>

            <h1>
                Kompletowanie
            </h1>

            <div class="order-id">
                {safe(order_id)}
            </div>

            <div class="scan-box">

                <strong>
                    Zeskanuj EAN lub SKU
                </strong>

                <input
                    type="text"
                    placeholder="Zeskanuj lub wpisz kod produktu"
                    autofocus
                >

            </div>

            {products_html}

            <div class="progress">

                <strong>
                    Postęp: {progress_percent}%
                </strong>

                <div class="bar">

                    <div class="bar-fill">
                    </div>

                </div>

            </div>

        </div>

    </body>

    </html>
    """
@app.post(
    "/orders/{order_id}/picking/confirm/{item_index}"
)
async def confirm_picking(
    order_id: str,
    item_index: int,
):

    if not access_token:

        return RedirectResponse(
            "/",
            status_code=303,
        )

    async with httpx.AsyncClient(
        timeout=20.0
    ) as client:

        response = await client.get(
            (
                f"{ALLEGRO_API_URL}"
                f"/order/checkout-forms/{order_id}"
            ),
            headers=allegro_headers(),
        )

    if response.status_code != 200:

        return HTMLResponse(
            "Nie udało się pobrać zamówienia.",
            status_code=500,
        )

    order = response.json()

    line_items = (
        order.get("lineItems")
        or []
    )

    if (
        item_index < 0
        or item_index >= len(line_items)
    ):

        return HTMLResponse(
            "Nie znaleziono produktu.",
            status_code=404,
        )

    item = line_items[item_index]

    required_quantity = int(
        item.get("quantity") or 0
    )

    order_progress = (
        picking_progress.setdefault(
            order_id,
            {}
        )
    )

    current_quantity = int(
        order_progress.get(
            item_index,
            0
        )
    )

    if current_quantity < required_quantity:

        order_progress[item_index] = (
            current_quantity + 1
        )

    return RedirectResponse(
        url=f"/orders/{order_id}/picking",
        status_code=303,
    )
# Shopify NanoBanana Backend (POC)

Minimal FastAPI backend to verify you can **fetch the 5 POC products** you created in Shopify.

## What it does
- `GET /health`: health check
- `GET /products`: fetch products filtered by tag (default: `poc-ai-gen`)

## Setup

1) Create venv + install deps:

```bash
cd /home/techtic/Downloads/poc_automations/shopify-nanobanana-poc/backend
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

2) Create `.env`:

```bash
cp .env.example .env
```

3) Fill in Shopify values in `.env`:
- `SHOPIFY_STORE_DOMAIN` (example: `techticdemo.myshopify.com`)
- `SHOPIFY_ADMIN_ACCESS_TOKEN` (Admin API token)

4) Run the server:

```bash
source .venv/bin/activate
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload
```

## Test

Health:

```bash
curl -sS http://localhost:9000/health
```

Products (default tag filter):

```bash
curl -sS "http://localhost:9000/products"
```

Products (custom tag):

```bash
curl -sS "http://localhost:9000/products?tag=poc-ai-gen"
```


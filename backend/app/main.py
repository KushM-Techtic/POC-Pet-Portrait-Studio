from __future__ import annotations

import asyncio
import importlib
import mimetypes
import time
from pathlib import Path

import httpx  # type: ignore[import-not-found]
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .settings import settings
from .shopify_client import ShopifyClient
from .gemini_client import GeminiClient


app = FastAPI(title="Shopify NanoBanana Backend (POC)", version="0.1.0")

# Allow local dev frontend (Vite) to call this API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve generated outputs
out_dir = Path(settings.output_dir)
out_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(out_dir)), name="static")


def _client() -> ShopifyClient:
    return ShopifyClient(
        store_domain=settings.shopify_store_domain,
        api_version=settings.shopify_api_version,
        access_token=settings.shopify_admin_access_token,
    )


@app.get("/health")
def health():
    return {"ok": True, "env": settings.app_env}


@app.get("/products")
async def get_products(
    tag: str = Query(default=None, description="Shopify product tag to filter by (defaults to SHOPIFY_POC_TAG)"),
    first: int = Query(default=25, ge=1, le=250),
):
    tag = tag or settings.shopify_poc_tag
    metafield_keys = [k.strip() for k in settings.shopify_metafield_keys_csv.split(",") if k.strip()]
    try:
        products = await _client().fetch_products_by_tag(
            tag=tag,
            first=first,
            metafield_namespace=settings.shopify_metafield_namespace,
            metafield_keys=metafield_keys,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {"count": len(products), "tag": tag, "products": products}


def _get_prompt(*, has_style_image: bool) -> str:
    mod = importlib.import_module(settings.prompt_module)
    return mod.get_prompt(has_style_image=has_style_image)


async def _download(url: str) -> tuple[str, bytes]:
    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        r = await client.get(url)
        r.raise_for_status()
        content_type = r.headers.get("content-type") or ""
        mime = content_type.split(";")[0].strip() if content_type else ""
        if not mime:
            mime = mimetypes.guess_type(url)[0] or "application/octet-stream"
        return mime, r.content


async def _generate_for_product_id(product_id: str):
    if not settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="Missing GEMINI_API_KEY in environment")

    metafield_keys = [k.strip() for k in settings.shopify_metafield_keys_csv.split(",") if k.strip()]
    product_gid = product_id if product_id.startswith("gid://") else f"gid://shopify/Product/{product_id}"

    try:
        product = await _client().fetch_product_by_id(
            product_gid=product_gid,
            metafield_namespace=settings.shopify_metafield_namespace,
            metafield_keys=metafield_keys,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shopify fetch failed: {e}")

    mf = product.get("metafields") or {}
    pet_url = (mf.get("pet_image") or {}).get("url") if isinstance(mf.get("pet_image"), dict) else None
    template_url = (mf.get("template_image") or {}).get("url") if isinstance(mf.get("template_image"), dict) else None
    style_url = (mf.get("style_image") or {}).get("url") if isinstance(mf.get("style_image"), dict) else None

    if not pet_url or not template_url:
        raise HTTPException(status_code=400, detail="Missing pet_image or template_image URL in metafields")

    try:
        pet_mime, pet_bytes = await _download(pet_url)
        template_mime, template_bytes = await _download(template_url)
        images: list[tuple[str, bytes]] = [(template_mime, template_bytes), (pet_mime, pet_bytes)]
        if style_url:
            style_mime, style_bytes = await _download(style_url)
            images.append((style_mime, style_bytes))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Download failed: {e}")

    prompt = _get_prompt(has_style_image=bool(style_url))
    gemini = GeminiClient(
        api_key=settings.gemini_api_key,
        model=settings.gemini_image_model,
        fallback_model=settings.gemini_fallback_model,
        aspect_ratio=settings.gemini_aspect_ratio,
        max_retries=int(settings.gemini_max_retries),
        initial_backoff_s=float(settings.gemini_initial_backoff_s),
    )

    try:
        result = await gemini.edit_image(prompt=prompt, images=images)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gemini generate failed: {e}")

    ts = int(time.time())
    safe_handle = (product.get("handle") or "product").replace("/", "_")
    ext = ".png" if result.mime_type.endswith("png") else ".jpg"
    out_name = f"{safe_handle}_{ts}{ext}"
    out_path = out_dir / out_name
    out_path.write_bytes(result.image_bytes)

    return {
        "product": {"id": product.get("id"), "title": product.get("title"), "handle": product.get("handle")},
        "input_urls": {"pet_image": pet_url, "template_image": template_url, "style_image": style_url},
        "output": {"filename": out_name, "url": f"/static/{out_name}", "mime_type": result.mime_type},
        "model": settings.gemini_image_model,
    }


@app.post("/generate/{product_id}")
async def generate_for_product(product_id: str):
    """
    Generate final portrait for a Shopify product GID.
    Expects metafields to include URLs for:
    - pet_image
    - template_image
    - style_image (optional)
    """
    return await _generate_for_product_id(product_id)


@app.post("/generate-all")
async def generate_all(
    tag: str = Query(default=None, description="Shopify product tag to filter by (defaults to SHOPIFY_POC_TAG)"),
    first: int = Query(default=None, ge=1, le=250, description="How many products to process"),
):
    """
    Generate portraits for all products matching a tag.
    Returns per-product success/failure without failing the whole batch.
    """
    tag = tag or settings.shopify_poc_tag
    first = int(first or settings.generate_all_first)

    metafield_keys = [k.strip() for k in settings.shopify_metafield_keys_csv.split(",") if k.strip()]
    try:
        products = await _client().fetch_products_by_tag(
            tag=tag,
            first=first,
            metafield_namespace=settings.shopify_metafield_namespace,
            metafield_keys=metafield_keys,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shopify fetch failed: {e}")

    results: list[dict] = []
    delay_s = max(0.0, float(settings.generate_all_delay_ms) / 1000.0)
    for i, p in enumerate(products):
        pid = p.get("id") or ""
        title = p.get("title")
        handle = p.get("handle")
        numeric_id = str(pid).split("/")[-1] if isinstance(pid, str) else str(pid)
        try:
            payload = await _generate_for_product_id(numeric_id)
            results.append(
                {
                    "status": "ok",
                    "product": {"id": pid, "title": title, "handle": handle},
                    "output": payload.get("output"),
                }
            )
        except HTTPException as e:
            results.append(
                {
                    "status": "error",
                    "product": {"id": pid, "title": title, "handle": handle},
                    "error": str(e.detail),
                }
            )
        except Exception as e:
            results.append(
                {
                    "status": "error",
                    "product": {"id": pid, "title": title, "handle": handle},
                    "error": str(e),
                }
            )

        if delay_s and i < len(products) - 1:
            await asyncio.sleep(delay_s)

    return {"count": len(results), "tag": tag, "results": results}


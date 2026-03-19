from __future__ import annotations

from dataclasses import dataclass

from google import genai  # type: ignore[import-not-found]
from google.genai import types  # type: ignore[import-not-found]


@dataclass(frozen=True)
class GeminiImageResult:
    image_bytes: bytes
    mime_type: str


class GeminiClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        fallback_model: str | None = None,
        aspect_ratio: str | None = None,
        max_retries: int = 0,
        initial_backoff_s: float = 2.0,
    ) -> None:
        self._model = model
        self._fallback_model = fallback_model
        self._aspect_ratio = aspect_ratio
        self._max_retries = max_retries
        self._initial_backoff_s = initial_backoff_s
        # Use SDK client; key can come from env but we pass explicitly.
        self._client = genai.Client(api_key=api_key)

    async def edit_image(self, *, prompt: str, images: list[tuple[str, bytes]]) -> GeminiImageResult:
        """
        Uses Gemini NanoBanana image editing: text + one or more reference images -> image.
        images: list of (mime_type, bytes) tuples.
        """
        # Best practice for editing: provide image(s) and an explicit instruction.
        # Put images first (template, pet, optional style), then the instruction text.
        contents: list[types.Part | str] = []
        for mime, data in images:
            contents.append(types.Part.from_bytes(data=data, mime_type=mime))
        contents.append(prompt)

        # The SDK call is synchronous; run it off the event loop.
        import anyio
        import random
        import time

        def _call(model_name: str):
            cfg = types.GenerateContentConfig(response_modalities=["IMAGE"])
            if self._aspect_ratio:
                # Only supported by some models; harmless if ignored by SDK/backend.
                cfg = types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=self._aspect_ratio),
                )
            return self._client.models.generate_content(
                model=model_name,
                contents=contents,
                config=cfg,
            )

        def _is_retryable(err: Exception) -> bool:
            msg = str(err).lower()
            return ("429" in msg) or ("resource_exhausted" in msg) or ("rate" in msg and "limit" in msg) or ("503" in msg)

        # Retry with exponential backoff; optionally fall back to a lower-latency model.
        attempt = 0
        model_to_use = self._model
        last_err: Exception | None = None
        while True:
            try:
                response = await anyio.to_thread.run_sync(lambda: _call(model_to_use))
                break
            except Exception as e:
                last_err = e
                if attempt >= self._max_retries or not _is_retryable(e):
                    # Try fallback model once if configured and different.
                    if self._fallback_model and self._fallback_model != model_to_use:
                        model_to_use = self._fallback_model
                        attempt += 1
                        continue
                    raise
                # Backoff with jitter
                sleep_s = (self._initial_backoff_s * (2**attempt)) + random.uniform(0.0, 0.4)
                time.sleep(sleep_s)
                attempt += 1

        # Extract first returned image.
        for candidate in (response.candidates or []):
            content = candidate.content
            if not content or not content.parts:
                continue
            for part in content.parts:
                # SDK uses inline_data with bytes.
                if getattr(part, "inline_data", None) is not None:
                    blob = part.inline_data
                    data = getattr(blob, "data", None)
                    mime = getattr(blob, "mime_type", None) or "image/png"
                    if data:
                        return GeminiImageResult(image_bytes=data, mime_type=mime)

        raise RuntimeError("No image returned from Gemini SDK response") from last_err


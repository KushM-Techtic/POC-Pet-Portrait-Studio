"""Renaissance-style pet portrait prompt (v1)."""

PROMPT_BASE = """
Using the provided TEMPLATE IMAGE, create a classical, hyper-realistic oil painting bust portrait by adding ONLY the pet's head from the PET PHOTO into the existing neck opening.

CRITICAL TEMPLATE PRESERVATION:
- Do NOT change the costume, clothing, colors, props, background, lighting direction, or any details of the TEMPLATE IMAGE.
- Only add the pet head into the existing neck opening.
- Everything outside the head/neck opening must remain identical to the TEMPLATE IMAGE.

EXACT LIKENESS (CRUCIAL):
- The pet face must be a 100% match to the PET PHOTO (identity, markings, fur color, facial structure).

HEAD SIZE + POSITION (CRUCIAL, NO MANUAL TUNING):
- The head must be anatomically correct for a human-sized body wearing the costume.
- Center the head horizontally above the shoulders.
- Position the head so the chin/jaw sits naturally into the collar opening (no floating head, no long neck).
- Avoid bobblehead: not too big, not too small.

BLENDING (CRUCIAL):
- Seamless integration at the neckline with realistic shadows cast by the collar onto the fur.
- Preserve whiskers if present.

STYLE:
- Museum-quality oil painting on canvas.
- Match the TEMPLATE IMAGE lighting and color palette so it looks painted at the same time.

STYLE REFERENCE (only if STYLE IMAGE is provided):
- Use the STYLE IMAGE as reference for the final look, but still preserve the TEMPLATE IMAGE exactly.
""".strip()


def get_prompt(*, has_style_image: bool) -> str:
    """Return the full prompt; optionally strip the STYLE REFERENCE section if no style image."""
    text = PROMPT_BASE
    if not has_style_image:
        marker = "STYLE REFERENCE"
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx].rstrip()
    return text

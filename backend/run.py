from __future__ import annotations

import uvicorn


def main() -> None:
    # Settings are loaded from .env by app.settings via pydantic-settings.
    port = 8003
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)


if __name__ == "__main__":
    main()


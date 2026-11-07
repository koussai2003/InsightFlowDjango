"""Start the local app using the private DATABASE_URL saved in .env."""
import os
from pathlib import Path
import uvicorn

if __name__ == "__main__":
    settings = Path(__file__).with_name(".env")
    if settings.exists():
        for line in settings.read_text(encoding="utf-8-sig").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == "DATABASE_URL":
                os.environ["DATABASE_URL"] = value.strip().strip("\"").strip("'")
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("Set DATABASE_URL in .env before starting the app.")
    os.environ["INSIGHTFLOW_LOCAL_HTTP"] = "1"
    uvicorn.run("accounts:app", host="127.0.0.1", port=8018)

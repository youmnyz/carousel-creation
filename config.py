import os
from dotenv import load_dotenv

_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=_env_path, override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
WP_SITE_URL = os.getenv("WP_SITE_URL", "").rstrip("/")
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "./output")
BRAND_COLOR = os.getenv("BRAND_COLOR", "#4A90D9")
ACCENT_COLOR = os.getenv("ACCENT_COLOR", "#FFFFFF")

_here = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_FILE = os.getenv(
    "TEMPLATE_FILE",
    os.path.join(_here, "template.pptx")
)

def validate():
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not WP_SITE_URL:
        missing.append("WP_SITE_URL")
    if missing:
        raise EnvironmentError(
            f"Missing required config: {', '.join(missing)}\n"
            f"Copy .env.example to .env and fill in the values."
        )

def hex_to_rgb(hex_color: str) -> tuple:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

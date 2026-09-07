import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGODB_URI = os.getenv("MONGODB_URI", "")
DB_NAME = os.getenv("DB_NAME", "movie_bot")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
CHANNEL_URL = os.getenv("CHANNEL_URL", "")
PRIVATE_CHANNEL_ID = int(os.getenv("PRIVATE_CHANNEL_ID", "0"))
DELETE_AFTER = int(os.getenv("DELETE_AFTER", "300"))
TELEGRAPH_TOKEN = os.getenv("TELEGRAPH_TOKEN", "")
MAINTENANCE_MODE = os.getenv("MAINTENANCE_MODE", "false").lower() == "true"
BUILD_VERSION = os.getenv("BUILD_VERSION", "v2.0.0")

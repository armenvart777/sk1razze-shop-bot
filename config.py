import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_IDS: list[int] = field(default_factory=list)
    CHANNEL_USERNAME: str = os.getenv("CHANNEL_USERNAME", "")
    OFFER_URL: str = os.getenv("OFFER_URL", "")
    SUPPORT_URL: str = os.getenv("SUPPORT_URL", "")
    REVIEWS_URL: str = os.getenv("REVIEWS_URL", "")
    CRYPTO_BOT_TOKEN: str = os.getenv("CRYPTO_BOT_TOKEN", "")
    LOLZ_TOKEN: str = os.getenv("LOLZ_TOKEN", "")
    LOLZ_PROFILE: str = os.getenv("LOLZ_PROFILE", "")

    def __post_init__(self):
        raw = os.getenv("ADMIN_IDS", "")
        # Validate each entry is a valid integer before converting
        self.ADMIN_IDS = [int(x.strip()) for x in raw.split(",") if x.strip().isdigit()]
        if not self.BOT_TOKEN:
            raise ValueError("BOT_TOKEN must be set in environment")


settings = Settings()

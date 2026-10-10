"""Settings from .env / environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv

from .exceptions import ConfigError

DEFAULT_USER_AGENT = "AlgoryxCrawlerBot/1.0 (+internship project)"
DEFAULT_SEED_URL = "https://books.toscrape.com/"


def _load_env_file() -> None:
    for candidate in (Path.cwd() / ".env", Path(__file__).resolve().parent.parent / ".env"):
        if candidate.is_file():
            load_dotenv(candidate)
            return


def _get_int(env: Mapping[str, str], key: str, default: int, minimum: int) -> int:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ConfigError(f"{key} must be a whole number, got '{raw}'.") from None
    if value < minimum:
        raise ConfigError(f"{key} must be at least {minimum}, got {value}.")
    return value


def _get_float(env: Mapping[str, str], key: str, default: float, minimum: float) -> float:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw.strip())
    except ValueError:
        raise ConfigError(f"{key} must be a number, got '{raw}'.") from None
    if value < minimum:
        raise ConfigError(f"{key} must be at least {minimum}, got {value}.")
    return value


def _get_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    raw = env.get(key)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip().lower()
    if value in ("1", "true", "yes", "on"):
        return True
    if value in ("0", "false", "no", "off"):
        return False
    raise ConfigError(f"{key} must be true or false, got '{raw}'.")


@dataclass(frozen=True)
class Settings:
    """Runtime configuration. Build it with Settings.from_env()."""

    seed_urls: tuple[str, ...] = (DEFAULT_SEED_URL,)
    max_depth: int = 2
    max_pages: int = 50
    concurrency: int = 5
    delay_s: float = 0.2
    timeout_s: float = 15.0
    max_retries: int = 3
    retry_delay_s: float = 1.0
    respect_robots: bool = True
    user_agent: str = DEFAULT_USER_AGENT
    output_dir: Path = Path("output")
    log_file: Path = Path("logs") / "crawler.log"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        if env is None:
            _load_env_file()
            env = os.environ

        seeds_raw = env.get("SEED_URLS", "").strip()
        seeds = tuple(s.strip() for s in seeds_raw.split(",") if s.strip()) or (DEFAULT_SEED_URL,)
        for url in seeds:
            if not url.startswith(("http://", "https://")):
                raise ConfigError(f"SEED_URLS entry is not a valid URL: '{url}'")

        return cls(
            seed_urls=seeds,
            max_depth=_get_int(env, "MAX_DEPTH", 2, 0),
            max_pages=_get_int(env, "MAX_PAGES", 50, 1),
            concurrency=_get_int(env, "CONCURRENCY", 5, 1),
            delay_s=_get_float(env, "DELAY_S", 0.2, 0),
            timeout_s=_get_float(env, "TIMEOUT_S", 15.0, 1),
            max_retries=_get_int(env, "MAX_RETRIES", 3, 1),
            retry_delay_s=_get_float(env, "RETRY_DELAY_S", 1.0, 0),
            respect_robots=_get_bool(env, "RESPECT_ROBOTS", True),
            user_agent=(env.get("USER_AGENT") or DEFAULT_USER_AGENT).strip(),
            output_dir=Path(env.get("OUTPUT_DIR") or "output"),
            log_file=Path(env.get("LOG_FILE") or Path("logs") / "crawler.log"),
        )

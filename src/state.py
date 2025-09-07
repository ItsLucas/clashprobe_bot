import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


logger = logging.getLogger(__name__)


STATE_DIR = Path("data")
STATE_FILE = STATE_DIR / "state.json"


@dataclass
class MessageRef:
    chat_id: int
    message_id: int


def ensure_state_dir() -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error("Failed to create state dir %s: %s", STATE_DIR, e)


def save_message_ref(ref: MessageRef) -> None:
    ensure_state_dir()
    try:
        with STATE_FILE.open("w", encoding="utf-8") as f:
            json.dump({"chat_id": ref.chat_id, "message_id": ref.message_id}, f)
        logger.info("Persisted message ref to %s", STATE_FILE)
    except Exception as e:
        logger.error("Failed to persist message ref: %s", e)


def load_message_ref() -> Optional[MessageRef]:
    try:
        if not STATE_FILE.exists():
            return None
        with STATE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        chat_id = int(data.get("chat_id"))
        message_id = int(data.get("message_id"))
        return MessageRef(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        logger.warning("No valid state found at %s: %s", STATE_FILE, e)
        return None


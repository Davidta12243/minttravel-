from __future__ import annotations

import json
from pathlib import Path

MODERATION_FILE = Path("moderation_state.json")


def _default_state() -> dict:
    return {"hidden_articles": [], "review_states": {}}


def load_state() -> dict:
    if not MODERATION_FILE.exists():
        return _default_state()

    try:
        payload = json.loads(MODERATION_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return _default_state()

    state = _default_state()
    state["hidden_articles"] = payload.get("hidden_articles", [])
    state["review_states"] = payload.get("review_states", {})
    return state


def save_state(state: dict) -> None:
    MODERATION_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def is_article_hidden(article_id: int) -> bool:
    state = load_state()
    return str(article_id) in {str(item) for item in state["hidden_articles"]}


def set_article_hidden(article_id: int, hidden: bool) -> None:
    state = load_state()
    hidden_articles = {str(item) for item in state["hidden_articles"]}
    article_key = str(article_id)
    if hidden:
        hidden_articles.add(article_key)
    else:
        hidden_articles.discard(article_key)
    state["hidden_articles"] = sorted(hidden_articles, key=int)
    save_state(state)


def get_review_status(review_id: int) -> str:
    state = load_state()
    return state["review_states"].get(str(review_id), "approved")


def set_review_status(review_id: int, status: str) -> None:
    state = load_state()
    review_states = state["review_states"]
    review_states[str(review_id)] = status
    state["review_states"] = review_states
    save_state(state)

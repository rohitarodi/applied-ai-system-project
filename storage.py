"""Shared JSON load/save helpers.

Design choice (Ticket 1): this project uses a single tracked seed file,
data/library.json, as the one source of truth for the song library. There is
no separate "seed" vs "runtime" file — the sidebar's "Add to playlist"
handler saves straight back into data/library.json via save_json(). Simpler
setups (ratings.json, history.json, etc. added in later tickets) are
runtime-mutated and therefore .gitignore'd, while data/library.json and
data/samples/ stay tracked since they're the shipped default content.

Nothing here ever raises on a missing or malformed file — callers always get
a usable value back (the provided default), with a logged warning so the
condition is still visible.
"""

import copy
import json
import logging
import os

logger = logging.getLogger(__name__)


def load_json(path, default):
    """Load JSON from ``path``.

    Returns the parsed JSON on success. If the file is missing, unreadable,
    or contains malformed JSON, logs a warning and returns a deep copy of
    ``default`` instead of raising.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.warning("load_json: file not found at %s, using default", path)
        return copy.deepcopy(default)
    except json.JSONDecodeError:
        logger.warning("load_json: malformed JSON at %s, using default", path)
        return copy.deepcopy(default)
    except OSError as exc:
        logger.warning("load_json: could not read %s (%s), using default", path, exc)
        return copy.deepcopy(default)


def save_json(path, data):
    """Write ``data`` as JSON to ``path``, creating parent dirs as needed."""
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

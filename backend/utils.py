from __future__ import annotations

import uuid


def new_session_id() -> str:
    return uuid.uuid4().hex

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

DEFAULT_BUCKET = "inbox"


@dataclass
class Task:
    id: int
    title: str
    due: Optional[datetime]
    done: bool
    gcal_event_id: Optional[str]
    created_at: datetime
    bucket: str = DEFAULT_BUCKET
    notes: str = ""
    uid: str = ""  # stable id shared across machines (the integer id is local only)

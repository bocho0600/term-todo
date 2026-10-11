from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Task:
    id: int
    title: str
    due: Optional[datetime]
    done: bool
    gcal_event_id: Optional[str]
    created_at: datetime

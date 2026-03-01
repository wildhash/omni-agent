"""WebAgent.

Default behavior is simulated (offline-friendly) to keep unit tests deterministic
and avoid requiring a browser runtime.
"""

from __future__ import annotations

import uuid
from typing import Dict, Optional


class WebAgent:
    """Simulated web interactions.

    - scrape / browse: returns the input URL.
    - book flight: returns a simulated flight booking payload.
    """

    def __init__(self) -> None:
        self._session_id = uuid.uuid4().hex

    def execute(self, task: str, context: Optional[Dict] = None) -> Dict:
        context = context or {}
        task_lower = task.lower()

        if "scrape" in task_lower or "browse" in task_lower:
            return self._scrape(context.get("url", "https://example.com"))
        elif "flight" in task_lower or "book" in task_lower:
            return self._book_flight(context)
        else:
            return {"error": f"Web task not recognised: '{task}'"}

    def _scrape(self, url: str) -> Dict:
        """Simulate scrape by echoing the URL."""
        if not url:
            url = "https://example.com"
        return {"status": "simulated", "url": url}

    def _book_flight(self, context: Dict) -> Dict:
        """Simulate a flight booking."""
        from_airport = context.get("from", "SFO")
        to_airport = context.get("to", "NYC")
        date = context.get("date", "")

        flight = {
            "from": from_airport,
            "to": to_airport,
            "date": date,
            "booking_id": f"sim_{self._session_id}",
        }
        return {"status": "simulated", "flight": flight}

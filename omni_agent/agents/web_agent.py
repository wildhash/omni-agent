"""WebAgent: handles browser automation and web interactions."""

from typing import Any, Dict, Optional


class WebAgent:
    """Handles browser automation and web interactions.

    Methods
    -------
    execute(task, context):
        Route tasks to specific tools.
    """

    def __init__(self) -> None:
        self.tools = {
            "scrape": self._scrape,
            "book flight": self._book_flight,
        }

    def execute(self, task: str, context: Optional[Dict] = None) -> Dict:
        """Route *task* to the appropriate web tool.

        Parameters
        ----------
        task:
            Description of the web task.
        context:
            Optional parameters (e.g. URL, flight details).
        """
        context = context or {}
        task_lower = task.lower()

        if "scrape" in task_lower or "browse" in task_lower:
            return self._scrape(context.get("url", ""))
        elif "flight" in task_lower or "book" in task_lower:
            return self._book_flight(context)
        else:
            return {"error": f"Web task not recognised: '{task}'"}

    def _scrape(self, url: str) -> Dict:
        """Scrape webpage content at *url* (simulated).

        Parameters
        ----------
        url:
            Target URL.
        """
        return {
            "status": "simulated",
            "url": url,
            "content": f"<html>Simulated content for {url}</html>",
        }

    def _book_flight(self, context: Dict) -> Dict:
        """Simulate a flight booking.

        Parameters
        ----------
        context:
            Dictionary optionally containing 'from', 'to', and 'date'.
        """
        return {
            "status": "simulated",
            "flight": {
                "from": context.get("from", "SFO"),
                "to": context.get("to", "NYC"),
                "date": context.get("date", "2026-03-15"),
                "price": "$299",
                "booking_id": "FL123456789",
            },
        }

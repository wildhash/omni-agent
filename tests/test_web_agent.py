"""Tests for WebAgent."""

from omni_agent.agents.web_agent import WebAgent


def test_execute_scrape():
    agent = WebAgent()
    result = agent.execute("scrape", {"url": "https://example.com"})
    assert result["status"] == "simulated"
    assert result["url"] == "https://example.com"


def test_execute_book_flight():
    agent = WebAgent()
    result = agent.execute("book flight", {"from": "LAX", "to": "JFK", "date": "2026-04-01"})
    assert result["status"] == "simulated"
    flight = result["flight"]
    assert flight["from"] == "LAX"
    assert flight["to"] == "JFK"
    assert flight["date"] == "2026-04-01"
    assert "booking_id" in flight


def test_execute_book_flight_defaults():
    agent = WebAgent()
    result = agent.execute("book flight", {})
    flight = result["flight"]
    assert flight["from"] == "SFO"
    assert flight["to"] == "NYC"


def test_execute_unknown_task():
    agent = WebAgent()
    result = agent.execute("dance")
    assert "error" in result

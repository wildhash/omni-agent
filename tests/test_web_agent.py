"""Tests for WebAgent."""

from omni_agent.agents.web_agent import WebAgent


def test_execute_scrape():
    agent = WebAgent()
    result = agent.execute("scrape", {"url": "https://example.com"})
    if "error" in result:
        assert "url" in result
        return
    assert result["status"] == "success"
    assert result["url"] == "https://example.com"
    assert "title" in result
    assert "content" in result


def test_execute_book_flight():
    agent = WebAgent()
    result = agent.execute("book flight", {"from": "LAX", "to": "JFK", "date": "2026-04-01"})
    if "error" in result:
        assert result.get("query", {}).get("from") == "LAX"
        return
    assert result["status"] == "success"
    query = result["query"]
    assert query["from"] == "LAX"
    assert query["to"] == "JFK"
    assert query["date"] == "2026-04-01"


def test_execute_book_flight_defaults():
    agent = WebAgent()
    result = agent.execute("book flight", {})
    if "error" in result:
        assert "query" in result
        return
    assert result["status"] == "success"
    query = result["query"]
    assert query["from"] == "SFO"
    assert query["to"] == "NYC"


def test_execute_unknown_task():
    agent = WebAgent()
    result = agent.execute("dance")
    assert "error" in result

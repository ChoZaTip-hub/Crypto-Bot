"""Sentiment scoring tests."""

from app.services.sentiment_service import SentimentService


def test_score_hack_negative() -> None:
    svc = SentimentService.__new__(SentimentService)
    score, conf, label, high_impact, tags = svc.score_text(
        "Major exchange hack drains $100M from protocol"
    )
    assert score <= 0
    assert high_impact
    assert "hack" in tags


def test_score_positive() -> None:
    svc = SentimentService.__new__(SentimentService)
    score, conf, label, high_impact, tags = svc.score_text("Bitcoin rally adoption surge bullish")
    assert score >= 0

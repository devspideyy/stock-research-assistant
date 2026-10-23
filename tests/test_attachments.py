import json

import pytest

from app.attachments import load_evidence_json


def test_import_dated_news_without_fetching_links():
    result = load_evidence_json(
        json.dumps(
            {
                "news": [
                    {
                        "title": "User-owned research note",
                        "published_at": "2026-10-22T12:00:00+05:30",
                        "source": "Researcher's note",
                        "url": "https://example.com/source",
                        "summary": "Evidence supplied by the user.",
                    }
                ]
            }
        )
    )
    assert len(result["news"]) == 1
    assert not result["depth"]


@pytest.mark.parametrize(
    "data",
    [
        {"news": [{"title": "No timestamp", "source": "Unknown"}]},
        {
            "news": [
                {
                    "title": "Bad link",
                    "source": "Test",
                    "published_at": "2026-01-01",
                    "url": "javascript:bad",
                }
            ]
        },
        {"fundamentals": {"revenue_growth": 10}},
        {"depth": {"bids": [], "asks": []}},
    ],
)
def test_missing_provenance_or_unsafe_format_is_rejected(data):
    with pytest.raises((ValueError, KeyError)):
        load_evidence_json(json.dumps(data))

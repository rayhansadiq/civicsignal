"""
API tests against a seeded SQLite database.

Seeded data (7 scored + 1 unscored):
  oakland  90 renewal        | oakland  75 new_initiative
  oakland  65 expansion      | seattle  55 expansion
  seattle  55 new_initiative | seattle   0 low_signal
  seattle  10 low_signal     | oakland  (unscored)
"""

import pytest


class TestHealth:
    def test_returns_ok(self, client):
        res = client.get("/health")
        assert res.status_code == 200
        assert res.json() == {"status": "ok"}

    def test_does_not_touch_the_database(self, client, monkeypatch):
        """
        /health must answer even when the database is unreachable. Neon's free
        tier sleeps after 5 minutes idle, and a health check that queries
        Postgres would report the service as down and get it restarted while
        it is in fact fine.
        """
        import db as dbmod

        def explode():
            raise RuntimeError("database is asleep")

        monkeypatch.setattr(dbmod, "SessionLocal", explode)
        assert client.get("/health").status_code == 200


class TestStats:
    def test_counts_only_scored_records(self, client):
        # 8 rows exist; one has no signal and must not be counted.
        assert client.get("/api/stats").json() == {
            "total_scored": 7,
            "high_signal_count": 2,
        }


class TestClients:
    def test_returns_distinct_sorted_cities(self, client):
        assert client.get("/api/clients").json() == {"clients": ["oakland", "seattle"]}


class TestSignals:
    def test_excludes_unscored_records(self, client):
        assert client.get("/api/signals").json()["count"] == 7

    def test_sorted_by_score_descending(self, client):
        scores = [r["signal_score"] for r in client.get("/api/signals").json()["results"]]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 90

    @pytest.mark.parametrize(
        "category,expected",
        [("renewal", 1), ("new_initiative", 2), ("expansion", 2), ("low_signal", 2)],
    )
    def test_category_filter(self, client, category, expected):
        assert client.get(f"/api/signals?category={category}").json()["count"] == expected

    def test_category_counts_sum_to_total(self, client):
        total = sum(
            client.get(f"/api/signals?category={c}").json()["count"]
            for c in ["renewal", "new_initiative", "expansion", "low_signal"]
        )
        # If this drifts, a filter is dropping or double-counting rows, which
        # looks completely fine on screen.
        assert total == client.get("/api/signals").json()["count"]

    @pytest.mark.parametrize(
        "min_score,expected", [(0, 7), (10, 6), (55, 5), (70, 2), (91, 0)]
    )
    def test_min_score_filter(self, client, min_score, expected):
        assert client.get(f"/api/signals?min_score={min_score}").json()["count"] == expected

    def test_client_filter(self, client):
        assert client.get("/api/signals?client=oakland").json()["count"] == 3
        assert client.get("/api/signals?client=seattle").json()["count"] == 4

    def test_unknown_client_returns_empty_not_error(self, client):
        res = client.get("/api/signals?client=atlantis")
        assert res.status_code == 200
        assert res.json()["count"] == 0

    def test_search_matches_title(self, client):
        assert client.get("/api/signals?q=NEOGOV").json()["count"] == 1

    def test_search_matches_matter_file(self, client):
        assert client.get("/api/signals?q=Inf 2937").json()["count"] == 1

    def test_search_is_case_insensitive(self, client):
        assert client.get("/api/signals?q=neogov").json()["count"] == 1

    def test_filters_combine(self, client):
        res = client.get("/api/signals?client=seattle&category=expansion")
        assert res.json()["count"] == 1

    def test_limit_caps_results(self, client):
        assert client.get("/api/signals?limit=3").json()["count"] == 3

    def test_limit_above_maximum_is_rejected(self, client):
        # The API caps limit at 200. Silently clamping would hide the fact
        # that a caller is asking for more data than it can get.
        assert client.get("/api/signals?limit=500").status_code == 422

    @pytest.mark.parametrize("bad", [-1, 101])
    def test_out_of_range_min_score_is_rejected(self, client, bad):
        assert client.get(f"/api/signals?min_score={bad}").status_code == 422

    def test_response_shape(self, client):
        row = client.get("/api/signals?limit=1").json()["results"][0]
        assert set(row) == {
            "id", "source_client", "matter_file", "matter_name", "matter_title",
            "matter_type", "matter_status", "matter_body", "intro_date",
            "agenda_date", "signal_score", "signal_category", "signal_summary",
        }


class TestSingleSignal:
    def test_returns_the_record(self, client):
        first = client.get("/api/signals?limit=1").json()["results"][0]
        assert client.get(f"/api/signals/{first['id']}").json()["id"] == first["id"]

    def test_missing_id_returns_404(self, client):
        # Not a 200 with an error body. Clients branch on status codes, and
        # an endpoint that answers 200 for a missing record forces every
        # caller to inspect the payload to find out whether it worked.
        res = client.get("/api/signals/999999")
        assert res.status_code == 404
        assert res.json() == {"detail": "Signal not found"}

    def test_non_numeric_id_is_rejected(self, client):
        assert client.get("/api/signals/not-a-number").status_code == 422


class TestCors:
    """
    Vercel gives every deployment and preview branch its own hostname, so the
    API matches them by regex. The pattern is anchored at both ends; these
    tests exist to keep it that way.
    """

    @pytest.mark.parametrize(
        "origin",
        [
            "http://localhost:3000",
            "https://example.com",
            "https://civicsignal.vercel.app",
            "https://civicsignal-coral.vercel.app",
            "https://civicsignal-git-main-rayhansadiq1.vercel.app",
            "https://civicsignal-eu0mhyai6-rayhansadiq1.vercel.app",
        ],
    )
    def test_allowed_origins(self, client, origin):
        res = client.get("/health", headers={"Origin": origin})
        assert res.headers.get("access-control-allow-origin") == origin

    @pytest.mark.parametrize(
        "origin",
        [
            "https://evil.example.com",
            "http://civicsignal-coral.vercel.app",            # http, not https
            "https://civicsignal-coral.vercel.app.evil.com",  # suffix attack
            "https://evil.com/?x=civicsignal-a.vercel.app",   # unanchored-prefix attack
            "https://notcivicsignal.vercel.app",              # different project
            "https://civicsignal-coral.vercel.app.co",        # lookalike TLD
        ],
    )
    def test_blocked_origins(self, client, origin):
        res = client.get("/health", headers={"Origin": origin})
        assert res.headers.get("access-control-allow-origin") is None

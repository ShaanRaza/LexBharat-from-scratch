"""Judgment view, Act lookup (public), stats (public), search."""

from datetime import date

from api_fakes import d

from api.pipeline import SearchHit

CC_BY = "Data: Open India Law by Vaquill AI, CC BY 4.0"


def seed_coverage(env, stats_live=True):
    env.store.coverage.append(
        {
            "court": "Supreme Court of India",
            "snapshot_version": "v2026.08",
            "data_as_of": d(2026, 8, 15),
            "stats_live": stats_live,
        }
    )


def test_case_view_has_anchors_citation_label_and_notices(env):
    seed_coverage(env)
    env.store.add_case(
        record_id="1959_INSC_62",
        title="A v. B",
        citation="[1959] SUPP. 2 S.C.R. 986",
        decision_date=date(1959, 5, 5),
        disposition="Appeal(s) allowed",
        outcome_label="allowed",
        pdf_url="https://example/p.pdf",
        full_text="First para.\n\nSecond para.\n\n\n\nThird.",
    )
    r = env.client.get("/api/v1/cases/1959_INSC_62", headers=env.auth())
    assert r.status_code == 200
    body = r.json()
    assert [p["anchor"] for p in body["paragraphs"]] == ["p1", "p2", "p3"]
    assert body["citation"] == "[1959] SUPP. 2 S.C.R. 986"  # exactly as stored
    assert body["citation_label"] == "as recorded in the dataset"
    assert body["pdf_url"] == "https://example/p.pdf"
    assert body["provenance"]["data_as_of"] == "2026-08-15"
    assert body["provenance"]["credit"] == CC_BY
    assert (
        body["provenance"]["notice"] == "TestBuddy gives information, not legal advice"
    )


def test_case_view_never_exposes_judges_or_party_names(env):
    env.store.add_case(
        record_id="c1", court="Supreme Court of India", full_text="x",
        judges="SECRET JUDGE", petitioner="SECRET PARTY",
    )  # fmt: skip
    r = env.client.get("/api/v1/cases/c1", headers=env.auth())
    assert "SECRET" not in r.text
    for banned in ("judges", "petitioner", "respondent"):
        assert banned not in r.json()


def test_case_without_citation_has_no_label(env):
    env.store.add_case(record_id="c2", court="X", full_text="t")
    assert (
        env.client.get("/api/v1/cases/c2", headers=env.auth()).json()["citation_label"]
        is None
    )


def test_case_not_found(client, env):
    r = client.get("/api/v1/cases/missing", headers=env.auth())
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"


def test_act_section_without_act_status_is_labelled_not_checked(env):
    env.store.add_act(
        record_id="ipc-302", act_name="The Indian Penal Code, 1860", act_year=1860,
        section_number="302", section_title="Punishment for murder", text="Whoever...",
        in_force=True,
    )  # fmt: skip
    r = env.client.get("/api/v1/acts/the-indian-penal-code-1860/sections/302")
    assert r.status_code == 200  # public: no login header sent
    body = r.json()
    assert body["status"] == {
        "checked": False,
        "act_status": None,
        "in_force": None,
        "label": "in-force status not checked",
    }
    assert body["provenance"]["credit"] == CC_BY
    assert "not legal advice" in body["provenance"]["notice"]


def test_act_section_shows_status_only_when_act_status_is_filled(env):
    env.store.add_act(
        record_id="bsa-130", act_name="The Bharatiya Sakshya Adhiniyam, 2023",
        act_year=2023, section_number="130", act_status="in_force", in_force=True,
    )  # fmt: skip
    body = env.client.get(
        "/api/v1/acts/the-bharatiya-sakshya-adhiniyam-2023/sections/130"
    ).json()
    assert body["status"]["checked"] is True
    assert body["status"]["act_status"] == "in_force"


def test_act_lookup_accepts_slug_variants_and_letter_sections(env):
    env.store.add_act(
        record_id="x", act_name="The Indian Penal Code, 1860", act_year=1860,
        section_number="498A",
    )  # fmt: skip
    for slug in (
        "indian-penal-code",
        "indian-penal-code-1860",
        "the-indian-penal-code",
    ):
        r = env.client.get(f"/api/v1/acts/{slug}/sections/498a")
        assert r.status_code == 200, slug


def test_act_section_not_found(client):
    r = client.get("/api/v1/acts/no-such-act/sections/1")
    assert r.status_code == 404


def test_act_page_uses_data_as_of_from_coverage(env):
    seed_coverage(env)
    env.store.add_act(record_id="y", act_name="Z Act", section_number="1")
    body = env.client.get("/api/v1/acts/z-act/sections/1").json()
    assert body["provenance"]["data_as_of"] == "2026-08-15"


def test_data_as_of_falls_back_to_config(env):
    env.store.add_act(record_id="y", act_name="Z Act", section_number="1")
    body = env.client.get("/api/v1/acts/z-act/sections/1").json()
    assert body["provenance"]["data_as_of"] == "2026-08-01"


def _seed_stats(env):
    seed_coverage(env)
    for i, (label, final, yr) in enumerate(
        [
            ("allowed", True, 2020), ("allowed", True, 2020), ("dismissed", True, 2020),
            ("dismissed", True, 2021), ("allowed", False, 2020),  # not final: not counted
        ]
    ):  # fmt: skip
        env.store.add_case(
            record_id=f"s{i}", outcome_label=label, is_final_outcome=final,
            decision_date=date(yr, 3, 1),
        )  # fmt: skip


def test_stats_is_off_until_the_switch_is_on(env):
    _seed_stats(env)
    r = env.client.get("/api/v1/stats")  # public: no login
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "stats_not_live"


def test_stats_off_if_this_court_is_not_marked_live(env):
    env.set_settings(FEATURE_STATS_LIVE=True)
    seed_coverage(env, stats_live=False)
    assert env.client.get("/api/v1/stats").status_code == 404


def test_stats_counts_are_descriptive_and_carry_notices(env):
    env.set_settings(FEATURE_STATS_LIVE=True)
    _seed_stats(env)
    r = env.client.get("/api/v1/stats")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 4
    assert {"year": 2020, "outcome_label": "allowed", "count": 2} in body["rows"]
    assert body["provenance"]["credit"] == CC_BY
    assert body["provenance"]["data_as_of"] == "2026-08-15"
    assert "predict" not in body["description"].lower()

    only_2021 = env.client.get("/api/v1/stats?year=2021").json()
    assert only_2021["total"] == 1


def test_stats_rejects_silly_year(env):
    env.set_settings(FEATURE_STATS_LIVE=True)
    assert env.client.get("/api/v1/stats?year=12").status_code == 422


def test_search_goes_through_the_pipeline_with_filters(env):
    env.pipeline.hits = [SearchHit(record_id="r1", title="T", snippet="s", url="u")]
    r = env.client.get("/api/v1/search?q=bail&year=2020&limit=3", headers=env.auth())
    assert r.status_code == 200
    assert r.json()["items"][0]["record_id"] == "r1"
    assert r.json()["provenance"]["credit"] == CC_BY
    assert env.pipeline.calls[0]["filters"] == {"court": None, "year": 2020}


def test_search_when_pipeline_not_wired_is_503(env):
    from api.deps import UnavailablePipeline

    env.app.state.pipeline = UnavailablePipeline()
    r = env.client.get("/api/v1/search?q=bail", headers=env.auth())
    assert r.status_code == 503
    assert r.json()["error"]["code"] == "pipeline_unavailable"

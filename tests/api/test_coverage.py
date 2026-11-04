"""GET /coverage: public, and every word comes from the one coverage source."""

from core import coverage


def test_coverage_is_public_and_reads_the_source(client):
    r = client.get("/api/v1/coverage")  # no login
    assert r.status_code == 200
    body = r.json()
    cov = coverage.load_coverage()
    assert body["status"] == cov.status == "measured"
    assert body["sentence_approved"] is False  # the owner approves the wording
    assert body["sentence"] == coverage.coverage_sentence("LexBharat")
    assert [c["label"] for c in body["courts"]] == [c.covered_label for c in cov.courts]
    assert [i["label"] for i in body["instruments"]] == [
        i.covered_label for i in cov.instruments
    ]
    assert body["excluded"] == list(cov.excluded)
    assert body["not_in_dataset_message"] == cov.not_in_dataset_message
    p = body["provenance"]  # date, credit and notice travel with it
    assert p["data_as_of"] and p["credit"].startswith("Data: Open India Law")


def test_coverage_names_nothing_the_source_does_not_name(client):
    body = client.get("/api/v1/coverage").json()
    cov = coverage.load_coverage()
    shown = {c["label"] for c in body["courts"]} | {
        i["label"] for i in body["instruments"]
    }
    assert shown == set(cov.covered_labels_each())
    # what is excluded is listed as excluded and appears in no covered label
    assert not any(e.lower() in label.lower() for e in cov.excluded for label in shown)

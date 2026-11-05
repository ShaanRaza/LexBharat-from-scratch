"""core/act_ids.json describes research_v3 (A191): the eight replaced Acts under their IND_SUPP_* ids, the Constitution added.

The offline tests read the checked-in file. The live test needs the copy instance (port 7333, read only) and is skipped
when it is not up: it checks that "section 11 CPC" resolves to a record that exists in research_v3.
"""

import json
import urllib.request

import pytest

from core.act_ids import resolve_act

REPLACED = {
    "The Indian Stamp Act, 1899": "IND_SUPP_stamp1899",
    "The Prevention of Corruption Act, 1988": "IND_SUPP_pca1988",
    "The Hindu Marriage Act, 1955": "IND_SUPP_hma1955",
    "The Limitation Act, 1963": "IND_SUPP_limitation1963",
    "The Specific Relief Act, 1963": "IND_SUPP_sra1963",
    "The Indian Contract Act, 1872": "IND_SUPP_contract1872",
    "The Negotiable Instruments Act, 1881": "IND_SUPP_nia1881",
    "The Code of Civil Procedure, 1908": "IND_SUPP_cpc1908",
}


def test_the_checked_in_file_names_research_v3():
    from core.act_ids import PATH

    d = json.loads(PATH.read_text())
    assert d["collection"] == "research_v3" and len(d["acts"]) == 1569
    ids = {a[0] for a in d["acts"]}
    assert set(REPLACED.values()) <= ids and "IND_SUPP_constitution" in ids
    # the old ids of the replaced Acts are gone: nothing resolves to a point research_v3 does not hold
    assert not {"IND_central_2191", "IND_central_1565", "IND_central_2187"} & ids


@pytest.mark.parametrize("name,act_id", sorted(REPLACED.items()))
def test_each_replaced_act_resolves_to_its_supplement_id(name, act_id):
    assert resolve_act(name) == (act_id,)


def test_section_11_cpc_resolves_to_the_supplement_act():
    assert resolve_act("CPC") == ("IND_SUPP_cpc1908",)
    assert resolve_act("Constitution of India") == ("IND_SUPP_constitution",)


def _live() -> bool:
    try:
        urllib.request.urlopen(
            "http://127.0.0.1:7333/collections/research_v3", timeout=2
        )  # noqa: S310
        return True
    except OSError:
        return False


@pytest.mark.skipif(not _live(), reason="the copy instance on port 7333 is not up")
def test_section_11_cpc_is_a_record_that_exists_in_research_v3():
    (act_id,) = resolve_act("CPC")
    body = {
        "limit": 5,
        "with_payload": ["text", "heading_section"],
        "with_vector": False,
        "filter": {
            "must": [
                {"key": "act_id", "match": {"value": act_id}},
                {"key": "heading_section", "match": {"value": "11"}},
            ]
        },
    }
    req = urllib.request.Request(  # noqa: S310
        "http://127.0.0.1:7333/collections/research_v3/points/scroll",
        json.dumps(body).encode(),
        {"content-type": "application/json"},
    )
    pts = json.load(urllib.request.urlopen(req, timeout=30))["result"]["points"]  # noqa: S310
    assert pts, "no chunk of the Code of Civil Procedure is headed by section 11"
    assert any("res judicata" in p["payload"]["text"].lower() for p in pts)

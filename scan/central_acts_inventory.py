"""Inventory of the Union-level Acts the corpus actually holds (DATA-GAPS section 20). Read-only; no embeddings, no model calls, no spend.

Plain words: nobody had listed which Union-level Acts are in the data; CrPC 1973 was found missing by accident (nine lookups
returned nothing). This lists every Union-level Act in three places and checks a list of the most-practised statutes against
all three, so a missing Act is classed as an ACQUISITION problem (not in the source files) or an INDEXING problem (in the
source, not in what is served).

  SOURCE   the central legislation parquet on the SSD (`in_central_legislation.parquet`)
  ORIGINAL `acts_india` (originals, port 6333), points whose `jurisdiction` is central; read-only
  SERVED   `kanoon_v1` (the copy instance, port 7333, the collection the product is configured to serve), same filter

  python -m scan.central_acts_inventory         # writes <home>/inventory.json and <home>/INVENTORY.md
"""

from __future__ import annotations

import collections
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
HOME = Path.home() / "qdrant-kanoon" / "central_acts"
PARQUET = Path("/Volumes/LAWSSD/open-india-law/in_central_legislation.parquet")
ORIG, COPY = "http://localhost:6333", "http://127.0.0.1:7333"
HARD_STOP_S = 60
PAUSE_S = 0.25
FIELDS = ["act_id", "title", "year", "act_status", "is_repealed"]


def _read(base: str, collection: str, body: dict) -> dict:
    """A scroll of one collection: the only kind of request this script makes. One at a time, a pause, a hard stop."""
    req = urllib.request.Request(  # noqa: S310 - a fixed loopback http base
        f"{base}/collections/{collection}/points/scroll",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        raw = urllib.request.urlopen(req, timeout=HARD_STOP_S).read()  # noqa: S310
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"HARD STOP: {exc}. No retry.")
    time.sleep(PAUSE_S)
    return json.loads(raw)["result"]


def scan_qdrant(base: str, collection: str) -> dict[str, dict]:
    """act_id -> {title, year, status, points} for every central point."""
    acts: dict[str, dict] = {}
    off = None
    while True:
        body = {
            "limit": 2000,
            "filter": {
                "must": [{"key": "jurisdiction", "match": {"value": "central"}}]
            },
            "with_payload": FIELDS,
            "with_vector": False,
        }
        if off is not None:
            body["offset"] = off
        res = _read(base, collection, body)
        for p in res["points"]:
            pl = p["payload"]
            a = acts.setdefault(
                pl["act_id"],
                {
                    "title": pl.get("title"),
                    "year": str(pl.get("year")),
                    "status": pl.get("act_status"),
                    "points": 0,
                },
            )
            a["points"] += 1
        off = res.get("next_page_offset")
        if off is None:
            return acts


def scan_parquet() -> dict[str, dict]:
    import pyarrow.parquet as pq

    t = pq.read_table(PARQUET, columns=["act_id", "title", "year", "act_status"])
    acts: dict[str, dict] = {}
    for aid, title, year, status in zip(
        t["act_id"].to_pylist(),
        t["title"].to_pylist(),
        t["year"].to_pylist(),
        t["act_status"].to_pylist(),
    ):
        a = acts.setdefault(
            aid, {"title": title, "year": str(year), "status": status, "points": 0}
        )
        a["points"] += 1
    return acts


def norm(title: str | None) -> str:
    t = (title or "").lower()
    t = re.sub(r"\(rep[^)]*\)", " ", t)  # "(Rep., Act 45 of 2023)"
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# (name, regex on the normalised title, year). The year is checked against the Act's own `year` field. An Act is "found"
# when a title matches AND the year agrees. The CrPC is Act 2 of 1974, so its year is accepted as 1973 or 1974.
CHECKLIST: list[tuple[str, str, tuple[int, ...]]] = [
    ("Indian Penal Code, 1860", r"indian penal code", (1860,)),
    (
        "Code of Criminal Procedure, 1973",
        r"code of criminal procedure|criminal procedure code",
        (1973, 1974),
    ),
    ("Code of Civil Procedure, 1908", r"code of civil procedure", (1908,)),
    ("Indian Evidence Act, 1872", r"indian evidence act", (1872,)),
    ("Bharatiya Nyaya Sanhita, 2023", r"bharatiya nyaya sanhita", (2023,)),
    (
        "Bharatiya Nagarik Suraksha Sanhita, 2023",
        r"bharatiya nagarik suraksha sanhita",
        (2023,),
    ),
    ("Bharatiya Sakshya Adhiniyam, 2023", r"bharatiya sakshya adhiniyam", (2023,)),
    ("Constitution of India", r"constitution of india", (1949, 1950)),
    ("Indian Contract Act, 1872", r"indian contract act", (1872,)),
    ("Sale of Goods Act, 1930", r"sale of goods act", (1930,)),
    ("Indian Partnership Act, 1932", r"indian partnership act", (1932,)),
    (
        "Limited Liability Partnership Act, 2008",
        r"limited liability partnership act",
        (2008,),
    ),
    ("Companies Act, 2013", r"companies act", (2013,)),
    ("Companies Act, 1956", r"companies act", (1956,)),
    (
        "Arbitration and Conciliation Act, 1996",
        r"arbitration and conciliation act",
        (1996,),
    ),
    ("Negotiable Instruments Act, 1881", r"negotiable instruments act", (1881,)),
    ("Limitation Act, 1963", r"limitation act", (1963,)),
    ("Specific Relief Act, 1963", r"specific relief act", (1963,)),
    ("Transfer of Property Act, 1882", r"transfer of property act", (1882,)),
    ("Registration Act, 1908", r"registration act", (1908,)),
    ("Indian Stamp Act, 1899", r"indian stamp act", (1899,)),
    ("Indian Easements Act, 1882", r"indian easements act", (1882,)),
    ("Indian Trusts Act, 1882", r"indian trusts act", (1882,)),
    (
        "Insolvency and Bankruptcy Code, 2016",
        r"insolvency and bankruptcy code",
        (2016,),
    ),
    (
        "SARFAESI Act, 2002",
        r"securitisation and reconstruction of financial assets",
        (2002,),
    ),
    ("Recovery of Debts and Bankruptcy Act, 1993", r"recovery of debts", (1993,)),
    ("Competition Act, 2002", r"competition act", (2002,)),
    ("Information Technology Act, 2000", r"information technology act", (2000,)),
    ("Copyright Act, 1957", r"copyright act", (1957,)),
    ("Patents Act, 1970", r"patents act", (1970,)),
    ("Trade Marks Act, 1999", r"trade marks act", (1999,)),
    ("Consumer Protection Act, 2019", r"consumer protection act", (2019,)),
    ("Consumer Protection Act, 1986", r"consumer protection act", (1986,)),
    (
        "Real Estate (Regulation and Development) Act, 2016",
        r"real estate regulation and development act",
        (2016,),
    ),
    ("Right to Information Act, 2005", r"right to information act", (2005,)),
    (
        "Foreign Exchange Management Act, 1999",
        r"foreign exchange management act",
        (1999,),
    ),
    (
        "Prevention of Money-laundering Act, 2002",
        r"prevention of money laundering act",
        (2002,),
    ),
    ("Prevention of Corruption Act, 1988", r"prevention of corruption act", (1988,)),
    (
        "Narcotic Drugs and Psychotropic Substances Act, 1985",
        r"narcotic drugs and psychotropic substances act",
        (1985,),
    ),
    ("Arms Act, 1959", r"arms act", (1959,)),
    ("Motor Vehicles Act, 1988", r"motor vehicles act", (1988,)),
    (
        "Protection of Children from Sexual Offences Act, 2012",
        r"protection of children from sexual offences act",
        (2012,),
    ),
    (
        "Protection of Women from Domestic Violence Act, 2005",
        r"protection of women from domestic violence act",
        (2005,),
    ),
    ("Dowry Prohibition Act, 1961", r"dowry prohibition act", (1961,)),
    (
        "Juvenile Justice (Care and Protection of Children) Act, 2015",
        r"juvenile justice",
        (2015,),
    ),
    (
        "SC and ST (Prevention of Atrocities) Act, 1989",
        r"scheduled castes and the scheduled tribes prevention of atrocities act",
        (1989,),
    ),
    ("Indian Succession Act, 1925", r"indian succession act", (1925,)),
    ("Hindu Marriage Act, 1955", r"hindu marriage act", (1955,)),
    ("Hindu Succession Act, 1956", r"hindu succession act", (1956,)),
    (
        "Hindu Minority and Guardianship Act, 1956",
        r"hindu minority and guardianship act",
        (1956,),
    ),
    (
        "Hindu Adoptions and Maintenance Act, 1956",
        r"hindu adoptions and maintenance act",
        (1956,),
    ),
    (
        "Muslim Personal Law (Shariat) Application Act, 1937",
        r"muslim personal law",
        (1937,),
    ),
    (
        "Dissolution of Muslim Marriages Act, 1939",
        r"dissolution of muslim marriages act",
        (1939,),
    ),
    (
        "Muslim Women (Protection of Rights on Divorce) Act, 1986",
        r"muslim women protection of rights on divorce act",
        (1986,),
    ),
    ("Special Marriage Act, 1954", r"special marriage act", (1954,)),
    ("Guardians and Wards Act, 1890", r"guardians and wards act", (1890,)),
    ("Indian Christian Marriage Act, 1872", r"indian christian marriage act", (1872,)),
    (
        "Parsi Marriage and Divorce Act, 1936",
        r"parsi marriage and divorce act",
        (1936,),
    ),
    ("Family Courts Act, 1984", r"family courts act", (1984,)),
    ("Income-tax Act, 1961", r"income tax act", (1961,)),
    (
        "Central Goods and Services Tax Act, 2017",
        r"central goods and services tax act",
        (2017,),
    ),
    (
        "Integrated Goods and Services Tax Act, 2017",
        r"integrated goods and services tax act",
        (2017,),
    ),
    ("Customs Act, 1962", r"customs act", (1962,)),
    ("Central Excise Act, 1944", r"central excise act", (1944,)),
    ("Code on Wages, 2019", r"code on wages", (2019,)),
    ("Industrial Relations Code, 2020", r"industrial relations code", (2020,)),
    ("Code on Social Security, 2020", r"code on social security", (2020,)),
    (
        "Occupational Safety, Health and Working Conditions Code, 2020",
        r"occupational safety health and working conditions code",
        (2020,),
    ),
    ("Industrial Disputes Act, 1947", r"industrial disputes act", (1947,)),
    ("Factories Act, 1948", r"factories act", (1948,)),
    ("Payment of Gratuity Act, 1972", r"payment of gratuity act", (1972,)),
    (
        "Employees' Provident Funds and Miscellaneous Provisions Act, 1952",
        r"employees provident funds and miscellaneous provisions act",
        (1952,),
    ),
    ("Minimum Wages Act, 1948", r"minimum wages act", (1948,)),
    ("Payment of Wages Act, 1936", r"payment of wages act", (1936,)),
    (
        "Employees' Compensation Act, 1923",
        r"employees compensation act|workmen s compensation act",
        (1923,),
    ),
    ("Maternity Benefit Act, 1961", r"maternity benefit act", (1961,)),
    (
        "Sexual Harassment of Women at Workplace Act, 2013",
        r"sexual harassment of women at workplace",
        (2013,),
    ),
    (
        "Right to Fair Compensation and Transparency in Land Acquisition Act, 2013",
        r"right to fair compensation and transparency in land acquisition",
        (2013,),
    ),
    ("Environment (Protection) Act, 1986", r"environment protection act", (1986,)),
    (
        "Representation of the People Act, 1951",
        r"representation of the people act",
        (1951,),
    ),
    ("Advocates Act, 1961", r"advocates act", (1961,)),
    ("Contempt of Courts Act, 1971", r"contempt of courts act", (1971,)),
    (
        "Legal Services Authorities Act, 1987",
        r"legal services authorities act",
        (1987,),
    ),
    (
        "Protection of Human Rights Act, 1993",
        r"protection of human rights act",
        (1993,),
    ),
]


def find(
    acts: dict[str, dict], pattern: str, years: tuple[int, ...]
) -> list[tuple[str, dict]]:
    rx = re.compile(pattern)
    out = []
    for aid, a in acts.items():
        t = norm(a["title"])
        # the Act's own `year` field decides; a title is only read when the field is empty (a year quoted inside
        # "(Rep., Act 47 of 2023)" must not make a 1872 Act look like a 2023 one)
        year_ok = (
            any(str(y) == a["year"] for y in years)
            if a["year"] not in ("None", "", "0")
            else any(str(y) in (a["title"] or "") for y in years)
        )
        if rx.search(t) and year_ok:
            out.append((aid, a))
    return out


def classify(src, orig, served) -> str:
    """Where is the Act, and if it is missing somewhere, whose problem is that?"""
    if served:
        return "present, served"
    if orig:
        return "INDEXING: in acts_india, not in the served collection"
    if src:
        return (
            "INDEXING: in the source file, not in acts_india or the served collection"
        )
    return "ACQUISITION: in none of the three"


def main() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    src = scan_parquet()
    print(
        f"source parquet: {len(src)} acts, {sum(a['points'] for a in src.values()):,} chunks",
        flush=True,
    )
    orig = scan_qdrant(ORIG, "acts_india")
    print(
        f"acts_india central: {len(orig)} acts, {sum(a['points'] for a in orig.values()):,} points ({time.time() - t0:.0f}s)",
        flush=True,
    )
    served = scan_qdrant(COPY, "kanoon_v1")
    print(
        f"kanoon_v1 central: {len(served)} acts, {sum(a['points'] for a in served.values()):,} points ({time.time() - t0:.0f}s)",
        flush=True,
    )

    def kinds(acts):
        c = collections.Counter()
        for aid, a in acts.items():
            c[
                (aid.split("_")[1] if aid.startswith("IND_") else "other", a["status"])
            ] += 1
        return {f"{k[0]}/{k[1]}": v for k, v in sorted(c.items())}

    rows = []
    for name, pat, years in CHECKLIST:
        s, o, v = (
            find(src, pat, years),
            find(orig, pat, years),
            find(served, pat, years),
        )
        pick = v or o or s
        rows.append(
            {
                "act": name,
                "status_found": sorted({a["status"] for _i, a in pick}) if pick else [],
                "act_ids": [i for i, _a in pick],
                "chunks": {
                    "source": sum(a["points"] for _i, a in s),
                    "acts_india": sum(a["points"] for _i, a in o),
                    "served": sum(a["points"] for _i, a in v),
                },
                "where": classify(s, o, v),
            }
        )
    out = {
        "source": {
            "acts": len(src),
            "chunks": sum(a["points"] for a in src.values()),
            "by_kind": kinds(src),
        },
        "acts_india": {
            "acts": len(orig),
            "points": sum(a["points"] for a in orig.values()),
            "by_kind": kinds(orig),
        },
        "served": {
            "acts": len(served),
            "points": sum(a["points"] for a in served.values()),
            "by_kind": kinds(served),
        },
        "acts_only_in_source": sorted(set(src) - set(orig)),
        "acts_only_in_acts_india": sorted(set(orig) - set(src)),
        "in_acts_india_not_served": len(set(orig) - set(served)),
        "served_not_in_acts_india": len(set(served) - set(orig)),
        "checklist": rows,
    }
    # for each missing Act, every central title that shares its first two significant words, so a mis-spelling is not mistaken for absence
    for r in rows:
        if r["where"].startswith(("ACQ", "INDEX")) or not r["act_ids"]:
            words = [
                w
                for w in norm(r["act"].split(",")[0]).split()
                if w not in {"the", "of", "and", "act", "code"}
            ][:2]
            r["near_titles_in_source"] = [
                f"{a['title']} [{i}, {a['status']}]"
                for i, a in src.items()
                if all(w in norm(a["title"]) for w in words)
            ][:8]
    (HOME / "inventory.json").write_text(json.dumps(out, indent=1))
    print(f"wrote {HOME / 'inventory.json'}")


if __name__ == "__main__":
    main()

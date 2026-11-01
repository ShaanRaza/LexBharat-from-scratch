"""Fixed numbers of the research pipeline.

CLAUDE.md section 4: passage counts are 50 -> 10 -> at most 8. They are NOT settings:
changing them means changing docs/DECISIONS.md first (and it is the owner's call).
The gate threshold (0.6) is different - it is tuned on the 200-question set - so it
lives in settings as JEV_GATE_THRESHOLD.
"""

RECENT_TURNS = 6  # step 1: last 6 exchanges (user message + answer) kept in full
SEARCH_TOP_K = 50  # step 5: search returns this many chunks
RERANK_TOP_K = 10  # step 6: re-rank keeps this many
MAX_PASSAGES = 8  # step 7: gate keeps at most this many, labelled S1..S8

# The four reasons a citation can be removed. These exact strings go to
# invented_citation_log.reason (docs/CITATION-VERIFIER.md).
NOT_RETRIEVED = "not_retrieved"
RECORD_MISSING = "record_missing"
QUOTE_NOT_FOUND = "quote_not_found"
CLAIM_NOT_SUPPORTED = "claim_not_supported"
REMOVAL_REASONS = (NOT_RETRIEVED, RECORD_MISSING, QUOTE_NOT_FOUND, CLAIM_NOT_SUPPORTED)

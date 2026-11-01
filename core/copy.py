"""User-facing wording, in one place (docs/UX-COPY.md says do not improvise in code).

Strings marked VERBATIM are copied from docs/UX-COPY.md or CLAUDE.md. Strings marked
PROVISIONAL are my wording of a rule that the docs describe but do not word - the owner
must approve them (CLAUDE.md section 8: wording about advice is the owner's call).
Product name is never hard-coded; it comes from settings.PRODUCT_NAME.
"""

# VERBATIM (docs/UX-COPY.md, "No relevant results")
NOT_FOUND = "No matching judgments found in our dataset (data as of the snapshot date)."

# VERBATIM (docs/UX-COPY.md, "The dataset has no coverage of the question").
# NOTE: it says "central and state Acts"; CLAUDE.md s.1 says Central Acts only in v1.
COVERAGE = (
    "Version 1 covers Supreme Court judgments and central and state Acts and "
    "regulations. It does not include High Courts, district courts, tribunals, or "
    "judgments after the snapshot date."
)

# VERBATIM (CLAUDE.md section 6)
DATA_CREDIT = "Data: Open India Law by Vaquill AI, CC BY 4.0"

# VERBATIM label (docs/UX-COPY.md "The verification badge")
RECORD_FOUND = "Record found in dataset"
CITATION_STRING_LABEL = "as recorded in the dataset"
IN_FORCE_NOT_CHECKED = "in-force status not checked"


def not_legal_advice(product_name: str) -> str:
    """VERBATIM idea from docs/UX-COPY.md: '<product> gives information, not legal advice'."""
    return f"{product_name} gives information, not legal advice."


# PROVISIONAL - docs only say: opens by saying it cannot advise on the user's own
# situation, and suggests consulting an advocate.
PERSONAL_ADVICE_OPENING = (
    "I cannot advise on your own situation. Please consult an advocate. "
    "What follows is general information from the dataset."
)


# PROVISIONAL - docs only say: "a note saying one authority could not be verified".
def removed_note(count: int) -> str:
    if count == 1:
        return "One authority could not be verified and was removed from this answer."
    return (
        f"{count} authorities could not be verified and were removed from this answer."
    )


# PROVISIONAL - shown for a "trick" safety decision (docs: "tricks are blocked").
BLOCKED = "This request cannot be processed."

# PROVISIONAL - shown when the decision service and its fallback are both down.
TRY_AGAIN = "Something went wrong on our side. Please try again."

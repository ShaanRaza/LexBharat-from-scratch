"""The standing notices every result must carry, in ONE place.

docs/UX-COPY.md: these strings carry the trust promise and the legal position, so they
are not improvised in route code. Change them here, deliberately. The product name is
read from config (PRODUCT_NAME), never typed here (CLAUDE.md section 1).
"""

from datetime import date

from core.settings import Settings

# Verbatim from CLAUDE.md section 6 and docs/UX-COPY.md.
CC_BY_CREDIT = "Data: Open India Law by Vaquill AI, CC BY 4.0"
IN_FORCE_UNCHECKED = "in-force status not checked"
VERIFICATION_LABEL = "Record found in dataset"
CITATION_AS_RECORDED = "as recorded in the dataset"


def not_legal_advice(settings: Settings) -> str:
    return f"{settings.PRODUCT_NAME} gives information, not legal advice"


def provenance(settings: Settings, data_as_of: date | str | None) -> dict:
    """The block added to every answer, stats page and Act page."""
    as_of = data_as_of if data_as_of else settings.DATA_AS_OF
    return {
        "data_as_of": str(as_of) if as_of else None,
        "snapshot_version": settings.SNAPSHOT_VERSION,
        "credit": CC_BY_CREDIT,
        "notice": not_legal_advice(settings),
    }


# ---- wording NOT given verbatim in docs/UX-COPY.md -----------------------------------
# The owner must approve these (CLAUDE.md section 8: user-facing copy about the law is the
# owner's call). They are the smallest plain-words version of what UX-COPY.md describes.
PARTLY_SUPPORTED_LABEL = "Supports this only in part"
UNVERIFIED_ONE = "One authority could not be verified and was removed."
UNVERIFIED_MANY = "{n} authorities could not be verified and were removed."

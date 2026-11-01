import re
from pathlib import Path

from core.settings import Settings

ROOT = Path(__file__).resolve().parent.parent


def _fresh() -> Settings:
    # Ignore any local .env so the test checks the real defaults.
    return Settings(_env_file=None)


def test_defaults_load():
    s = _fresh()
    assert s.PRODUCT_NAME == "LexBharat"
    assert s.CORPUS_COLLECTION == "kanoon_v1"
    assert s.SNAPSHOT_VERSION == "v2026.08"
    assert s.JEV_TIMEOUT_MS == 800
    assert s.JEV_GATE_THRESHOLD == 0.6
    assert s.ANSWER_CACHE_TTL_DAYS == 7


def test_every_feature_switch_is_off():
    s = _fresh()
    switches = {
        k: v
        for k, v in s.model_dump().items()
        if k.startswith(("FEATURE_", "JEV_ENABLED_"))
    }
    assert switches, "no feature switches found"
    assert not any(switches.values()), switches


def test_has_a_field_for_every_name_in_env_example():
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    names = set(re.findall(r"^([A-Z][A-Z0-9_]*)=", text, flags=re.MULTILINE))
    missing = names - set(Settings.model_fields)
    assert not missing, f"missing from Settings: {sorted(missing)}"


def test_secrets_never_print():
    s = Settings(_env_file=None, GEMINI_API_KEY="super-secret-value")
    assert "super-secret-value" not in repr(s)
    assert "super-secret-value" not in str(s)
    assert "super-secret-value" not in s.model_dump_json()
    assert s.GEMINI_API_KEY.get_secret_value() == "super-secret-value"


def test_no_brand_word_hard_coded_in_code():
    """The product name lives in config only (CLAUDE.md section 1). The old working
    name must not appear in code; the new default is allowed only in settings."""
    old = "kanoon" + "buddy"
    new = "lexbharat"
    bad = []
    for base in ("api", "core", "adapters", "workers", "evals", "data", "migrations"):
        for f in (ROOT / base).rglob("*.py"):
            text = f.read_text(encoding="utf-8").lower()
            if old in text or (new in text and f != ROOT / "core" / "settings.py"):
                bad.append(str(f.relative_to(ROOT)))
    assert bad == [], bad

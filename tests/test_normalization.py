from app.catalog.normalization import build_search_text, normalize_text, tokenize_query


def test_normalize_text_removes_case_accents_and_extra_whitespace():
    assert normalize_text("  Violão   Clássico  ") == "violao classico"


def test_normalize_text_keeps_literal_symbols():
    assert normalize_text("Corda 100%") == "corda 100%"
    assert normalize_text("x' OR '1'='1") == "x' or '1'='1"


def test_tokenize_query_uses_normalized_whitespace():
    assert tokenize_query("  Kala   SOPRANO ") == ["kala", "soprano"]


def test_build_search_text_includes_category_name_description_and_spec_values():
    search_text = build_search_text(
        "Ukuleles",
        "Kala KA-15 Soprano",
        "Modelo compacto com corpo em mahogany.",
        {"top": "Mahogany", "scale": "502mm"},
    )

    assert "ukuleles" in search_text
    assert "kala ka-15 soprano" in search_text
    assert "modelo compacto" in search_text
    assert "mahogany" in search_text
    assert "502mm" in search_text


def test_build_search_text_is_deterministic_across_spec_key_order():
    first = build_search_text("Cat", "Prod", "Desc", {"b": "Two", "a": "One"})
    second = build_search_text("Cat", "Prod", "Desc", {"a": "One", "b": "Two"})
    assert first == second

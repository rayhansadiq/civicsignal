"""
Tests for the two pure functions that stand between an LLM's output and the
database. These are the highest-risk code in the project: everything else
fails loudly, but a bad parse or an unclamped score writes silently wrong
data that then shows up in the dashboard as fact.
"""

import pytest

from ai_signals import extract_json, validate


class TestExtractJson:
    """
    The model is instructed to return raw JSON, but instructions are not
    guarantees, and Gemini's OpenAI-compatible endpoint does not document
    a strict JSON mode. So the parser has to cope with what models actually
    do rather than what they were told.
    """

    def test_clean_json(self):
        raw = '{"signal_score": 85, "signal_category": "renewal", "signal_summary": "x"}'
        assert extract_json(raw) == {
            "signal_score": 85,
            "signal_category": "renewal",
            "signal_summary": "x",
        }

    def test_surrounding_whitespace(self):
        raw = '\n\n  {"signal_score": 40}  \n'
        assert extract_json(raw)["signal_score"] == 40

    def test_json_fenced_code_block(self):
        raw = '```json\n{"signal_score": 72, "signal_category": "renewal"}\n```'
        assert extract_json(raw)["signal_score"] == 72

    def test_bare_fenced_code_block(self):
        raw = '```\n{"signal_score": 30}\n```'
        assert extract_json(raw)["signal_score"] == 30

    def test_chatty_preamble(self):
        raw = 'Sure! Here is the JSON you asked for:\n{"signal_score": 20}'
        assert extract_json(raw)["signal_score"] == 20

    def test_trailing_commentary(self):
        raw = '{"signal_score": 55}\n\nLet me know if you need anything else.'
        assert extract_json(raw)["signal_score"] == 55

    def test_nested_objects_survive(self):
        # The last-resort regex is greedy, so it must capture the *outermost*
        # braces rather than stopping at the first inner closing brace.
        raw = 'Here: {"signal_score": 60, "meta": {"nested": true}} done'
        parsed = extract_json(raw)
        assert parsed["signal_score"] == 60
        assert parsed["meta"] == {"nested": True}

    def test_no_json_at_all_raises(self):
        with pytest.raises(ValueError, match="Could not find JSON"):
            extract_json("I'm sorry, I can't help with that.")

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            extract_json("")


class TestValidate:
    """
    validate() is the last line of defence before a write. It must never
    raise on plausible-but-wrong model output, and must never let an
    out-of-range score or unknown category reach the database, because the
    frontend colour-codes on both.
    """

    def test_valid_input_passes_through(self):
        assert validate(
            {
                "signal_score": 75,
                "signal_category": "new_initiative",
                "signal_summary": "A new system is being funded.",
            }
        ) == {
            "signal_score": 75,
            "signal_category": "new_initiative",
            "signal_summary": "A new system is being funded.",
        }

    @pytest.mark.parametrize(
        "given,expected",
        [(150, 100), (101, 100), (100, 100), (0, 0), (-20, 0), (-1, 0)],
    )
    def test_score_is_clamped_to_0_100(self, given, expected):
        assert validate({"signal_score": given})["signal_score"] == expected

    def test_score_given_as_string_is_coerced(self):
        assert validate({"signal_score": "88"})["signal_score"] == 88

    def test_missing_score_defaults_to_zero(self):
        assert validate({})["signal_score"] == 0

    @pytest.mark.parametrize(
        "category",
        ["renewal", "new_initiative", "expansion", "low_signal"],
    )
    def test_known_categories_are_kept(self, category):
        assert validate({"signal_category": category})["signal_category"] == category

    def test_unknown_category_falls_back(self):
        # The UI has styles for four categories. An unexpected fifth would
        # render unstyled, so it is coerced rather than passed through.
        assert validate({"signal_category": "SOMETHING_ELSE"})["signal_category"] == "low_signal"

    def test_category_case_and_whitespace_normalised(self):
        assert validate({"signal_category": "  Renewal "})["signal_category"] == "renewal"

    def test_missing_category_falls_back(self):
        assert validate({})["signal_category"] == "low_signal"

    def test_summary_is_stripped(self):
        assert validate({"signal_summary": "  spaced  "})["signal_summary"] == "spaced"

    def test_missing_summary_becomes_empty_string(self):
        # Not None: the frontend types signal_summary as a non-null string.
        assert validate({})["signal_summary"] == ""

    def test_returns_only_expected_keys(self):
        out = validate({"signal_score": 10, "unexpected": "field"})
        assert set(out) == {"signal_score", "signal_category", "signal_summary"}

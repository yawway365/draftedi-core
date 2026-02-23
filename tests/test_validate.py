"""Unit tests for draftedi.validate — pure validation functions."""

from __future__ import annotations


from draftedi.validate import (
    check_element_data_type,
    check_element_length,
    check_relational_conditions,
    leaf_loop,
    check_envelope,
    build_nav_tree,
    assign_loop_paths,
    build_spec_lookup,
    check_mandatory_segments,
    check_segment_max_use,
    SegEntry,
    LoopEntry,
)
from helpers import make_segment, make_spec_segment


# =========================================================================
# Helpers
# =========================================================================


def _make_rc(rc_type: str, positions: list[int]) -> dict:
    """Build a relational condition dict."""
    return {
        "transaction_set_segment_rc_type": rc_type,
        "transaction_set_segment_rc_elements": [str(p) for p in positions],
    }


# =========================================================================
# TestLeafLoop — pure function
# =========================================================================


class TestLeafLoop:
    def test_multi_part_path(self):
        assert leaf_loop("PO1/N1") == "N1"

    def test_single_part(self):
        assert leaf_loop("PO1") == "PO1"

    def test_none_input(self):
        assert leaf_loop(None) is None

    def test_empty_string(self):
        """Behavioral normalization: empty string and None both map to None."""
        result = leaf_loop("")
        assert result is None

    def test_trailing_slash(self):
        """Trailing slash produces empty string as last part."""
        result = leaf_loop("A/B/")
        assert result == ""


# =========================================================================
# TestCheckElementDataType — pure function
# =========================================================================


class TestCheckElementDataType:
    # AN — always passes
    def test_an_always_passes(self):
        assert check_element_data_type("anything!@#", "AN", "E100") is None

    # Numeric types
    def test_n0_valid_integer(self):
        assert check_element_data_type("12345", "N0", "E100") is None

    def test_n2_valid_negative(self):
        assert check_element_data_type("-100", "N2", "E100") is None

    def test_n_invalid_alpha(self):
        result = check_element_data_type("12A5", "N", "E100")
        assert result is not None
        assert "numeric" in result.lower()

    def test_n_decimal_fails(self):
        result = check_element_data_type("12.5", "N2", "E100")
        assert result is not None

    # Date types
    def test_dt_valid_8_digit(self):
        assert check_element_data_type("20231117", "DT", "E100") is None

    def test_dt_valid_6_digit(self):
        assert check_element_data_type("231117", "DT", "E100") is None

    def test_dt_invalid_length_7(self):
        result = check_element_data_type("2023111", "DT", "E100")
        assert result is not None

    def test_dt_invalid_month_13(self):
        result = check_element_data_type("20231317", "DT", "E100")
        assert result is not None
        assert "invalid date" in result.lower()

    def test_dt_invalid_day_zero(self):
        result = check_element_data_type("20231100", "DT", "E100")
        assert result is not None

    def test_dt_non_digits(self):
        result = check_element_data_type("2023ABCD", "DT", "E100")
        assert result is not None

    def test_dt_month_00_rejected(self):
        result = check_element_data_type("20230015", "DT", "E100")
        assert result is not None
        assert "invalid date" in result.lower()

    def test_dt_day_00_rejected(self):
        result = check_element_data_type("20230100", "DT", "E100")
        assert result is not None
        assert "invalid date" in result.lower()

    def test_dt_6_digit_month_13_rejected(self):
        result = check_element_data_type("231317", "DT", "E100")
        assert result is not None

    # Time types
    def test_tm_valid_4_digit(self):
        assert check_element_data_type("1430", "TM", "E100") is None

    def test_tm_valid_6_digit(self):
        assert check_element_data_type("143025", "TM", "E100") is None

    def test_tm_valid_8_digit(self):
        assert check_element_data_type("14302599", "TM", "E100") is None

    def test_tm_invalid_length_3(self):
        result = check_element_data_type("143", "TM", "E100")
        assert result is not None

    def test_tm_invalid_hour_25(self):
        result = check_element_data_type("2500", "TM", "E100")
        assert result is not None

    def test_tm_invalid_minute_60(self):
        result = check_element_data_type("1460", "TM", "E100")
        assert result is not None

    # Decimal type
    def test_r_valid_decimal(self):
        assert check_element_data_type("123.45", "R", "E100") is None

    def test_r_valid_integer(self):
        assert check_element_data_type("123", "R", "E100") is None

    def test_r_valid_negative(self):
        assert check_element_data_type("-99.5", "R", "E100") is None

    def test_r_invalid_double_dot(self):
        result = check_element_data_type("12.3.4", "R", "E100")
        assert result is not None

    # ID — always passes (code check is separate)
    def test_id_always_passes(self):
        assert check_element_data_type("PO", "ID", "E100") is None

    # B — always passes
    def test_b_always_passes(self):
        assert check_element_data_type("binary_junk", "B", "E100") is None

    # Empty value
    def test_empty_value_returns_none(self):
        assert check_element_data_type("", "N", "E100") is None

    # Unknown type
    def test_unknown_type_returns_none(self):
        assert check_element_data_type("anything", "ZZ", "E100") is None


# =========================================================================
# TestCheckElementLength — pure function
# =========================================================================


class TestCheckElementLength:
    def test_within_range(self):
        assert check_element_length("ABC", 1, 10) is None

    def test_at_minimum(self):
        assert check_element_length("A", 1, 10) is None

    def test_at_maximum(self):
        assert check_element_length("1234567890", 1, 10) is None

    def test_below_minimum(self):
        result = check_element_length("A", 2, 10)
        assert result is not None
        assert "minimum is 2" in result

    def test_above_maximum(self):
        result = check_element_length("12345678901", 1, 10)
        assert result is not None
        assert "maximum is 10" in result

    def test_empty_value_skips(self):
        assert check_element_length("", 1, 10) is None

    def test_invalid_min_max_skips(self):
        assert check_element_length("ABC", "bad", "bad") is None


# =========================================================================
# TestCheckRelationalConditions — pure function
# =========================================================================


class TestCheckRelationalConditions:
    # Paired (P)
    def test_paired_all_present_passes(self):
        issues = check_relational_conditions("N1", [_make_rc("P", [1, 2])], {1: "A", 2: "B"})
        assert len(issues) == 0

    def test_paired_partial_presence_fails(self):
        issues = check_relational_conditions("N1", [_make_rc("P", [1, 2])], {1: "A", 2: ""})
        assert len(issues) == 1
        assert issues[0]["severity"] == "error"
        assert "Paired" in issues[0]["message"]

    def test_paired_none_present_passes(self):
        issues = check_relational_conditions("N1", [_make_rc("P", [1, 2])], {1: "", 2: ""})
        assert len(issues) == 0

    # Required (R)
    def test_required_one_present_passes(self):
        issues = check_relational_conditions(
            "N1", [_make_rc("R", [1, 2, 3])], {1: "", 2: "X", 3: ""}
        )
        assert len(issues) == 0

    def test_required_none_present_warns(self):
        issues = check_relational_conditions("N1", [_make_rc("R", [1, 2])], {1: "", 2: ""})
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"
        assert "Required" in issues[0]["message"]

    # Exclusion (E)
    def test_exclusion_one_present_passes(self):
        issues = check_relational_conditions(
            "N1", [_make_rc("E", [1, 2, 3])], {1: "X", 2: "", 3: ""}
        )
        assert len(issues) == 0

    def test_exclusion_multiple_present_warns(self):
        issues = check_relational_conditions("N1", [_make_rc("E", [1, 2])], {1: "X", 2: "Y"})
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"
        assert "Exclusion" in issues[0]["message"]

    # Conditional (C)
    def test_conditional_first_present_rest_present_passes(self):
        issues = check_relational_conditions(
            "N1", [_make_rc("C", [1, 2, 3])], {1: "A", 2: "B", 3: "C"}
        )
        assert len(issues) == 0

    def test_conditional_first_present_rest_missing_fails(self):
        issues = check_relational_conditions(
            "N1", [_make_rc("C", [1, 2, 3])], {1: "A", 2: "", 3: "C"}
        )
        assert len(issues) == 1
        assert issues[0]["severity"] == "error"
        assert "Conditional" in issues[0]["message"]

    def test_conditional_first_absent_passes(self):
        issues = check_relational_conditions("N1", [_make_rc("C", [1, 2])], {1: "", 2: ""})
        assert len(issues) == 0

    # List conditional (L)
    def test_list_first_present_one_rest_passes(self):
        issues = check_relational_conditions(
            "N1", [_make_rc("L", [1, 2, 3])], {1: "A", 2: "", 3: "X"}
        )
        assert len(issues) == 0

    def test_list_first_present_no_rest_warns(self):
        issues = check_relational_conditions(
            "N1", [_make_rc("L", [1, 2, 3])], {1: "A", 2: "", 3: ""}
        )
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"
        assert "List conditional" in issues[0]["message"]

    # Edge cases
    def test_fewer_than_two_positions_skipped(self):
        issues = check_relational_conditions("N1", [_make_rc("P", [1])], {1: "A"})
        assert len(issues) == 0

    def test_invalid_position_values_skipped(self):
        rc = {
            "transaction_set_segment_rc_type": "P",
            "transaction_set_segment_rc_elements": ["bad", "data"],
        }
        issues = check_relational_conditions("N1", [rc], {})
        assert len(issues) == 0


# =========================================================================
# TestCheckEnvelope — pure function
# =========================================================================


class TestCheckEnvelope:
    def test_correct_count_no_issues(self):
        tx = {"segment_count_reported": 5}
        parsed = [make_segment("BEG", 1), make_segment("PO1", 2), make_segment("CTT", 3)]
        issues = check_envelope(tx, parsed)
        assert len(issues) == 0

    def test_count_mismatch_warns(self):
        tx = {"segment_count_reported": 10}
        parsed = [make_segment("BEG", 1), make_segment("CTT", 2)]
        issues = check_envelope(tx, parsed)
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"
        assert "SE01 reports 10" in issues[0]["message"]

    def test_none_count_skips(self):
        tx = {"segment_count_reported": None}
        parsed = [make_segment("BEG", 1)]
        issues = check_envelope(tx, parsed)
        assert len(issues) == 0


# =========================================================================
# TestNavTreeAndLoopPaths
# =========================================================================


class TestNavTreeAndLoopPaths:
    def test_flat_segments(self):
        spec = [
            make_spec_segment("BEG"),
            make_spec_segment("CTT"),
        ]
        root = build_nav_tree(spec)
        assert root.loop_id is None
        assert len(root.children) == 2
        assert isinstance(root.children[0], SegEntry)

    def test_loop_trigger_is_first_child(self):
        """Loop trigger segment is the first child of the loop entry."""
        spec = [
            {
                "type": "loop",
                "loop_id": "PO1",
                "segments": [
                    make_spec_segment("PO1"),
                    make_spec_segment("PID"),
                ],
            },
        ]
        root = build_nav_tree(spec)
        loop_child = root.children[0]
        assert isinstance(loop_child, LoopEntry)
        assert loop_child.trigger_id == "PO1"
        assert isinstance(loop_child.children[0], SegEntry)
        assert loop_child.children[0].segment_id == "PO1"

    def test_assign_flat_all_none(self):
        spec = [make_spec_segment("BEG"), make_spec_segment("CTT")]
        root = build_nav_tree(spec)
        parsed = [make_segment("BEG", 1), make_segment("CTT", 2)]
        results = assign_loop_paths(parsed, root)
        for _, lp in results:
            assert lp is None

    def test_single_loop(self):
        spec = [
            make_spec_segment("BEG"),
            {
                "type": "loop",
                "loop_id": "PO1",
                "segments": [
                    make_spec_segment("PO1"),
                    make_spec_segment("PID"),
                ],
            },
            make_spec_segment("CTT"),
        ]
        root = build_nav_tree(spec)
        parsed = [
            make_segment("BEG", 1),
            make_segment("PO1", 2),
            make_segment("PID", 3),
            make_segment("CTT", 4),
        ]
        results = assign_loop_paths(parsed, root)
        paths = [(seg["segment_id"], lp) for seg, lp in results]
        assert paths[0] == ("BEG", None)
        assert paths[1] == ("PO1", "PO1")
        assert paths[2] == ("PID", "PO1")
        assert paths[3] == ("CTT", None)

    def test_nested_loops(self):
        spec = [
            make_spec_segment("BEG"),
            {
                "type": "loop",
                "loop_id": "PO1",
                "segments": [
                    make_spec_segment("PO1"),
                    {
                        "type": "loop",
                        "loop_id": "N1",
                        "segments": [
                            make_spec_segment("N1"),
                            make_spec_segment("N3"),
                        ],
                    },
                ],
            },
            make_spec_segment("CTT"),
        ]
        root = build_nav_tree(spec)
        parsed = [
            make_segment("BEG", 1),
            make_segment("PO1", 2),
            make_segment("N1", 3),
            make_segment("N3", 4),
            make_segment("CTT", 5),
        ]
        results = assign_loop_paths(parsed, root)
        paths = [(seg["segment_id"], lp) for seg, lp in results]
        assert paths[0] == ("BEG", None)
        assert paths[1] == ("PO1", "PO1")
        assert paths[2] == ("N1", "PO1/N1")
        assert paths[3] == ("N3", "PO1/N1")
        assert paths[4] == ("CTT", None)

    def test_loop_iteration_resets(self):
        spec = [
            {
                "type": "loop",
                "loop_id": "PO1",
                "segments": [
                    make_spec_segment("PO1"),
                    make_spec_segment("PID"),
                ],
            },
        ]
        root = build_nav_tree(spec)
        parsed = [
            make_segment("PO1", 1),
            make_segment("PID", 2),
            make_segment("PO1", 3),
            make_segment("PID", 4),
        ]
        results = assign_loop_paths(parsed, root)
        assert all(lp == "PO1" for _, lp in results)

    def test_unrecognized_segment_at_root(self):
        spec = [make_spec_segment("BEG")]
        root = build_nav_tree(spec)
        parsed = [make_segment("BEG", 1), make_segment("ZZZ", 2)]
        results = assign_loop_paths(parsed, root)
        assert results[1][1] is None


# =========================================================================
# TestBuildSpecLookup
# =========================================================================


class TestBuildSpecLookup:
    def test_flat_segments(self):
        spec = [make_spec_segment("BEG"), make_spec_segment("CTT")]
        lookup = build_spec_lookup(spec)
        assert ("BEG", None) in lookup
        assert ("CTT", None) in lookup

    def test_loop_segments(self):
        spec = [
            {
                "type": "loop",
                "loop_id": "PO1",
                "segments": [make_spec_segment("PO1")],
            },
        ]
        lookup = build_spec_lookup(spec)
        assert ("PO1", "PO1") in lookup

    def test_first_entry_wins(self):
        seg1 = make_spec_segment("BEG", requirement="M")
        seg2 = make_spec_segment("BEG", requirement="O")
        spec = [seg1, seg2]
        lookup = build_spec_lookup(spec)
        assert lookup[("BEG", None)]["segment_requirement"] == "M"


# =========================================================================
# TestCheckMandatorySegments
# =========================================================================


class TestCheckMandatorySegments:
    def test_mandatory_present_passes(self):
        spec = [make_spec_segment("BEG", requirement="M")]
        assignments = [(make_segment("BEG", 1), None)]
        issues = check_mandatory_segments(assignments, spec)
        assert len(issues) == 0

    def test_mandatory_missing_errors(self):
        spec = [make_spec_segment("BEG", requirement="M")]
        assignments = [(make_segment("CTT", 1), None)]
        issues = check_mandatory_segments(assignments, spec)
        assert len(issues) == 1
        assert issues[0]["severity"] == "error"
        assert "BEG" in issues[0]["message"]

    def test_mandatory_in_inactive_loop_passes(self):
        spec = [
            {
                "type": "loop",
                "loop_id": "N1",
                "segments": [make_spec_segment("N1", requirement="M")],
            },
        ]
        assignments = [(make_segment("BEG", 1), None)]
        issues = check_mandatory_segments(assignments, spec)
        assert len(issues) == 0

    def test_mandatory_in_active_loop_missing_errors(self):
        spec = [
            {
                "type": "loop",
                "loop_id": "N1",
                "segments": [
                    make_spec_segment("N1", requirement="M"),
                    make_spec_segment("N3", requirement="M"),
                ],
            },
        ]
        assignments = [(make_segment("N1", 1), "N1")]
        issues = check_mandatory_segments(assignments, spec)
        assert len(issues) == 1
        assert "N3" in issues[0]["message"]
        assert "loop N1" in issues[0]["message"]

    def test_envelope_segments_st_se_skipped(self):
        spec = [
            make_spec_segment("ST", requirement="M"),
            make_spec_segment("SE", requirement="M"),
        ]
        assignments = []
        issues = check_mandatory_segments(assignments, spec)
        assert len(issues) == 0


# =========================================================================
# TestCheckSegmentMaxUse
# =========================================================================


class TestCheckSegmentMaxUse:
    def test_within_limit_passes(self):
        spec = [make_spec_segment("BEG", max_use=5)]
        assignments = [(make_segment("BEG", i), None) for i in range(1, 4)]
        issues = check_segment_max_use(assignments, spec)
        assert len(issues) == 0

    def test_exceeded_warns(self):
        spec = [make_spec_segment("BEG", max_use=1)]
        assignments = [(make_segment("BEG", i), None) for i in range(1, 4)]
        issues = check_segment_max_use(assignments, spec)
        assert len(issues) == 1
        assert issues[0]["severity"] == "warning"
        assert "3 time(s)" in issues[0]["message"]
        assert "max use is 1" in issues[0]["message"]

    def test_none_max_use_skips(self):
        spec = [make_spec_segment("BEG")]
        assignments = [(make_segment("BEG", i), None) for i in range(1, 10)]
        issues = check_segment_max_use(assignments, spec)
        assert len(issues) == 0

    def test_invalid_max_use_skips(self):
        spec = [make_spec_segment("BEG", max_use="N/A")]
        assignments = [(make_segment("BEG", 1), None)]
        issues = check_segment_max_use(assignments, spec)
        assert len(issues) == 0


# =========================================================================
# TestDataTypeAdversarial — bug-fix verification
# =========================================================================


class TestDataTypeAdversarial:
    def test_dt_feb_29_non_leap_year_rejected(self):
        """2025 is not a leap year; Feb 29 is invalid."""
        result = check_element_data_type("20250229", "DT", "E100")
        assert result is not None
        assert "invalid date" in result.lower()

    def test_dt_april_31_rejected(self):
        """April has 30 days; day 31 is invalid."""
        result = check_element_data_type("20230431", "DT", "E100")
        assert result is not None
        assert "invalid date" in result.lower()

    def test_dt_feb_29_leap_year_accepted(self):
        """2024 is a leap year; Feb 29 is valid."""
        result = check_element_data_type("20240229", "DT", "E100")
        assert result is None

    def test_dt_6digit_yy00_leap_feb29_accepted(self):
        """6-digit: YY=00 → year 2000, which is a leap year."""
        result = check_element_data_type("000229", "DT", "E100")
        assert result is None

    def test_dt_6digit_yy99_not_leap_feb29_rejected(self):
        """6-digit: YY=99 → year 1999, not a leap year."""
        result = check_element_data_type("990229", "DT", "E100")
        assert result is not None
        assert "invalid date" in result.lower()

    def test_n_multiple_leading_minuses_rejected(self):
        """Multiple leading minuses are invalid (bug fix)."""
        result = check_element_data_type("---5", "N0", "E100")
        assert result is not None
        assert "numeric" in result.lower()

    def test_n_double_minus_rejected(self):
        """Double minus is invalid (bug fix)."""
        result = check_element_data_type("--5", "N0", "E100")
        assert result is not None
        assert "numeric" in result.lower()

    def test_n_single_minus_valid(self):
        """Single leading minus is valid (bug fix confirms correct behaviour)."""
        result = check_element_data_type("-5", "N0", "E100")
        assert result is None

    def test_n_minus_only_rejected(self):
        """A lone '-' is rejected (no digits follow)."""
        result = check_element_data_type("-", "N0", "E100")
        assert result is not None
        assert "numeric" in result.lower()

    def test_tm_seconds_60_rejected(self):
        """Seconds=60 is invalid (bug fix)."""
        result = check_element_data_type("001260", "TM", "E100")
        assert result is not None
        assert "invalid time" in result.lower()

    def test_tm_seconds_59_accepted(self):
        """Seconds=59 is valid."""
        result = check_element_data_type("001259", "TM", "E100")
        assert result is None

    def test_n_very_long_numeric_accepted(self):
        """No length limit in type check — very long numerics pass."""
        result = check_element_data_type("9" * 1000, "N0", "E100")
        assert result is None

    def test_dt_6_digit_month_13_rejected(self):
        """6-digit date with month=13 is correctly rejected."""
        result = check_element_data_type("231317", "DT", "E100")
        assert result is not None


# =========================================================================
# TestRelationalAdversarial
# =========================================================================


class TestRelationalAdversarial:
    def test_position_zero_treated_as_absent(self):
        """Position 0 is not a valid X12 element position; treated as absent."""
        rc = _make_rc("P", [0, 1])
        issues = check_relational_conditions("N1", [rc], {0: "", 1: "A"})
        assert len(issues) == 1
        assert "Paired" in issues[0]["message"]

    def test_all_positions_non_numeric_skipped(self):
        """If all position values fail int conversion, condition is skipped."""
        rc = {
            "transaction_set_segment_rc_type": "P",
            "transaction_set_segment_rc_elements": ["A", "B", "C"],
        }
        issues = check_relational_conditions("N1", [rc], {1: "X", 2: "Y"})
        assert len(issues) == 0

    def test_duplicate_positions_in_exclusion_no_false_violation(self):
        """Duplicate positions in Exclusion do NOT produce a false violation (bug fix)."""
        rc = _make_rc("E", [1, 1])
        issues = check_relational_conditions("N1", [rc], {1: "X"})
        assert len(issues) == 0

    def test_position_beyond_segment_elements(self):
        """Position 99 absent from val_by_pos → treated as missing."""
        rc = _make_rc("P", [1, 99])
        issues = check_relational_conditions("N1", [rc], {1: "A"})
        assert len(issues) == 1
        assert "Paired" in issues[0]["message"]

    def test_single_position_skipped(self):
        """Relational conditions with < 2 positions are skipped."""
        rc = _make_rc("P", [1])
        issues = check_relational_conditions("N1", [rc], {1: "X"})
        assert len(issues) == 0


# =========================================================================
# TestLoopPathAdversarial
# =========================================================================


class TestLoopPathAdversarial:
    def test_deep_nesting_20_levels(self):
        """20-level deep nested spec does not crash assignment."""
        spec: list = []
        current = spec
        for i in range(20):
            loop = {
                "type": "loop",
                "loop_id": f"L{i}",
                "segments": [make_spec_segment(f"S{i}")],
            }
            current.append(loop)
            current = loop["segments"]

        root = build_nav_tree(spec)
        parsed = [make_segment(f"S{i}", i + 1) for i in range(20)]
        results = assign_loop_paths(parsed, root)

        assert len(results) == 20
        last_path = results[-1][1]
        assert last_path is not None
        assert last_path.count("/") == 19


# =========================================================================
# TestEnvelopeAdversarial
# =========================================================================


class TestEnvelopeAdversarial:
    def test_negative_segment_count(self):
        """Negative segment_count_reported triggers warning."""
        tx = {"segment_count_reported": -5}
        parsed = [make_segment("BEG", 1)]
        issues = check_envelope(tx, parsed)
        assert len(issues) == 1
        assert "SE01 reports -5" in issues[0]["message"]

    def test_very_large_segment_count(self):
        """Very large segment count triggers warning."""
        tx = {"segment_count_reported": 999999999}
        parsed = [make_segment("BEG", 1)]
        issues = check_envelope(tx, parsed)
        assert len(issues) == 1
        assert "999999999" in issues[0]["message"]

    def test_string_segment_count_warns(self):
        """String segment_count_reported (type mismatch) triggers warning."""
        tx = {"segment_count_reported": "12"}
        parsed = [make_segment("BEG", 1)] * 10
        issues = check_envelope(tx, parsed)
        assert len(issues) == 1

    def test_zero_segment_count(self):
        """Zero segment count always triggers warning."""
        tx = {"segment_count_reported": 0}
        parsed = [make_segment("BEG", 1)]
        issues = check_envelope(tx, parsed)
        assert len(issues) == 1
        assert "SE01 reports 0" in issues[0]["message"]


# =========================================================================
# 6-digit DT century inference
# =========================================================================


class TestDTCenturyInference:
    def test_yy00_maps_to_2000(self):
        """YY=00 → year 2000."""
        result = check_element_data_type("000115", "DT", "E100")
        assert result is None

    def test_yy49_maps_to_2049(self):
        """YY=49 → year 2049."""
        result = check_element_data_type("491231", "DT", "E100")
        assert result is None

    def test_yy50_maps_to_1950(self):
        """YY=50 → year 1950."""
        result = check_element_data_type("500101", "DT", "E100")
        assert result is None

    def test_yy99_maps_to_1999(self):
        """YY=99 → year 1999."""
        result = check_element_data_type("991231", "DT", "E100")
        assert result is None


# =========================================================================
# TestNegativeImport — omitted symbols must not be importable
# =========================================================================


class TestNegativeImport:
    def test_validate_transaction_not_importable(self):
        import importlib

        mod = importlib.import_module("draftedi.validate")
        assert not hasattr(mod, "validate_transaction")

    def test_get_validation_context_not_importable(self):
        import importlib

        mod = importlib.import_module("draftedi.validate")
        assert not hasattr(mod, "_get_validation_context")
        assert not hasattr(mod, "get_validation_context")

    def test_save_validation_results_not_importable(self):
        import importlib

        mod = importlib.import_module("draftedi.validate")
        assert not hasattr(mod, "_save_validation_results")
        assert not hasattr(mod, "save_validation_results")

    def test_persist_loop_paths_not_importable(self):
        import importlib

        mod = importlib.import_module("draftedi.validate")
        assert not hasattr(mod, "_persist_loop_paths")
        assert not hasattr(mod, "persist_loop_paths")

    def test_check_code_value_not_importable(self):
        import importlib

        mod = importlib.import_module("draftedi.validate")
        assert not hasattr(mod, "_check_code_value")
        assert not hasattr(mod, "check_code_value")

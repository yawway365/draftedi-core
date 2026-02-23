"""Tests for draftedi.parser."""

from __future__ import annotations

import pytest

from draftedi.parser import parse_interchange, parse_edi_file
from factories import SampleX12
from helpers import to_bytes


# =========================================================================
# parse_interchange — separator detection
# =========================================================================


class TestParseInterchange:
    def test_standard_separators(self) -> None:
        edi = SampleX12.build_interchange()
        result = parse_interchange(edi)
        assert result["element_sep"] == "*"
        assert result["segment_term"] == "~"
        assert result["repetition_sep"] == "^"
        assert result["component_sep"] == ">"

    def test_pipe_element_separator(self) -> None:
        isa = (
            "ISA|00|          |00|          "
            "|ZZ|TESTSENDER     |ZZ|TESTRECEIVER   "
            "|231117|0041|^|00501|000000001|0|T|>~"
        )
        result = parse_interchange(isa)
        assert result["element_sep"] == "|"

    def test_returns_raw_isa_and_parts(self) -> None:
        edi = SampleX12.build_interchange()
        result = parse_interchange(edi)
        assert len(result["raw_isa"]) == 106
        assert result["isa_parts"][0] == "ISA"
        assert len(result["isa_parts"]) == 17

    def test_blank_repetition_sep_kept_as_space(self) -> None:
        isa = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041* *00501*000000001*0*T*>~"
        )
        result = parse_interchange(isa)
        assert result["repetition_sep"] == " "

    def test_not_starting_with_isa_raises(self) -> None:
        with pytest.raises(ValueError, match="does not start with ISA"):
            parse_interchange("GS*PO*SENDER*RECEIVER*20231117*0041*1*X*005010~")

    def test_too_short_raises(self) -> None:
        with pytest.raises(ValueError, match="does not contain a full ISA segment"):
            parse_interchange("ISA*00*short")

    def test_exactly_106_chars_parses(self) -> None:
        isa = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>~"
        )
        assert len(isa) == 106
        result = parse_interchange(isa)
        assert result["element_sep"] == "*"


# =========================================================================
# parse_edi_file — happy path with real fixtures
# =========================================================================


class TestParseEdiFileHappyPath:
    def test_sample_850(self, sample_850: bytes) -> None:
        result = parse_edi_file(sample_850)
        interchanges = result["interchanges"]
        assert len(interchanges) == 1
        groups = interchanges[0]["groups"]
        assert len(groups) == 1
        txns = groups[0]["transactions"]
        assert len(txns) == 1
        assert txns[0]["transaction_set_id"] == "850"

    def test_sample_997(self, sample_997: bytes) -> None:
        result = parse_edi_file(sample_997)
        txns = result["interchanges"][0]["groups"][0]["transactions"]
        assert len(txns) == 1
        assert txns[0]["transaction_set_id"] == "997"

    def test_file_metadata(self, sample_850: bytes) -> None:
        result = parse_edi_file(sample_850, source="sftp_poll")
        assert result["file_hash"]
        assert len(result["file_hash"]) == 64
        assert result["processed_at"]
        assert result["source"] == "sftp_poll"

    def test_no_db_fields_in_result(self, sample_850: bytes) -> None:
        result = parse_edi_file(sample_850)
        forbidden = {
            "partner_id",
            "file_id",
            "interchange_id",
            "processing_state",
            "raw_bytes",
            "ack_status",
            "group_id",
            "transaction_id",
            "edi_file_dict",
            "parse_status",
            "parse_error",
        }
        assert not forbidden.intersection(result.keys())

    def test_isa_fields(self, sample_850: bytes) -> None:
        result = parse_edi_file(sample_850)
        ic = result["interchanges"][0]
        assert ic["isa_sender_qualifier"] is not None
        assert ic["isa_sender_id"] is not None
        assert ic["isa_receiver_qualifier"] is not None
        assert ic["isa_receiver_id"] is not None
        assert ic["isa_control_number"] is not None
        assert ic["usage_indicator"] is not None
        assert ic["element_sep"] == "*"
        assert ic["segment_term"] == "~"

    def test_gs_fields(self, sample_850: bytes) -> None:
        result = parse_edi_file(sample_850)
        grp = result["interchanges"][0]["groups"][0]
        assert grp["functional_id_code"] is not None
        assert grp["gs_sender_id"] is not None
        assert grp["gs_receiver_id"] is not None
        assert grp["group_control_number"] is not None
        assert grp["x12_release"] is not None

    def test_st_se_fields(self, sample_850: bytes) -> None:
        result = parse_edi_file(sample_850)
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        assert tx["transaction_set_id"] == "850"
        assert tx["control_number"] == "0001"
        assert tx["segment_count_reported"] is not None
        assert tx["raw_st_segment"] is not None
        assert tx["raw_se_segment"] is not None


# =========================================================================
# parse_edi_file — structure and element parsing
# =========================================================================


class TestParseEdiFileStructure:
    def test_segment_positions_sequential(self, sample_850: bytes) -> None:
        result = parse_edi_file(sample_850)
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        positions = [seg["position"] for seg in tx["segments"]]
        assert positions == list(range(1, len(positions) + 1))

    def test_element_values_from_beg(self) -> None:
        edi = SampleX12.build_interchange()
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        beg = tx["segments"][0]
        assert beg["segment_id"] == "BEG"
        vals = {e["element_pos"]: e["value_text"] for e in beg["elements"]}
        assert vals[1] == "00"
        assert vals[2] == "NE"
        assert vals[3] == "PO-001"

    def test_composite_element_parsing(self) -> None:
        composite_txn = "ST*837*0001~SV1*HC>99213>25*50*UN*1~SE*3*0001~"
        group = SampleX12.build_group(
            functional_id="HC",
            transactions=[composite_txn],
        )
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        sv1 = tx["segments"][0]
        assert sv1["segment_id"] == "SV1"
        elem1 = sv1["elements"][0]
        assert elem1["is_composite"] == 1
        assert len(elem1["components"]) == 3
        assert elem1["components"][0]["value_text"] == "HC"
        assert elem1["components"][1]["value_text"] == "99213"
        assert elem1["components"][2]["value_text"] == "25"

    def test_empty_middle_element(self) -> None:
        txn = "ST*850*0001~N4*CHICAGO**60601~SE*3*0001~"
        group = SampleX12.build_group(transactions=[txn])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        n4 = tx["segments"][0]
        vals = {e["element_pos"]: e["value_text"] for e in n4["elements"]}
        assert vals[1] == "CHICAGO"
        assert vals[2] == ""
        assert vals[3] == "60601"

    def test_repetition_separator_splits_values(self) -> None:
        txn = "ST*850*0001~REF*PO*ABC^DEF~SE*3*0001~"
        group = SampleX12.build_group(transactions=[txn])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        ref = tx["segments"][0]
        elements_pos2 = [e for e in ref["elements"] if e["element_pos"] == 2]
        assert len(elements_pos2) >= 1

    def test_multi_repetition_element_produces_distinct_dicts(self) -> None:
        """Regression for F-027: each ^ repetition yields a separate Element dict.

        Asserts 3-repetition REF element produces 3 distinct dicts with correct
        value_text and repetition_index. (ref: DL-002)
        """
        txn = "ST*850*0001~REF*PO*FIRST^SECOND^THIRD~SE*3*0001~"
        group = SampleX12.build_group(transactions=[txn])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        ref = tx["segments"][0]
        elements_pos2 = [e for e in ref["elements"] if e["element_pos"] == 2]
        assert len(elements_pos2) == 3
        assert [e["value_text"] for e in elements_pos2] == ["FIRST", "SECOND", "THIRD"]
        assert [e["repetition_index"] for e in elements_pos2] == [1, 2, 3]

    def test_segments_between_gs_and_st_excluded(self) -> None:
        """Segments between GS and ST are silently ignored."""
        edi = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>~"
            "GS*PO*SENDER*RECEIVER*20231117*0041*1*X*005010~"
            "REF*PO*ORPHAN~"
            "ST*850*0001~BEG*00*NE~SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        seg_ids = [s["segment_id"] for s in tx["segments"]]
        assert "REF" not in seg_ids
        assert "BEG" in seg_ids


# =========================================================================
# parse_edi_file — multi-envelope
# =========================================================================


class TestParseEdiFileMultiEnvelope:
    def test_two_interchanges(self) -> None:
        ic1 = SampleX12.build_interchange(control_number="000000001")
        ic2 = SampleX12.build_interchange(control_number="000000002")
        result = parse_edi_file(to_bytes(ic1 + ic2))
        assert len(result["interchanges"]) == 2

    def test_two_groups_in_one_interchange(self) -> None:
        g1 = SampleX12.build_group(functional_id="PO", control_number="000000001")
        g2 = SampleX12.build_group(functional_id="IN", control_number="000000002")
        edi = SampleX12.build_interchange(groups=[g1, g2])
        result = parse_edi_file(to_bytes(edi))
        assert len(result["interchanges"]) == 1
        assert len(result["interchanges"][0]["groups"]) == 2

    def test_two_transactions_in_one_group(self) -> None:
        tx1 = SampleX12.build_850(control_number="0001")
        tx2 = SampleX12.build_850(control_number="0002")
        group = SampleX12.build_group(transactions=[tx1, tx2])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        txns = result["interchanges"][0]["groups"][0]["transactions"]
        assert len(txns) == 2
        assert txns[0]["control_number"] == "0001"
        assert txns[1]["control_number"] == "0002"

    def test_two_interchanges_different_separators(self) -> None:
        """Each interchange uses its own separator set for element parsing."""
        # First interchange: standard separators (* element, > component, ^ rep, ~ term)
        ic1_txn = "ST*850*0001~BEG*00*NE*VAL1>COMP~SE*3*0001~"
        ic1_group = SampleX12.build_group(transactions=[ic1_txn])
        ic1 = SampleX12.build_interchange(groups=[ic1_group], control_number="000000001")

        # Second interchange: pipe as element sep, colon as component sep
        # ISA header with | as element sep and : as component sep at position 105 = ~
        ic2_raw = (
            "ISA|00|          |00|          "
            "|ZZ|SENDER2        |ZZ|RECEIVER2      "
            "|231117|0041|^|00501|000000002|0|T|:~"
            "GS|PO|SENDER2|RECEIVER2|20231117|0041|000000002|X|005010~"
            "ST|850|0002~"
            "BEG|00|NE|VAL2:COMP2~"
            "SE|3|0002~"
            "GE|1|000000002~"
            "IEA|1|000000002~"
        )

        result = parse_edi_file(to_bytes(ic1 + ic2_raw))
        assert len(result["interchanges"]) == 2

        # First interchange uses * as element sep
        ic1_result = result["interchanges"][0]
        assert ic1_result["element_sep"] == "*"

        # Second interchange uses | as element sep
        ic2_result = result["interchanges"][1]
        assert ic2_result["element_sep"] == "|"

        # Segments inside second interchange are parsed with | element sep
        tx2 = ic2_result["groups"][0]["transactions"][0]
        assert tx2["transaction_set_id"] == "850"


# =========================================================================
# parse_edi_file — error paths
# =========================================================================


class TestParseEdiFileErrors:
    def test_malformed_isa_raises(self, sample_edi_path: object) -> None:
        from pathlib import Path

        path = Path(str(sample_edi_path))
        raw = (path / "malformed_isa.edi").read_bytes()
        with pytest.raises(ValueError):
            parse_edi_file(raw)

    def test_st_before_gs_raises(self) -> None:
        edi = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>~"
            "ST*850*0001~"
            "SE*2*0001~"
            "IEA*0*000000001~"
        )
        with pytest.raises(ValueError, match="Encountered ST before GS"):
            parse_edi_file(to_bytes(edi))

    def test_se_without_transaction_raises(self) -> None:
        edi = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>~"
            "GS*PO*SENDER*RECEIVER*20231117*0041*1*X*005010~"
            "SE*2*0001~"
            "GE*0*1~"
            "IEA*1*000000001~"
        )
        with pytest.raises(ValueError, match="Encountered SE but no active transaction"):
            parse_edi_file(to_bytes(edi))

    def test_truncated_file_does_not_crash(self, sample_edi_path: object) -> None:
        from pathlib import Path

        path = Path(str(sample_edi_path))
        raw = (path / "truncated_file.edi").read_bytes()
        result = parse_edi_file(raw)
        assert result["file_hash"] is not None

    def test_missing_gs_graceful(self, sample_edi_path: object) -> None:
        from pathlib import Path

        path = Path(str(sample_edi_path))
        raw = (path / "missing_gs.edi").read_bytes()
        result = parse_edi_file(raw)
        assert len(result["interchanges"]) >= 1

    def test_filename_from_attribute(self) -> None:
        edi = SampleX12.build_interchange()
        raw = to_bytes(edi)

        class NamedBytes(bytes):
            filename: str

        named = NamedBytes(raw)
        named.filename = "test_upload.edi"
        result = parse_edi_file(named)
        assert result["filename"] == "test_upload.edi"

    def test_filename_fallback_raw_text(self) -> None:
        edi = SampleX12.build_interchange()
        result = parse_edi_file(to_bytes(edi))
        assert result["filename"] == "raw text"


# =========================================================================
# Adversarial — encoding abuse
# =========================================================================


class TestParserEncoding:
    def test_bom_prefix_rejected(self) -> None:
        """UTF-8 BOM before ISA causes rejection — parser does not strip it."""
        edi = SampleX12.build_interchange()
        raw = b"\xef\xbb\xbf" + to_bytes(edi)
        with pytest.raises(ValueError, match="does not start with ISA"):
            parse_edi_file(raw)

    def test_null_bytes_in_element_data(self) -> None:
        """Null bytes are valid UTF-8 and pass through to element values."""
        txn = "ST*850*0001~BEG*00*NE*PO\x00001**20231117~SE*3*0001~"
        group = SampleX12.build_group(transactions=[txn])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        beg = tx["segments"][0]
        vals = {e["element_pos"]: e["value_text"] for e in beg["elements"]}
        assert "\x00" in vals[3]

    def test_latin1_bytes_replaced(self) -> None:
        """Non-UTF-8 bytes are replaced with U+FFFD but parsing continues."""
        edi = SampleX12.build_interchange()
        raw = to_bytes(edi)
        raw = raw.replace(b"PO-001", b"PO\xe9001")
        result = parse_edi_file(raw)
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        beg = tx["segments"][0]
        vals = {e["element_pos"]: e["value_text"] for e in beg["elements"]}
        assert "\ufffd" in vals[3]

    def test_empty_bytes_rejected(self) -> None:
        with pytest.raises(ValueError, match="does not start with ISA"):
            parse_edi_file(b"")

    def test_whitespace_only_rejected(self) -> None:
        with pytest.raises(ValueError, match="does not start with ISA"):
            parse_edi_file(b"   \n\t  ")

    def test_utf8_input_parsed_correctly(self) -> None:
        """UTF-8 encoded EDI parses without replacement characters."""
        edi = SampleX12.build_interchange()
        result = parse_edi_file(to_bytes(edi))
        assert result["file_hash"]
        assert len(result["interchanges"]) == 1


# =========================================================================
# Adversarial — boundary conditions
# =========================================================================


class TestParserBoundary:
    def test_isa_105_chars_off_by_one(self) -> None:
        """ISA with 105 chars (one short) is rejected."""
        isa = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>"
        )
        assert len(isa) == 105
        with pytest.raises(ValueError, match="does not contain a full ISA segment"):
            parse_interchange(isa)

    def test_segment_term_is_newline(self) -> None:
        """If segment_term at position 105 is newline, segments split on newline."""
        isa = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>"
        )
        assert len(isa) == 105
        isa_with_nl = isa + "\n"
        assert len(isa_with_nl) == 106
        result = parse_interchange(isa_with_nl)
        assert result["segment_term"] == "\n"

    def test_isa_with_fewer_than_16_elements(self) -> None:
        """Malformed ISA with missing fields still parses — component_sep is None."""
        isa_short = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001"
        )
        isa_short = isa_short.ljust(105) + "~"
        assert len(isa_short) == 106
        result = parse_interchange(isa_short)
        assert result["component_sep"] is None

    def test_segment_with_100_elements(self) -> None:
        """Parser handles segments with many elements without crashing."""
        elements = "*".join([f"V{i}" for i in range(100)])
        txn = f"ST*850*0001~BEG*{elements}~SE*3*0001~"
        group = SampleX12.build_group(transactions=[txn])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        beg = tx["segments"][0]
        assert len(beg["elements"]) == 100

    def test_se_non_numeric_count(self) -> None:
        """SE with non-numeric count sets segment_count_reported to None."""
        txn = "ST*850*0001~BEG*00*NE~SE*ABC*0001~"
        group = SampleX12.build_group(transactions=[txn])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        assert tx["segment_count_reported"] is None


# =========================================================================
# Adversarial — separator conflicts
# =========================================================================


class TestParserSeparatorConflicts:
    def test_element_sep_equals_segment_term(self) -> None:
        """When element_sep == segment_term, segment splitting is corrupted."""
        isa = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>*"
        )
        assert len(isa) == 106
        result = parse_interchange(isa)
        assert result["element_sep"] == "*"
        assert result["segment_term"] == "*"

    def test_component_sep_equals_element_sep_crashes(self) -> None:
        """Bug fixed: empty ISA16 returns component_sep=None instead of IndexError."""
        isa = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T**~"
        )
        assert len(isa) == 106
        result = parse_interchange(isa)
        assert result["component_sep"] is None

    def test_repetition_sep_equals_element_sep(self) -> None:
        """When repetition_sep == element_sep, element values get false splits."""
        isa = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041***00501*000000001*0*T*>~"
        )
        assert len(isa) == 106
        result = parse_interchange(isa)
        assert result["element_sep"] == "*"

    def test_all_separators_identical(self) -> None:
        """All four separators = '*' — total parse corruption."""
        isa = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041***00501*000000001*0*T**~"
        )
        isa = isa[:-1] + "*"
        assert len(isa) == 106
        result = parse_interchange(isa)
        assert result["element_sep"] == "*"
        assert result["segment_term"] == "*"


# =========================================================================
# Adversarial — structural abuse
# =========================================================================


class TestParserStructuralAbuse:
    def test_ge_without_preceding_gs(self) -> None:
        """GE without a GS is silently ignored (sets current_group to None)."""
        edi = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>~"
            "GE*0*1~"
            "IEA*1*000000001~"
        )
        result = parse_edi_file(to_bytes(edi))
        assert len(result["interchanges"]) == 1
        assert len(result["interchanges"][0]["groups"]) == 0

    def test_iea_without_preceding_isa(self) -> None:
        """IEA alone fails at ISA detection since there is no ISA prefix."""
        with pytest.raises(ValueError, match="does not start with ISA"):
            parse_edi_file(to_bytes("IEA*1*000000001~"))

    def test_duplicate_isa_control_numbers(self) -> None:
        """Duplicate ISA control numbers produce two separate interchanges."""
        ic1 = SampleX12.build_interchange(control_number="000000001")
        ic2 = SampleX12.build_interchange(control_number="000000001")
        result = parse_edi_file(to_bytes(ic1 + ic2))
        assert len(result["interchanges"]) == 2
        cn1 = result["interchanges"][0]["isa_control_number"]
        cn2 = result["interchanges"][1]["isa_control_number"]
        assert cn1 == cn2 == "000000001"

    def test_empty_segment_between_terminators(self) -> None:
        """Double ~~ (empty segment) is filtered out, not stored."""
        txn = "ST*850*0001~BEG*00*NE~~CTT*1~SE*4*0001~"
        group = SampleX12.build_group(transactions=[txn])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        seg_ids = [s["segment_id"] for s in tx["segments"]]
        assert "" not in seg_ids
        assert "BEG" in seg_ids
        assert "CTT" in seg_ids

    def test_segments_outside_transaction_ignored(self) -> None:
        """Segments between GS and ST are silently ignored."""
        edi = (
            "ISA*00*          *00*          "
            "*ZZ*TESTSENDER     *ZZ*TESTRECEIVER   "
            "*231117*0041*^*00501*000000001*0*T*>~"
            "GS*PO*SENDER*RECEIVER*20231117*0041*1*X*005010~"
            "REF*PO*ORPHAN~"
            "ST*850*0001~BEG*00*NE~SE*3*0001~"
            "GE*1*1~"
            "IEA*1*000000001~"
        )
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        seg_ids = [s["segment_id"] for s in tx["segments"]]
        assert "REF" not in seg_ids

    def test_crlf_line_endings_handled(self) -> None:
        """Files with CRLF between segments parse correctly due to strip()."""
        txn = "ST*850*0001~\r\nBEG*00*NE~\r\nSE*3*0001~\r\n"
        group = SampleX12.build_group(transactions=[txn])
        edi = SampleX12.build_interchange(groups=[group])
        result = parse_edi_file(to_bytes(edi))
        tx = result["interchanges"][0]["groups"][0]["transactions"][0]
        assert tx["transaction_set_id"] == "850"
        assert tx["segments"][0]["segment_id"] == "BEG"

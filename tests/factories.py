from __future__ import annotations

"""Test data factories for draftedi-core (stdlib only, no external deps)."""


class SampleX12:
    """Builds valid X12 documents for testing the parser and ingestion."""

    @staticmethod
    def build_interchange(
        sender_id="TESTSENDER     ",
        receiver_id="TESTRECEIVER   ",
        control_number="000000001",
        usage_indicator="T",
        groups=None,
    ):
        """Build a complete ISA/IEA interchange envelope."""
        groups = groups or [SampleX12.build_group()]
        segments = [
            f"ISA*00*          *00*          *ZZ*{sender_id}*ZZ*{receiver_id}"
            f"*231117*0041*^*00501*{control_number}*0*{usage_indicator}*>~",
        ]
        for group in groups:
            segments.append(group)
        segments.append(f"IEA*{len(groups)}*{control_number}~")
        return "".join(segments)

    @staticmethod
    def build_group(
        functional_id="PO",
        sender_id="TESTSENDER",
        receiver_id="TESTRECEIVER",
        control_number="000000001",
        x12_version="005010",
        transactions=None,
    ):
        """Build a GS/GE functional group."""
        transactions = transactions or [SampleX12.build_850()]
        segments = [
            f"GS*{functional_id}*{sender_id}*{receiver_id}"
            f"*20231117*0041*{control_number}*X*{x12_version}~",
        ]
        for txn in transactions:
            segments.append(txn)
        segments.append(f"GE*{len(transactions)}*{control_number}~")
        return "".join(segments)

    @staticmethod
    def build_850(control_number="0001"):
        """Build a minimal valid 850 Purchase Order."""
        body_segments = [
            f"ST*850*{control_number}~",
            "BEG*00*NE*PO-001**20231117~",
            "PO1*1*10*EA*25.00**BP*ITEM001~",
            "CTT*1~",
        ]
        segment_count = len(body_segments) + 1  # +1 for SE itself
        body_segments.append(f"SE*{segment_count}*{control_number}~")
        return "".join(body_segments)

    @staticmethod
    def build_997(
        control_number="0001",
        ack_group_control="000000001",
        functional_id="PO",
        ack_code="A",
    ):
        """Build a minimal valid 997 Functional Acknowledgment."""
        body_segments = [
            f"ST*997*{control_number}~",
            f"AK1*{functional_id}*{ack_group_control}~",
            f"AK9*{ack_code}*1*1*1~",
        ]
        segment_count = len(body_segments) + 1
        body_segments.append(f"SE*{segment_count}*{control_number}~")
        return "".join(body_segments)

"""Issue #27 mailbox marker parsing and formatting tests."""
import unittest

from trading_lab.research.bridge_mailbox import (
    BridgeMarker,
    format_inbound_marker,
    format_outbound_marker,
    parse_bridge_marker,
)


class BridgeMailboxTests(unittest.TestCase):
    def test_parse_inbound_marker(self):
        marker = parse_bridge_marker("<!-- chatgpt-bridge:inbound update_id=12345 -->\nhello")
        self.assertEqual(marker, BridgeMarker(direction="inbound", reference="12345"))

    def test_parse_outbound_marker(self):
        text = "<!-- chatgpt-bridge:outbound reply_to=project-progress-20260921T1915Z -->"
        marker = parse_bridge_marker(text)
        self.assertEqual(
            marker,
            BridgeMarker(direction="outbound", reference="project-progress-20260921T1915Z"),
        )

    def test_invalid_field_for_direction_returns_none(self):
        self.assertIsNone(parse_bridge_marker("<!-- chatgpt-bridge:inbound reply_to=42 -->"))
        self.assertIsNone(parse_bridge_marker("<!-- chatgpt-bridge:outbound update_id=42 -->"))

    def test_absent_marker_returns_none(self):
        self.assertIsNone(parse_bridge_marker("normal issue comment without bridge marker"))

    def test_formatters_reject_blank_reference(self):
        with self.assertRaises(ValueError):
            format_inbound_marker("  ")
        with self.assertRaises(ValueError):
            format_outbound_marker("\n")

    def test_format_and_parse_round_trip(self):
        inbound = format_inbound_marker("888")
        outbound = format_outbound_marker("ticket-abc")
        self.assertEqual(parse_bridge_marker(inbound), BridgeMarker("inbound", "888"))
        self.assertEqual(parse_bridge_marker(outbound), BridgeMarker("outbound", "ticket-abc"))


if __name__ == "__main__":
    unittest.main()

"""Local Kian smoke tests for execution kernel stubs."""
import unittest

from trading_lab.execution.kernel import entry_price, exit_price


class LocalKianExecutionTests(unittest.TestCase):
    def test_buy_entry_uses_ask(self):
        self.assertEqual(entry_price("BUY", 100.0, 100.2), 100.2)

    def test_buy_exit_uses_bid(self):
        self.assertEqual(exit_price("BUY", 100.0, 100.2), 100.0)


if __name__ == "__main__":
    unittest.main()

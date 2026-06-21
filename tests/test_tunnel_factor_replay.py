import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from analysis.tunnel_factor_replay import PointInTimeMarketView, verify_seal


class TunnelFactorReplayTest(unittest.TestCase):
    def test_point_in_time_view_excludes_future_market_rows(self):
        rows = {
            "2026-06-08": {"600000": {"收盘": 10}},
            "2026-06-09": {"600000": {"收盘": 11}},
        }
        view = PointInTimeMarketView(sorted(rows), rows, "2026-06-08")
        self.assertEqual(view.dates, ["2026-06-08"])
        self.assertEqual(view.histories()["600000"][-1][1]["收盘"], 10)

    def test_signal_seal_rejects_post_hoc_changes(self):
        payload = {"rules_frozen_before_evaluation": True, "decisions": []}
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        payload["signal_seal_sha256"] = hashlib.sha256(canonical).hexdigest()
        verify_seal(payload)
        payload["decisions"].append({"next_high_return": 9.9})
        with self.assertRaises(RuntimeError):
            verify_seal(payload)


if __name__ == "__main__":
    unittest.main()

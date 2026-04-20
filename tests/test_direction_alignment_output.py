from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from src.output.direction_alignment import write_direction_alignment_output


CSV_BODY = """signal_date,ticker,signal_type,signal_direction,llm_direction,signal_price,catalyst_tag,news_tone,trade_frame_scenario,return_1d,return_5d,return_20d,evaluated_1d,evaluated_5d,evaluated_20d,conviction,action,regime,factors_json,benchmark_return_5d,alpha_5d
2026-04-10,AAPL,takeaway,bull,bull,100,earnings,bullish,base,+1.00%,+2.00%,N/A,True,True,False,58,buy,risk_on,{},+1.00%,+1.00%
2026-04-10,MSFT,takeaway,bear,bull,200,macro,bearish,base,-1.00%,-2.00%,N/A,True,True,False,44,avoid,risk_on,{},-1.00%,-1.00%
2026-04-10,TSLA,takeaway,neutral,neutral,300,other,neutral,base,+0.00%,+0.10%,N/A,True,True,False,50,watch,risk_on,{},+0.50%,-0.40%
"""


class DirectionAlignmentOutputTests(unittest.TestCase):
    def test_writes_summary_pairs_and_recent_conflicts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "output"
            data_dir = root / "data"
            data_dir.mkdir(parents=True, exist_ok=True)
            (data_dir / "signal_tracker.csv").write_text(CSV_BODY, encoding="utf-8")

            payload = write_direction_alignment_output(output_root=root, limit=10)

            self.assertEqual(payload["summary"]["total_signals"], 3)
            self.assertEqual(payload["summary"]["comparable_signals"], 3)
            self.assertEqual(payload["summary"]["agreement_count"], 2)
            self.assertEqual(payload["summary"]["conflict_count"], 1)
            self.assertEqual(payload["recent_conflicts"][0]["ticker"], "MSFT")

            written = json.loads((data_dir / "direction_alignment.json").read_text(encoding="utf-8"))
            self.assertEqual(written["summary"]["agreement_count"], 2)


if __name__ == "__main__":
    unittest.main()

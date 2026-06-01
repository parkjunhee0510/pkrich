from __future__ import annotations

import unittest
from io import StringIO

from src.utils.cli_progress import CliProgress, create_collect_only_progress, create_pipeline_progress


class CliProgressTests(unittest.TestCase):
    def test_progress_writes_step_done_and_failed_messages(self) -> None:
        stream = StringIO()
        progress = CliProgress(
            steps=[
                ("load_inputs", "설정과 입력 로드 중..."),
                ("collect", "가격/시장 데이터 수집 중..."),
            ],
            stream=stream,
        )

        progress.step("load_inputs")
        progress.step("collect", detail="AAPL, AMD")
        progress.done("파이프라인 종료")
        progress.failed("RuntimeError: example")

        self.assertEqual(
            stream.getvalue().splitlines(),
            [
                "[1/2] 설정과 입력 로드 중...",
                "[2/2] 가격/시장 데이터 수집 중... AAPL, AMD",
                "완료: 파이프라인 종료",
                "실패: RuntimeError: example",
            ],
        )

    def test_disabled_progress_writes_nothing(self) -> None:
        stream = StringIO()
        progress = CliProgress(
            steps=[("load_inputs", "설정과 입력 로드 중...")],
            enabled=False,
            stream=stream,
        )

        progress.step("load_inputs")
        progress.done("파이프라인 종료")
        progress.failed("failure")

        self.assertEqual(stream.getvalue(), "")

    def test_progress_output_errors_do_not_escape(self) -> None:
        class BrokenStream:
            def write(self, _value: str) -> None:
                raise OSError("closed")

            def flush(self) -> None:
                raise OSError("closed")

        progress = CliProgress(
            steps=[("load_inputs", "설정과 입력 로드 중...")],
            stream=BrokenStream(),
        )

        progress.step("load_inputs")
        progress.done("파이프라인 종료")
        progress.failed("failure")

    def test_pipeline_progress_includes_optional_sector_step(self) -> None:
        stream = StringIO()
        progress = create_pipeline_progress(enabled=True, with_sectors=True, stream=stream)

        for key in (
            "load_inputs",
            "collect",
            "news_context",
            "analysis",
            "decision",
            "evidence",
            "state",
            "output",
            "sectors",
            "notify",
            "finalize",
        ):
            progress.step(key)

        lines = stream.getvalue().splitlines()
        self.assertEqual(lines[0], "[1/11] 설정과 입력 로드 중...")
        self.assertEqual(lines[8], "[9/11] 섹터 탐색 출력 갱신 중...")
        self.assertEqual(lines[-1], "[11/11] 운영 리포트와 로그 마무리 중...")

    def test_collect_only_progress_uses_short_step_set(self) -> None:
        stream = StringIO()
        progress = create_collect_only_progress(enabled=True, stream=stream)

        for key in ("load_inputs", "collect", "output", "finalize"):
            progress.step(key)

        self.assertEqual(
            stream.getvalue().splitlines(),
            [
                "[1/4] 설정과 입력 로드 중...",
                "[2/4] 가격/시장 데이터 수집 중...",
                "[3/4] intraday refresh 출력 생성 중...",
                "[4/4] 운영 리포트와 로그 마무리 중...",
            ],
        )


if __name__ == "__main__":
    unittest.main()

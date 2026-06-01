from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import TextIO


ProgressStep = tuple[str, str]


@dataclass
class CliProgress:
    steps: list[ProgressStep]
    enabled: bool = True
    stream: TextIO | None = None
    _indices: dict[str, int] = field(init=False, repr=False)
    _stream: TextIO = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._indices = {key: index + 1 for index, (key, _label) in enumerate(self.steps)}
        self._stream = self.stream or sys.stderr

    def step(self, key: str, detail: str | None = None) -> None:
        if not self.enabled:
            return
        index = self._indices.get(key)
        label = next((step_label for step_key, step_label in self.steps if step_key == key), key)
        prefix = f"[{index}/{len(self.steps)}]" if index is not None else f"[-/{len(self.steps)}]"
        suffix = f" {detail}" if detail else ""
        self._write(f"{prefix} {label}{suffix}")

    def done(self, message: str) -> None:
        if self.enabled:
            self._write(f"완료: {message}")

    def failed(self, message: str) -> None:
        if self.enabled:
            self._write(f"실패: {message}")

    def _write(self, line: str) -> None:
        try:
            self._stream.write(f"{line}\n")
            self._stream.flush()
        except Exception:
            return


def create_pipeline_progress(
    *,
    enabled: bool,
    with_sectors: bool,
    stream: TextIO | None = None,
) -> CliProgress:
    steps: list[ProgressStep] = [
        ("load_inputs", "설정과 입력 로드 중..."),
        ("collect", "가격/시장/매크로 데이터 수집 중..."),
        ("news_context", "뉴스/포트폴리오 맥락 준비 중..."),
        ("analysis", "AI 분석과 앙상블 실행 중..."),
        ("decision", "공식 판단 생성 중..."),
        ("evidence", "검색 근거와 리스크 인텔 보강 중..."),
        ("state", "시그널 상태 저장 중..."),
        ("output", "Markdown/JSON 출력 생성 중..."),
    ]
    if with_sectors:
        steps.append(("sectors", "섹터 탐색 출력 갱신 중..."))
    steps.extend(
        [
            ("notify", "알림 전송과 신호 점검 중..."),
            ("finalize", "운영 리포트와 로그 마무리 중..."),
        ]
    )
    return CliProgress(steps=steps, enabled=enabled, stream=stream)


def create_collect_only_progress(*, enabled: bool, stream: TextIO | None = None) -> CliProgress:
    return CliProgress(
        steps=[
            ("load_inputs", "설정과 입력 로드 중..."),
            ("collect", "가격/시장 데이터 수집 중..."),
            ("output", "intraday refresh 출력 생성 중..."),
            ("finalize", "운영 리포트와 로그 마무리 중..."),
        ],
        enabled=enabled,
        stream=stream,
    )

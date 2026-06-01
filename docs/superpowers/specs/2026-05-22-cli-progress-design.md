# CLI Progress Design

## Goal

`python main.py` 실행 중 사용자가 현재 파이프라인 단계가 어디인지 CLI에서 바로 볼 수 있게 한다.

## Design

- 기본 CLI 실행은 진행 표시를 켠다.
- `--no-progress`를 추가해 자동화나 조용한 실행에서 끌 수 있게 한다.
- 진행 표시는 `stderr`로만 출력한다. Markdown/JSON 출력, 구조화 로그, 결정 로직, 비용 로직은 바꾸지 않는다.
- `run_pipeline()`과 `collect_only()`는 API 호출 시 기본값을 조용한 모드로 유지하고, `main.py`가 CLI 실행 여부에 맞춰 `show_progress`를 넘긴다.
- 진행 표시 실패는 파이프라인 실패로 번지지 않는다.

## User-Facing Output

기본 파이프라인은 설정, 수집, 분석, 판단, 근거 보강, 상태 저장, 출력, 알림/마무리 단계를 표시한다. `--with-sectors`가 켜지면 섹터 탐색 단계가 추가된다.

`--collect-only`는 설정, 가격/시장 수집, intraday 출력, 로그 마무리만 표시한다.

## Tests

- `main.py`가 기본적으로 `show_progress=True`를 넘기는지 확인한다.
- `--no-progress`가 `show_progress=False`를 넘기는지 확인한다.
- 진행 헬퍼가 단계/완료/실패 메시지를 `stderr` 호환 스트림에 출력하고, disabled 모드에서는 아무것도 출력하지 않는지 확인한다.
- `run_pipeline(show_progress=True)`가 주요 단계 키를 순서대로 호출하는지 확인한다.

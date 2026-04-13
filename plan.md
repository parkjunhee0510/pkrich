# 뉴스 질 개선 구현 계획

## 목표
현재 뉴스 품질을 가장 크게 끌어올릴 수 있는 5개 개선안을 우선 적용한다.  
핵심 방향은 `더 많이 모으기`보다 `더 좋은 기사만 남기기`, 그리고 `LLM에는 대표 뉴스만 전달하기`다.

---

## 1. IR RSS 확장

### 목적
공식 발표 비중을 높여 일반 기사 의존도를 낮춘다.

### 작업
- `config/watchlist.yaml`에 아래 종목의 공식 IR/뉴스룸 RSS 추가
  - `CAT`
  - `XOM`
  - `AMD`
  - `KO`
  - `T`
  - `IONQ`
  - `PLUG`
- `ir_source_names`도 함께 채워서 출력 소스명이 깔끔하게 보이도록 정리

### 영향 파일
- `config/watchlist.yaml`

### 기대 효과
- 공식 뉴스 비중 증가
- 뉴스 신뢰도 상승
- 해설 기사보다 기업 직접 발표가 더 앞에 오도록 개선

---

## 2. 뉴스 중복 클러스터링

### 목적
같은 이벤트를 여러 매체가 반복 보도하는 문제를 줄인다.

### 작업
- 제목 정규화 로직 추가
- 아래 기준으로 유사 뉴스 묶기
  - 같은 날짜
  - 유사 제목
  - 같은 핵심 키워드
- 중복 클러스터에서는 대표 기사 1건만 유지
- 필요 시 `related_count` 메타 추가

### 영향 파일
- `src/collector/news_rss.py`
- 필요 시 `src/types.py`

### 기대 효과
- 뉴스 리스트가 훨씬 덜 산만해짐
- 같은 재료를 여러 번 읽는 문제 감소
- 상단 뉴스의 밀도와 신호 품질 상승

---

## 3. Soft/SEO 기사 감점 강화

### 목적
설명형/낚시형/재가공 기사 노출을 줄인다.

### 작업
- 뉴스 랭킹 로직에서 아래 키워드 penalty 강화
  - `why`
  - `what is`
  - `explained`
  - `analysis of`
  - `stock to buy`
  - `price prediction`
- 길고 설명형인 제목도 감점
- 기존 `hard / medium / soft` 분류와 함께 가중치 반영

### 영향 파일
- `src/collector/news_rss.py`

### 기대 효과
- 상단 뉴스가 더 실제 거래 재료 중심으로 정리됨
- SEO/콘텐츠팜성 기사 비중 감소

---

## 4. LLM 입력용 대표 뉴스 세트 축소

### 목적
LLM이 중복 기사나 약한 기사에 끌리지 않게 한다.

### 작업
- analyzer로 넘길 뉴스 수를 대표 세트로 제한
- 우선순위 예시
  - 공식/하드 catalyst `1~2건`
  - 주요 시장 뉴스 `1~2건`
  - 보완 기사 `1건`
- 전체 뉴스는 output에는 남기되, LLM 입력에는 전부 넣지 않음

### 영향 파일
- `src/analyzer/research_note.py`
- 필요 시 `src/collector/news_rss.py`

### 기대 효과
- `summary`
- `key_news`
- `signal_or_takeaway`
의 선명도 향상
- token 낭비 감소
- 프롬프트 품질 안정화

---

## 5. 출력에서 뉴스 3단 구조 분리

### 목적
사용자가 뉴스 중요도를 빠르게 읽게 만든다.

### 작업
- 뉴스 출력 구조를 아래처럼 분리
  - `공식/하드 catalyst`
  - `시장 뉴스`
  - `해설/배경`
- Markdown, JSON, Web에서 같은 구조 유지
- 필요하면 각 뉴스에 `왜 중요한지` 또는 `confidence`도 추가

### 영향 파일
- `src/output/markdown.py`
- `src/output/json_export.py`
- `web/src/pages/TickerDetail.tsx`
- 필요 시 `web/src/types/index.ts`

### 기대 효과
- 같은 뉴스 수라도 체감 품질이 크게 향상
- 사용자가 `무엇이 진짜 재료인지` 더 빨리 판단 가능

---

## 추천 구현 순서

1. `IR RSS 확장`
2. `뉴스 중복 클러스터링`
3. `Soft/SEO 기사 감점 강화`
4. `LLM 입력용 대표 뉴스 세트 축소`
5. `출력 3단 구조 분리`

---

## 검증 방법

```bash
python -m unittest discover tests -v
python main.py

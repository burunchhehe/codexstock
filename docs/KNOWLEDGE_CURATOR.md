# Knowledge Curator

지식 큐레이터는 코덱스스톡의 회의, 복기, 연구, 후보 판단, 외부 신호가 계속 쌓여도 필요한 근거를 다시 찾을 수 있도록 정리하는 읽기 전용 지식 직원입니다.

## 무엇을 해결하나

기존 원장은 각각의 업무에 맞게 저장됩니다. 시간이 지나면 같은 내용이 여러 파일에 반복되고, 최신 회의와 오래된 과거장 연구가 섞이며, AI 직원이 필요한 근거를 찾기 위해 큰 파일을 처음부터 다시 읽는 문제가 생깁니다.

지식 큐레이터는 원본을 수정하지 않고 검색용 투영본만 만듭니다.

```text
원본 회의·복기·연구·후보·외부신호 원장
    -> 공개 가능한 필드만 읽기
    -> 출처·원본 위치·발생시각 보존
    -> 내용 해시로 변경·중복 판별
    -> SQLite FTS 즉시 검색
    -> 선택형 전문 엔진 인덱스
    -> AI 직원과 운영 화면에 근거 반환
```

## 정보 분류와 정리 방식

### 1. 소스 계층

| 계층 | 포함 범위 | 실행 정책 |
| --- | --- | --- |
| 상시 핵심 원장 | AI 회의, 학습 통찰, 조건검색, 당일 복기, 외부신호 검증, 후보 판단, 매매 복기, 시장 재료, 다음 장 계획 | 60초 주기로 변경 확인 |
| 연구 아카이브 | 과거장 리플레이, AI 대회, 100억 프로젝트, 워크포워드, 장기 전략 연구, 선별 Obsidian 문서 | 장후·휴장일 명시적 배치 |
| SQLite 연구 저장소 | 이름에 research, meeting, review, replay, learning, strategy, journal, memory, evidence가 포함된 연구 테이블 | 읽기 전용 투영 |

계좌, 잔고, 주문, 체결, 포지션, 토큰, 비밀번호, API 키 관련 테이블과 열은 색인 대상에서 제외합니다.

### 2. 문서 계층

각 자료는 다음 정보와 함께 저장됩니다.

- 원본 파일 경로와 파일 종류
- JSONL 줄, JSON 항목, SQLite 테이블 행 등 원본 위치
- 제목과 발생시각
- 원본 내용 해시와 민감값 제거 후 투영 해시
- 색인 시각

문서 ID는 `원본 경로 + 원본 위치`로 만들고, 내용 해시가 같으면 변경되지 않은 자료로 처리합니다. JSONL은 파일 전체를 매번 읽지 않고 마지막으로 읽은 위치 이후의 추가분만 처리할 수 있습니다.

### 3. 검색 계층

| 엔진 | 역할 | 가동 방식 | 현재 공개 상태 |
| --- | --- | --- | --- |
| SQLite FTS5 | 제목·본문 키워드와 BM25 기반 즉시 검색 | 상시 경량 | 구현·가동 |
| Qdrant | 토큰·문자 조각 feature-hash 벡터를 이용한 가벼운 유사 검색 | 상시 또는 증분 | 구현·최근 완료 |
| LlamaIndex | 긴 문서를 512 크기, 64 중첩 단위로 잘라 문서 검색 구조 생성 | 장후·필요 시 | 구현·최근 완료 |
| Graphiti | 시간 관계와 개체 연결 실험 | 요청형 무거운 작업 | 부분 실험 |
| Microsoft GraphRAG | 대규모 자료의 전역 관계 요약 실험 | 휴장일·명시 요청 | 부분 실험 |

Qdrant 투영은 현재 신경망 임베딩 모델이 아니라 재현 가능한 경량 feature-hash 방식입니다. Graphiti와 GraphRAG도 완성 기능으로 표시하지 않고 부분 실험 상태를 그대로 공개합니다.

## 자원 관리

- 장중에는 SQLite FTS와 필요한 Qdrant 증분 작업만 허용합니다.
- LlamaIndex, Graphiti, GraphRAG 같은 중·대형 작업은 장중에 자동 연기합니다.
- 무거운 전문 엔진은 동시에 하나만 실행합니다.
- 변경 문서 수와 마지막 성공 시각이 기준을 넘었을 때만 재실행합니다.
- 원본 원장은 불변이며 검색 인덱스가 주문 경로를 수정할 수 없습니다.

## 2026-07-22 실행 스냅샷

- 색인 문서: 7,871개
- 발견된 상시 소스: 23개
- 발견된 아카이브 소스: 161개
- 스케줄러: 실행 중, 스레드 정상
- Qdrant: 최근 작업 완료
- LlamaIndex: 최근 작업 완료
- Graphiti: 부분 완료
- GraphRAG: 부분 완료

위 숫자는 지식 검색 기반의 실행 상태이며 투자성과를 의미하지 않습니다.

## 주요 인터페이스

- `GET /api/knowledge-curator/status`
- `GET /api/knowledge-curator/search?q=...`
- `GET /api/knowledge-curator/engine-plan`
- `POST /api/knowledge-curator/sync`
- `POST /api/knowledge-curator/specialist`

관련 구현은 [`app/knowledge_curator.py`](../app/knowledge_curator.py), 전문 엔진 worker는 [`app/knowledge_engine_worker.py`](../app/knowledge_engine_worker.py), 회귀 테스트는 [`tests/test_knowledge_curator.py`](../tests/test_knowledge_curator.py)에서 확인할 수 있습니다.

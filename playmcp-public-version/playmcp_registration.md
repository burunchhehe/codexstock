# PlayMCP Registration Values

Use these values on the PlayMCP registration page.

## Basic Info

- Team profile: `dinho`
- MCP name: `AI 주식 리서처`
- MCP identifier: `codexstock`
- Auth: `Bearer token` if user-specific KIS/DART profiles are enabled, otherwise `No authentication` for public fallback mode
- Tool count: `20`
- Representative image: `assets/playmcp-codexstock-stock-research.png`

## Description

```text
AI 주식 리서처는 코덱스스톡 기반의 읽기 전용 주식 연구 MCP입니다. 공개 시장 데이터와 선택적 KIS/OpenDART 조회 데이터를 바탕으로 시장 분위기, 업종·테마, 종목 조회, 상승·하락 종목, 뉴스·재료, 공시·재무, 후보 발굴·비교, AI 역할별 의견, 리스크 점검, 전략 검증, 장마감 복기와 학습 요약을 제공합니다. 실전 주문, 계좌·잔고·체결, 개인 매매기록에는 접근하지 않으며 모든 결과는 투자 연구 참고자료입니다.
```

Short version:

```text
공개 시장 데이터와 선택적 KIS/OpenDART 조회 데이터를 활용해 시장 요약, 종목 후보 발굴, 뉴스·공시·재무 점검, 후보 비교, AI 의견, 리스크, 전략 검증, 장마감 복기와 학습 요약을 제공하는 읽기 전용 주식 연구 MCP입니다. 실전 주문과 계좌 조회는 제공하지 않습니다.
```

## Conversation Examples

```text
오늘 강한 업종과 테마를 알려줘
```

```text
후보 종목들을 근거와 리스크로 비교해줘
```

```text
삼성전자의 재료와 리스크를 점검해줘
```

## Endpoint

```text
https://<your-public-host>/mcp
```

Do not register an expiring quick-tunnel hostname for production review. Use a stable HTTPS endpoint that you control.

## User API Connection

Recommended structure:

1. User opens `https://<your-public-host>/connect`.
2. User enters KIS App Key, KIS App Secret, and OpenDART API Key.
3. Server stores the keys in an encrypted per-user credential profile.
4. Server shows a one-time connection token.
5. User registers only this value in PlayMCP:

```text
Authorization: Bearer <user_bearer_token>
```

Status check:

```text
https://<your-public-host>/connect/status?token=<user_bearer_token>
```

If `user_profile_active=true`, the user's read-only KIS/DART profile is active.

## Safety Notice

```text
AI 주식 리서처는 투자 연구 참고용 정보 서비스이며 투자 자문, 매매 추천, 실전 주문을 제공하지 않습니다. 모든 결과는 공개 데이터 기반 연구 보조 자료이고, 최종 투자 판단과 책임은 사용자에게 있습니다.
```

## Safety Boundaries

- No live order submission
- No account lookup
- No balance lookup
- No fill lookup
- No private trading journal access
- No raw API key fields in MCP tool parameters
- Optional KIS/OpenDART keys are stored only through the encrypted `/connect` profile flow
- Public MCP remains read-only even when user credentials are active

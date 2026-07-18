# PlayMCP Registration Values

Use these values on the PlayMCP registration page.

## Basic Info

- Team profile: `dinho`
- MCP name: `AI 주식 리서처`
- MCP identifier: `codexstock`
- Auth: `No authentication`
- Tool count: `20`
- Representative image: `assets/playmcp-codexstock-stock-research.png`

## Description

Korean draft for the PlayMCP form:

```text
AI 주식 리서처는 코덱스스톡 기반의 읽기 전용 주식 리서치 MCP입니다. 공개 시장 데이터와 선택적 KIS/OpenDART 조회 데이터를 바탕으로 시장 분위기, 강한 업종과 테마, 종목 조회, 상승·하락 종목, 뉴스·재료 맥락, 공시·재무 점검, 후보 발굴, 후보 비교, AI 직원별 의견, 리스크 점검, AI 종합 리서치, 전략 검증, 장마감 복기와 학습 요약을 제공합니다. 실전 주문, 계좌·잔고·체결 조회, API 키·토큰 및 개인 매매기록에는 접근하지 않습니다. 모든 결과는 투자 연구와 정보 제공을 위한 참고자료이며 매매 추천이나 투자 자문이 아닙니다. 자세한 기능과 공개 범위는 GitHub에서 확인할 수 있습니다: https://github.com/burunchhehe/codexstock
```

Shorter Korean draft if the form feels too tight:

```text
AI 주식 리서처는 코덱스스톡 기반의 읽기 전용 주식 리서치 MCP입니다. 공개 시장 데이터와 선택적 KIS/OpenDART 조회 데이터로 시장 분위기, 업종·테마, 종목 조회, 상승·하락 종목, 뉴스·재료, 공시·재무, 후보 비교, AI 의견, 리스크, 전략 검증, 장마감 복기와 학습 요약을 제공합니다. 실전 주문, 계좌·잔고·체결, 토큰, 개인 매매기록에는 접근하지 않으며 매매 추천이나 투자 자문이 아닙니다.
```

English draft:

```text
AI Stock Researcher is a read-only stock research MCP powered by CodexStock. It combines public market snapshots, optional KIS/OpenDART read-only data, sector/theme checks, stock lookup, mover scans, news/catalyst context, disclosure and fundamental checks, candidate discovery, candidate comparison, AI staff viewpoints, risk checks, AI research consensus, strategy validation, post-market review, and learning summaries. It does not access live orders, accounts, balances, fills, tokens, or private trading journals.
```

## Conversation Examples

```text
오늘 강한 업종과 테마 알려줘
```

```text
후보 종목들을 근거와 리스크로 비교해줘
```

```text
이 종목이 왜 움직였는지 재료 점검해줘
```

## Safety Notice

```text
AI 주식 리서처는 투자 연구 참고용 정보 서비스이며 투자 자문, 매매 추천, 실전 주문을 제공하지 않습니다. 모든 결과는 공개 데이터 기반의 연구 보조 자료이고, 최종 투자 판단과 책임은 사용자에게 있습니다.
```

## Endpoint

Fill this after hosting the public read-only MCP server over HTTPS.

```text
https://<your-public-host>/mcp
```

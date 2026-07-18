# 친구용 코덱스스톡 시작 가이드

코덱스스톡은 각자 본인의 API 키와 본인의 계좌로 실행해야 합니다. 만든 사람의 API 키, 계좌번호, 텔레그램 토큰은 절대 공유하면 안 됩니다.

## 1. 친구에게 전달하기 전

1. 만든 사람은 원본 폴더를 그대로 압축하지 않습니다.
2. PowerShell에서 아래 명령으로 친구용 폴더를 만듭니다.

```powershell
.\prepare_friend_release.ps1
```

3. 생성된 `dist\CodexStock-Friend` 폴더만 전달합니다.
4. 프로그램의 `설정` 탭에서 `친구 배포 준비도`를 확인합니다.
5. 친구용 폴더 안에 `.env`, `.env.local`, KIS 토큰, 실전 주문 로그, 텔레그램 기록이 있으면 전달하지 않습니다.
6. 개발자나 GPT에게 현재 기술 수준을 설명해야 하면 `CODEXSTOCK_TECHNICAL_BRIEF.md` 문서를 함께 보여줍니다.
7. 친구용 `data`와 `reports` 폴더에는 안내용 `README.txt`만 있어야 합니다. 원본 사용자의 학습 기록, 매매 기록, 계좌 기록은 포함하지 않습니다.

## 2. 친구가 처음 해야 할 일

1. 받은 폴더를 원하는 위치에 압축 해제합니다.
2. `.env.example` 파일을 복사해서 `.env.local` 이름으로 저장합니다.
3. `.env.local`에 본인이 직접 발급받은 API 키와 계좌 정보를 넣습니다.
4. 처음에는 아래 안전값을 유지합니다.

```env
LIVE_TRADING=false
KIS_READONLY=true
KIS_USE_MOCK=true
```

5. 프로그램 실행 후 대시보드와 설정 탭에서 API 연결 상태를 확인합니다.

## 3. 각자 직접 발급해야 하는 것

- 한국투자증권 KIS API: 시세, 계좌 조회, 모의/실전 주문
- OpenDART API: 공시와 재무제표
- KRX API: 국내 시장, 종목, 거래 데이터
- 한국은행 ECOS API: 금리, 환율, 거시지표
- FRED API: 미국 금리, 고용, 물가 등 거시지표
- 텔레그램 Bot Token과 Chat ID: 보고와 명령 수신
- OpenAI API 또는 Ollama 로컬 모델: AI 분석 엔진

## 4. 절대 공유하면 안 되는 파일

- `.env`
- `.env.local`
- `data/kis_token_real.json`
- `data/kis_token_mock.json`
- `data/telegram_offset.json`
- `data/live_order_submits.jsonl`
- `data/live_position_decisions.jsonl`
- `data/telegram_outbox.jsonl`
- `data/telegram_dispatch.jsonl`
- API Secret, 계좌번호, 텔레그램 토큰이 들어간 모든 파일

## 5. 실전매매를 켜기 전

실전매매는 친구 본인이 충분히 이해하고 직접 켤 때만 사용합니다.

- `LIVE_TRADING=true`
- `KIS_READONLY=false`
- `KIS_USE_MOCK=false`
- KIS 실전 App Key, App Secret, 계좌번호 입력
- 프로그램 안의 주문 잠금, 1일 손실 제한, 종목별 한도, 주문 횟수 제한 확인
- 처음에는 반드시 1주 단위의 작은 테스트만 실행

## 6. 한 줄 설명

코덱스스톡은 AI 주식 연구, 백테스트, 모의훈련, 텔레그램 보고, 한국투자증권 연동을 목표로 하는 로컬 주식 프로그램입니다. 수익을 보장하지 않으며, 모든 API와 계좌는 각자 본인 것으로 설정해야 합니다.

## 7. 개발자용 기술 문서

- `CODEXSTOCK_TECHNICAL_BRIEF.md`: 현재 구현된 기술 스택, API, 데이터 저장 방식, 응답 시간, 검증 결과, 부족한 점을 정리한 문서입니다.
- 이 문서는 API 키나 계좌번호를 담지 않습니다.
- 친구나 개발자가 "어디까지 된 프로그램인지" 빠르게 판단할 때 이 문서를 먼저 보면 됩니다.

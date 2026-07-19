# 코덱스스톡 내부 개발자

내부 개발자는 코덱스스톡 본체와 분리된 운영 복구 사이드카다. 본체를
`import`하지 않고 로컬 HTTP로 상태를 읽으며, 진단·사건·리포트·GPT 자문은
활성 데이터 루트 아래의 개별 JSON 파일로 보존한다.

## 실행 구조

- `CodexStock-Watchdog`: 기존 독립 감시자. 본체 생존 감시와 검증된 재시작 담당
- `CodexStock-InternalDeveloper`: 1분마다 내부 개발자 1회 주기 실행
- `app/internal_developer_service.py`: HTTP 관찰, 작업 진행 판정, 안전 복구 조정
- `app/internal_developer_engine.py`: 결정론적 분류·정책·실행·재검증
- `app/internal_developer_store.py`: 원자적 JSON 저장, 리포트, 자문, 플레이북
- `app/codexstock_mcp_server.py`: 본체가 중단돼도 GPT가 저장소를 직접 조회하는 MCP 연결

스케줄러는 숨김 실행되며 `IgnoreNew`와 파일 잠금을 함께 사용한다. 한 주기가
길어지면 다음 주기는 겹쳐 실행되지 않는다.

## 자동 허용 범위

- 기능 건강 캐시 강제 재검증
- resident/read-only 계약이 확인된 KIS 외부 엔진 재연결
- `FAILED` 또는 `INTERRUPTED` 연구 작업의 최대 1회 재시도
- 내부 개발자 자신의 파생 상태 원장 재구성
- 등록된 SQLite DB의 읽기 전용 잠금 탐지
- 5회 연속 비-busy 생존 실패 후 기존 감시자용 재시작 요청 파일 작성
- 장애·복구·외부 자문용 JSON 및 텔레그램/실행기 텍스트 리포트 작성

DB 탐지는 `mode=ro`, `PRAGMA query_only=ON`만 사용한다. WAL, SHM, 잠금 파일을
삭제하거나 잠금을 보유한 프로세스를 종료하지 않는다.

## 자동 금지 범위

- 실전 주문 또는 주문 승인
- API 키·토큰·계정 자격증명 변경
- 리스크 한도 완화 또는 안전장치 우회
- 코드·소스 파일 자동 수정
- 보안·인증 설정 해제
- 프로세스 강제 종료
- DB/WAL/SHM/잠금 파일 삭제

재시작도 내부 개발자가 직접 수행하지 않는다. 정확한
`runtime/codexstock_restart_request.json`만 만들고, 기존 감시자가 PID·포트·명령행과
연구 작업 계약을 다시 검증한 뒤 처리한다.

## 장시간 작업 처리

- busy이며 진행 서명이 바뀌면 정상 진행으로 판단하고 모든 재시작을 유예한다.
- busy 상태가 5분 이상 정체되면 `BUSY_STALLED` 리포트만 작성한다.
- 정체 상태에서는 재시작 요청을 만들지 않는다.
- 일반 생존 실패는 busy가 아닌 경우에만 누적하며 5회 미만에는 재시작하지 않는다.

일시적인 생존 실패도 감사용 사건과 리포트는 삭제하지 않는다. 이후 모든 읽기 전용
진단이 정상인 주기가 확인되면 재시작을 요청하지 않은 사건은
`RECOVERED_UNREVIEWED`로 전환한다. 이때 운영 상태는 다시 `healthy`가 되지만,
사람이나 GPT가 과거 리포트를 확인할 수 있도록 `attention_required`는 유지된다.

재시작을 요청한 사건은 더 엄격하게 처리한다. 감시자가 소유한 요청 파일이 남아
있거나 현재 PID를 확인할 수 없으면 절대 복구 완료로 표시하지 않는다. 요청 파일이
소비된 뒤 3회 연속 완전 정상 주기를 통과해야 `RECOVERED_UNREVIEWED`가 되며, PID가
바뀌었을 때만 `restart_verified: true`로 기록한다. PID가 같으면 재시작 성공이라고
주장하지 않고 `service_restored_without_verified_restart`로 기록한다.

## GPT 외부 자문 흐름

코덱스스톡이 GPT를 능동 호출하지 않는다. 사용자가 GPT에게 상태를 물으면 GPT가
MCP를 통해 로컬 JSON 저장소를 읽는다. 따라서 코덱스스톡에서 API 호출 비용이
발생하는 구조가 아니다.

1. 내부 개발자가 복구하지 못한 사건과 리포트를 저장한다.
2. GPT가 MCP의 brief/incident/report 도구로 내용을 읽는다.
3. GPT가 `codexstock_submit_developer_advice`로 자문과 구조화된 제안을 저장한다.
4. 저장 직후에는 `execution_authorized: false`, `execution_performed: false`다.
5. 다음 내부 개발자 주기에서 자유 텍스트는 무시하고 구조화된 action만 다시 검증한다.
6. 로컬에 미리 등록된 안전 핸들러만 실행하고 결과를 재검증한다.
7. 성공한 복구만 `RECOVERED_UNREVIEWED`와 검증 플레이북으로 남긴다.

GPT가 제안해도 재시작은 자동 적용하지 않는다. 재시작은 오직 내부 생존 판정의
5회 실패 규칙으로만 요청된다. 주문·키·리스크·코드·보안 관련 자문은 격리된다.

MCP 내부 개발자 도구:

- `codexstock_internal_developer_status`
- `codexstock_internal_developer_component_status`
- `codexstock_internal_developer_list_incidents`
- `codexstock_internal_developer_get_incident`
- `codexstock_internal_developer_latest_report`
- `codexstock_internal_developer_brief`
- `codexstock_internal_developer_activity`
- `codexstock_internal_developer_readonly_diagnostics`
- `codexstock_submit_developer_advice`

일반 `codexstock_status`에도 내부 개발자의 미확인 주의사항이 자동 첨부된다.

## 파일 위치

기본 활성 데이터 루트:

```text
%LOCALAPPDATA%\CodexStock\data\internal_developer\
```

주요 파일:

```text
state.json                       전체 상태와 주의 필요 여부
index.json                       개별 원본 JSON에서 재구성 가능한 파생 색인
service_state.json               연속 실패·진행 서명·1회 재시도 원장
service_heartbeat.json           최근 1분 주기 결과
incidents\INC-*.json             사건 원본
reports\REP-*.json               리포트 원본
advice\ADV-*.json                GPT 자문과 적용 결과
events\EVT-*.json                감사 이벤트
playbooks\PB-*.json              재검증된 안전 복구 증거
telegram\latest_report.txt       텔레그램 표시용 리포트
launcher\latest_report.txt       실행기 표시용 리포트
scheduler.log                    스케줄러 실행 기록
```

재시작 요청은 데이터 루트가 아니라 저장소의 다음 단일 경로만 사용한다.

```text
runtime\codexstock_restart_request.json
```

## 운영 확인

스케줄러 확인:

```powershell
Get-ScheduledTask -TaskName CodexStock-InternalDeveloper
Get-ScheduledTaskInfo -TaskName CodexStock-InternalDeveloper
```

안전한 1회 수동 확인:

```powershell
powershell.exe -NoProfile -File .\tools\run_internal_developer.ps1
```

등록 계약과 재설치 방법은 `docs/INTERNAL_DEVELOPER_SCHEDULER.md`를 참고한다.

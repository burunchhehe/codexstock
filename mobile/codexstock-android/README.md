# 코덱스스톡 Android 조종석

PC에서 24시간 실행되는 코덱스스톡을 휴대폰으로 확인하는 개인용 앱입니다. 증권사 API 키, 계좌 인증정보, 텔레그램 토큰은 PC 밖으로 내보내지 않습니다.

## 휴대폰에서 할 수 있는 일

- 본체, 매매 파이프라인, 외부 실행기, 내부 개발자 상태 확인
- 현재 매매 집중도와 연구 집중도 확인
- AI 직원의 현재 업무 확인
- 후보 종목과 선정·차단 근거 확인
- 오늘의 실전 전송, 차단, 후보, Paper 기록 확인
- 계좌의 종목별 보유·손익 요약 확인
- 하위 엔진 준비도와 최근 성공 시각 확인
- 장애, 복구, GPT 자문 기록 확인
- 읽기 전용 비서와 대화
- 정확한 확인 문구를 입력한 긴급정지

모바일 API에는 자동매매 시작, 긴급정지 해제, 위험 한도 완화, 개별 실주문 기능이 없습니다.

## 휴대폰 연결

가장 쉬운 방법은 저장소 루트에서 다음 명령을 한 번 실행하는 것입니다.

```powershell
.\mobile\prepare_phone.ps1
```

이 명령은 PC 본체 상태, APK 위치, Tailscale 준비 여부를 확인하고 10분짜리 일회용 코드를 만듭니다.

1. PC와 휴대폰에 Tailscale을 설치하고 같은 개인 네트워크에 연결합니다.
2. PC의 로컬 포트 `8765`를 Tailscale Serve HTTPS로 연결합니다.
3. PC에서 10분 동안 한 번만 쓸 수 있는 8자리 페어링 코드를 만듭니다.

```powershell
python app/mobile_pairing_cli.py create
```

4. 휴대폰 앱의 설정에서 HTTPS 주소, 8자리 코드, 기기 이름을 입력합니다.
5. 페어링이 끝나면 기기 전용 토큰만 휴대폰에 저장됩니다. 원본 API 키와 계좌 비밀값은 전송되지 않습니다.

등록 기기 확인과 해제:

```powershell
python app/mobile_pairing_cli.py list
python app/mobile_pairing_cli.py revoke <device_id>
```

## APK 빌드

저장소 루트에서 다음 명령을 실행합니다.

```powershell
.\mobile\build_android.ps1
```

완성 파일은 `dist/CodexStock-Mobile-debug.apk`에 생성됩니다.

개발 명령:

```powershell
cd mobile/codexstock-android
npm install
npx cap sync android
cd android
.\gradlew.bat assembleDebug
```

## 보안 원칙

- 페어링 코드는 짧게 만료되고 한 번만 사용할 수 있습니다.
- 서버에는 모바일 토큰의 SHA-256 해시만 저장됩니다.
- 읽기 API는 기기 토큰이 없으면 `401`을 반환합니다.
- 긴급정지는 가능하지만 모바일에서 해제할 수 없습니다.
- 서비스 워커는 정적 화면만 캐시하며 API 응답과 개인 데이터를 캐시하지 않습니다.
- Android 백업, 평문 HTTP, 혼합 콘텐츠, WebView 디버깅은 차단합니다.

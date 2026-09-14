# Stock Radar Kiwoom — 2026 프리마켓 대응판

키움 REST API의 **조회 전용** 기능으로 장 시작 전 후보를 점수화하고 GitHub Pages에 표시합니다. 매수·매도 주문 코드는 포함하지 않습니다.

## 왜 08:30 조건을 바꿨나

2026년 9월 시장 운영시간 확대로 07:00부터 쌓이는 프리마켓 정보가 중요해졌습니다. 따라서 과거 일봉의 RSI 과매도만 보는 방식 대신 아래 순서로 동작합니다.

1. 07:00 KST 1차 프리마켓 스냅샷
2. 08:30 KST 예상체결·거래량·호가·체결강도·거래대금·수급 결합
3. 누락 시 08:40/08:50 재시도
4. 결과가 비어도 기존 정상 파일을 보존

기본 점수 비중은 예상체결 등락 24, 예상체결량 18, 호가 불균형 16, 체결강도 14, 거래대금 14, 외국인·기관 8, 시장상태 6입니다. 갭은 +0.5~+5.0%만 허용해 과열 추격을 줄였습니다. 이 값은 수익 보장이 아니라 검증을 시작하기 위한 보수적 기본값입니다.

## 한 번에 설치

1. GitHub Desktop에서 **File → Clone repository → GitHub.com**을 열고 `nnniiixoxo/Stock-Radar-GPT`를 복제합니다.
2. 이 ZIP을 압축 해제합니다.
3. PowerShell을 열어 다음을 실행합니다.

   `powershell -ExecutionPolicy Bypass -File .\install-to-repo.ps1 -RepoPath "복제한 Stock-Radar-GPT 폴더 전체 경로"`

4. GitHub Desktop에서 Summary에 `Replace with Kiwoom premarket edition` 입력 → **Commit to main** → **Push origin**.

## 키 등록(채팅이나 코드에 키를 적지 마세요)

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret**에서 아래 두 개를 만듭니다.

- `KIWOOM_APP_KEY`
- `KIWOOM_SECRET_KEY`

그 다음 **Actions → Market screen 07:00 and 08:30 KST → Run workflow**를 한 번 실행합니다. Pages는 **Settings → Pages → Source: GitHub Actions**로 둡니다.

## 정상 판정

- Actions 왼쪽에는 `Market screen 07:00 and 08:30 KST`, `Deploy GitHub Pages` 두 개만 보여야 합니다.
- 테스트와 조회가 완료되면 둘 다 초록색 체크가 됩니다.
- 사이트: `https://nnniiixoxo.github.io/Stock-Radar-GPT/`

## 안전장치

- 주문 API 경로 자체를 허용 목록에 넣지 않았습니다.
- API 비정상·빈 데이터·휴장일에는 빈 배열 인덱싱을 하지 않습니다.
- 조회 하나가 실패해도 다른 신호를 계속 수집하고 경고에 기록합니다.
- 새 결과가 전혀 없으면 마지막 정상 결과를 덮어쓰지 않습니다.


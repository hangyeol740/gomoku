# 오목 선생님

PC 중심의 Streamlit 렌주 학습 사이트. 기존 **Rapfi** 엔진과 **BAZE `gpt-6-luna`**를 연결합니다. 강화학습은 포함하지 않습니다.

## 기능

- 클릭/키보드로 두는 15×15 판, 흑·백 선택, AI 대국, 기권
- 흑 쌍삼·쌍사·장목 검사, 흑 정확한 5목·백 5목 이상 승리
- 매 수 아래에 흑/백 가로 승률 막대
- 질문할 때만 BAZE 호출, 현재 국면과 직전 수의 엔진 분석으로 해설
- 질문 후 추천 위치 번호, 공격·방어 색상, 연속 위협 연결선
- 종료 후 양측 정확도·좋은 수/보통 수/나쁜 수/이상한 수 통계
- 한 수씩 복기, 기보 JSON 다운로드·검증 후 가져오기, 다시 분석
- 비로그인 이용, Google 로그인, 계정별 대국·해설 저장/불러오기/삭제

## 로컬 실행

Python 3.12 권장. Linux에서 C++ 컴파일러와 make가 필요합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

http://localhost:8501 에서 실행됩니다. 첫 실행에는 고정 리비전 Rapfi 소스를 받아 `.cache/rapfi`에 컴파일하므로 수 분이 걸릴 수 있습니다. 이후에는 캐시를 재사용합니다. 외부 가중치 없이 Rapfi 내장 classical 평가를 사용합니다. 기존 실행 파일을 쓰려면 `RAPFI_PATH` 환경변수에 절대 경로를 설정하세요. 실패하면 앱에 안내와 재시도 버튼이 표시됩니다.

## Secrets

`.streamlit/secrets.toml.example`을 참고해 로컬 `.streamlit/secrets.toml` 또는 Streamlit Community Cloud의 **App settings → Secrets**를 작성합니다. 실제 키는 Git에 포함하지 않습니다.

### 1. BAZE

```toml
BAZE_API_KEY = "실제 BAZE 키"
BAZE_MODEL = "gpt-6-luna"
```

서버에서 `https://api.baze.co/v1/gateway/chat/completions/`로 Bearer 인증 요청합니다. 환경변수도 지원합니다. 키가 없으면 대국과 엔진 가이드는 가능하지만 자연어 AI 해설은 활성화되지 않습니다. 질문할 때 해당 기보·분석과 최근 대화가 BAZE로 전송되며 키 발급 계정에 사용료가 청구됩니다. 자동 재시도는 하지 않습니다.

### 2. Google 로그인

Google Cloud Console → APIs & Services → OAuth consent screen에서 앱을 구성하고, Credentials에서 **OAuth client ID / Web application**을 만듭니다. 테스트 상태일 때는 테스트 사용자를 등록하고, 공개 이용 시 앱 게시 상태와 동의 화면을 확인하세요.

Authorized redirect URIs에 아래 주소를 등록합니다.

- 로컬: `http://localhost:8501/oauth2callback`
- 배포: `https://YOUR-APP.streamlit.app/oauth2callback`

Secrets의 `redirect_uri`와 Google에 등록한 주소는 정확히 같아야 합니다.

```toml
[auth]
redirect_uri = "https://YOUR-APP.streamlit.app/oauth2callback"
cookie_secret = "충분히 긴 무작위 문자열"
client_id = "Google OAuth client ID"
client_secret = "Google OAuth client secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

cookie secret 생성: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
로그인은 Streamlit의 OIDC 검증을 사용하고, 서버에서 검증된 issuer + Google subject의 해시를 기록 소유자로 사용합니다. 이메일이나 브라우저가 보내는 임의 사용자 ID를 소유자로 사용하지 않습니다.

### 3. 영구 기록 DB

배포 환경의 파일시스템은 재시작/재배포로 초기화될 수 있습니다. **영구 저장에는 외부 PostgreSQL이 필요합니다.** Supabase Postgres도 사용할 수 있으며 별도 Supabase Auth 설정은 필요하지 않습니다.

1. PostgreSQL DB를 준비합니다.
2. SQL Editor에서 `sql/schema.sql`을 한 번 실행합니다.
3. 서버용 DB 접속 문자열을 Secrets의 **최상단**에 추가합니다. `[auth]` 아래에 넣으면 auth 설정으로 들어가므로 주의하세요.

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/postgres?sslmode=require"
```

Supabase는 Connect의 pooler 연결 문자열을 사용하고, 비밀번호 특수문자는 URL 인코딩합니다. 이 키는 서버 전용입니다. 앱은 모든 조회/수정/삭제에 로그인 소유자 조건을 강제합니다. 테이블은 RLS를 켜고 공개 API 정책은 열지 않습니다. Streamlit 서버에는 테이블 접근 권한이 있는 DB 계정을 연결합니다.

DATABASE_URL이 없으면 로컬 SQLite(`data/games.sqlite3`)로 동작하며 영구 저장이 아님을 표시합니다. 게스트 기록은 세션 동안 유지되며 JSON 다운로드로 보관할 수 있습니다. 로그인은 새 세션을 시작할 수 있으므로 진행 중 게스트 대국은 로그인 전에 다운로드하세요. 로그인 사용자는 ‘계정에 기록 저장’ 버튼으로 저장하며, 진행 중인 대국도 저장해 이어둘 수 있습니다.

## Streamlit Community Cloud 배포

1. 코드를 GitHub `hangyeol740/gomoku`의 `main` 브랜치에 커밋·푸시합니다.
2. https://share.streamlit.io 에서 Create app → 해당 저장소 선택.
3. Main file path를 **`streamlit_app.py`**, Python을 **3.12**로 설정합니다.
4. Advanced settings → Secrets에 BAZE/DB/Google 설정을 입력합니다.
5. Google redirect URI를 배포 주소에 맞춥니다.
6. Deploy를 누릅니다. `requirements.txt`, `packages.txt`가 의존성을 설치합니다.

코드는 공개 배포용으로 준비되어 있지만 실제 GitHub 푸시·Community Cloud 배포·Google 프로젝트 등록·DB 생성은 별도 작업입니다. 계정 자격 증명 없이 외부 서비스가 자동으로 만들어지지는 않습니다.

## 엔진과 분석의 해석

- 엔진: [Rapfi](https://github.com/dotb1ue/rapfi), 고정 리비전 `1387d11312190ec66665d361ff07a7c70221b78a`.
- 현재 최선 1개는 Rapfi 탐색 결과입니다. 2·3번 가이드는 **형태 참고(미탐색)**이며 엔진 순위라고 표시하지 않습니다.
- 흑/백 승률은 Rapfi WINRATE를 차례에 맞게 변환합니다. 초기값 50%는 중립 표시입니다. 한 수 즉시 승리는 규칙으로 확인합니다. 평가가 없는 국면은 미평가로 표시합니다.
- 실전 통계로 보정된 승률이 아니며 내장 classical 평가·제한 시간 탐색의 추정치입니다.
- 승률 손실 ≤3%p 좋은 수, 3~10%p 미만 보통 수, 10~25%p 미만 나쁜 수, ≥25%p 또는 즉시 승리/필수 방어 누락은 이상한 수.
- 수 정확도는 `100 × exp(-승률손실/20)`의 평균. 엔진 최선과 일치하면 손실 0으로 처리합니다. 기권은 수 평가에 포함하지 않습니다. 탐색 오차가 있으며 공식 기력 등급이 아닙니다.
- AI는 동일한 엔진 최선 수를 두므로 AI 정확도가 높게 나오는 것이 자연스럽습니다.
- 금수는 `renju==0.1.0`의 재귀 판정기를 사용합니다. 정확한 흑 5목이 동시에 생기면 승리를 우선합니다. 클릭한 금수는 착수하지 않고 거절하는 학습용 방식입니다. 스왑·정식 오프닝 규정은 적용하지 않습니다.
- 연결선은 3개 이상 **연속된** 돌을 설명합니다. 모든 끊긴 위협 패턴의 완전한 시각화는 아닙니다.

## 검증

```bash
python -m unittest discover -s tests -v
```

`RAPFI_PATH`가 있으면 실제 엔진의 합법 수·즉시 승리 테스트도 실행합니다. BAZE 테스트는 모의 응답이며 실제 키를 사용한 유료 호출은 별도입니다.

## 파일 구조

```text
streamlit_app.py             대국·채팅·복기·인증 화면
gomoku/rules.py              렌주 규칙 어댑터
gomoku/engine.py             Rapfi 자동 준비와 프로세스 통신
gomoku/game.py               대국·분석·기보 검증
gomoku/teacher.py            BAZE 채팅 선생님
gomoku/storage.py            PostgreSQL/SQLite 계정별 기록
gomoku/board_component/      의존성 없는 Canvas Streamlit 컴포넌트
sql/schema.sql              외부 DB 초기화
tests/                      규칙·기보·DB·엔진·채팅 테스트
```

Rapfi는 GPL-3.0-or-later이며 소스·라이선스는 첫 실행 시 내려받은 소스 폴더에도 보관됩니다. 이 저장소에는 Rapfi 바이너리/가중치를 포함하지 않습니다. `renju`는 MIT 라이선스입니다. 자세한 출처는 `THIRD_PARTY.md`를 참고하세요.

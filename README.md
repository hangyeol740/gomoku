# 렌주 오목 선생님

Streamlit 기반 오목 학습 사이트를 위한 프로젝트입니다.
현재는 BAZE 채팅 연결 모듈을 구현한 초기 단계이며, 대국 화면·오목 엔진·로그인·복기는 아직 구현 전입니다.

## BAZE 채팅 설정

- 기본 모델: `gpt-6-luna`
- API: `https://api.baze.co/v1/gateway/chat/completions/`
- 인증: Bearer API 키
- OpenCode 설정과 별개로 사이트 서버에서만 API를 호출합니다.

로컬에서는 `.streamlit/secrets.toml.example`을 `.streamlit/secrets.toml`로 복사한 뒤 키를 입력합니다.
Streamlit Community Cloud에서는 앱 설정의 Secrets에 다음 내용을 입력합니다.

```toml
BAZE_API_KEY = "실제 키"
BAZE_MODEL = "gpt-6-luna"
```

실제 키 파일은 Git에서 제외됩니다. API 키를 README나 소스 코드에 넣지 마세요.
환경변수 `BAZE_API_KEY`, `BAZE_MODEL`도 지원하며 전달한 Secrets 설정이 우선합니다.

향후 Streamlit 채팅 제출 처리에서 다음과 같이 사용합니다.

```python
from gomoku.teacher import BazeTeacher, TeacherError

teacher = BazeTeacher.from_settings(st.secrets)
try:
    answer = teacher.explain(question, position, history)
except TeacherError as error:
    st.error(str(error))
```

`position`에는 현재 판·기보·차례·좌표 체계와 엔진 분석을 전달합니다.
엔진 분석이 없으면 일반 원리만 설명하도록 지침을 전달합니다.
추천 표시와 금수 판단은 언어 모델의 답변이 아니라 엔진 결과로 구현할 예정입니다.
자동 API 재시도는 하지 않으며 사용자가 질문을 제출할 때만 호출해야 합니다.
API 사용료는 키를 발급한 BAZE 계정에 청구됩니다.

## 검증

Python 3.10 이상에서 별도 의존성 없이 연결 모듈을 검사할 수 있습니다.

```bash
python3 -m unittest discover -s tests -v
```

테스트는 모의 응답을 사용합니다. 실제 키를 사용한 인증·모델 접근 확인은 별도로 필요합니다.

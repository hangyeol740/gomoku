"""실행: streamlit run streamlit_app.py"""
import copy
import hashlib
import json
import os
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from gomoku.engine import analyze, EngineError
from gomoku.game import new_game, play, branch_play, review_move, export_game, import_game
from gomoku.rules import board_at, coord, threat_lines, winning_moves
from gomoku.storage import GameStore
from gomoku.teacher import BazeTeacher, TeacherError

st.set_page_config(page_title="오목 선생님", page_icon="⚫", layout="wide")
st.markdown("""<style>
.block-container{max-width:1420px;padding-top:2rem}h1{letter-spacing:-1.5px}div[data-testid="stMetric"]{background:white;padding:16px;border-radius:12px}div[data-testid="stChatMessage"]{border-radius:14px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:3px;color:#18745c}.winbar{display:flex;height:30px;border-radius:8px;overflow:hidden;border:1px solid #cdd6cc}.winbar span{display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;white-space:nowrap}button{min-height:38px}
[data-stale="true"], [data-stale="true"] > *{opacity:1 !important;filter:none !important;transition:none !important}
[data-testid="stStatusWidget"], [data-testid="stAppRunningIndicator"]{display:none !important}
</style>""", unsafe_allow_html=True)

try:
    settings = st.secrets.to_dict()
except FileNotFoundError:
    settings = {}

board_widget = components.declare_component("renju_board", path=str(Path(__file__).parent / "gomoku/board_component"))


@st.cache_data(max_entries=512, show_spinner=False)
def analysis_for(moves, budget):
    return analyze(moves, budget)


def terminal_analysis(game):
    return {"engine": "대국 결과", "best_move": None, "black_winrate": {1: 1., 2: 0., 3: .5}[game["result"]],
            "guides": [], "winning_moves": [], "opponent_winning_moves": [], "depth": 0}


def fill_analysis(game, budget):
    # 인덱스 i = i수를 둔 뒤의 국면. 미완성 상태도 재실행 시 이어서 분석한다.
    while len(game["analyses"]) <= len(game["moves"]):
        index = len(game["analyses"])
        if index == len(game["moves"]) and game["result"] and game["reason"] != "기권":
            item = terminal_analysis(game)
        else:
            item = analysis_for(tuple(map(tuple, game["moves"][:index])), budget)
        game["analyses"].append(item)
    game["reviews"] = [review_move(game["analyses"][i], game["analyses"][i+1], i%2+1, move)
                       for i, move in enumerate(game["moves"])]


def reset(game=None, review=False):
    st.session_state.game = game or new_game(st.session_state.get("color", 1))
    st.session_state.replay = review
    st.session_state.ply = len(st.session_state.game["moves"])
    st.session_state.guide = False


def owner_id():
    if not st.user.get("is_logged_in", False) or not st.user.get("sub"):
        return None
    return hashlib.sha256((str(st.user.get("iss", "https://accounts.google.com"))+":"+st.user["sub"]).encode()).hexdigest()


if "game" not in st.session_state:
    reset()
ss = st.session_state
if ss.get("move_notice"):
    st.toast(ss.pop("move_notice"), icon="⚠️")
game = ss.game
owner = owner_id()
database_url = settings.get("DATABASE_URL") or os.getenv("DATABASE_URL", "")
store = GameStore(database_url)

with st.sidebar:
    st.title("⚫ 오목 선생님")
    st.caption("RENJU · PLAY & LEARN")
    if owner:
        st.write(f"{st.user.get('name', '플레이어')}님")
        if st.button("로그아웃", use_container_width=True):
            st.logout()
    else:
        if st.button("Google로 로그인", use_container_width=True, disabled=not bool(settings.get("auth"))):
            st.login()
        st.caption("비로그인도 대국·해설·복기를 이용할 수 있어요.")
        if not settings.get("auth"):
            st.caption("Google 로그인은 OAuth Secrets 설정 후 활성화됩니다.")
    st.divider()
    ss.color = st.radio("내 돌", [1, 2], format_func=lambda c: "⚫ 흑 · 먼저 두기" if c == 1 else "⚪ 백 · 나중에 두기")
    budget = st.select_slider("엔진 생각 시간", [300, 600, 1200], value=600, format_func=lambda n: f"{n/1000:.1f}초")
    if st.button("새 대국 시작", type="primary", use_container_width=True):
        reset()
        st.rerun()
    st.toggle("착수 번호", key="numbers")
    st.toggle("착수음", value=True, key="sound")
    if game["moves"] and not ss.replay and not game["result"]:
        if st.button("기권하고 분석 보기", use_container_width=True):
            game["result"], game["reason"] = 3-game["player"], "기권"
            # 기권은 착수 평가에 포함하지 않는다. 마지막 국면 분석은 유지한다.
            ss.replay = True
            ss.ply = len(game["moves"])
            st.rerun()
    with st.expander("렌주 규칙"):
        st.write("15×15 · 흑은 쌍삼·쌍사·장목 금수, 정확히 5목 승리. 백은 5목 이상 승리합니다. 정확한 흑 5목은 금수보다 우선합니다. 금수 클릭은 착수하지 않고 안내합니다. 스왑·오프닝 규정은 사용하지 않습니다.")
    with st.expander("기보 가져오기"):
        uploaded = st.file_uploader("기보 JSON", type=["json"])
        if uploaded and st.button("기보 열기"):
            try:
                reset(import_game(uploaded.getvalue()), review=True)
                st.rerun()
            except ValueError as error:
                st.error(str(error))
    with st.expander("내 대국 기록", expanded=False):
        if owner:
            if not database_url:
                st.warning("로컬 저장 모드입니다. 클라우드 재배포 후에도 보관하려면 DATABASE_URL을 설정하세요.")
            try:
                records = store.list(owner)
                for saved in records:
                    label = f"{saved['created_at'][:16].replace('T',' ')} · {len(saved['moves'])}수"
                    a, b = st.columns([3, 1])
                    if a.button(label, key="load"+saved["id"]):
                        reset(copy.deepcopy(saved), review=True)
                        st.rerun()
                    if b.button("삭제", key="delete"+saved["id"]):
                        store.delete(owner, saved["id"])
                        st.rerun()
                if not records:
                    st.caption("저장된 기록이 없습니다.")
            except Exception:
                st.error("기록 DB에 연결하지 못했습니다. 연결 정보와 schema.sql 적용 여부를 확인하세요.")
        else:
            st.caption("로그인하면 계정별 기록을 저장하고 다시 볼 수 있어요.")

st.markdown('<div class="eyebrow">RENJU LEARNING STUDIO</div>', unsafe_allow_html=True)
st.title("한 수씩 두고, 이유를 배우세요.")
st.caption("AI와 대국하고 · 궁금한 수를 질문하고 · 나의 대국을 돌아보세요")

# 대국 상태가 바뀐 때만 분석. 채팅·번호 토글·복기 이동은 캐시를 재사용한다.
try:
    if len(game["analyses"]) <= len(game["moves"]):
        fill_analysis(game, budget)
except EngineError as error:
    st.error(str(error))
    st.button("엔진 다시 연결", on_click=lambda: None)
    st.stop()

ai_pending = not ss.replay and not game["result"] and len(game["moves"]) % 2 + 1 != game["player"]
if ai_pending:
    best = game["analyses"][-1]["best_move"]
    try:
        play(game, *best)
        ss.guide = False
        st.rerun()
    except ValueError as error:
        st.toast(f"AI 응수를 다시 확인해야 해요: {error}", icon="⚠️")
        if st.button("AI 응수 다시 시도"):
            analysis_for.clear()
            game["analyses"] = game["analyses"][:len(game["moves"])]
            st.rerun()

if game["result"] and not ss.replay:
    ss.replay = True
    ss.ply = len(game["moves"])

board_col, chat_col = st.columns([1.25, 1], gap="large")
with board_col:
    heading, control = st.columns([3, 1])
    heading.subheader("대국 복기" if ss.replay else "대국실")
    if game["moves"] and not game["result"]:
        if control.button("대국으로" if ss.replay else "복기 보기"):
            ss.replay = not ss.replay
            ss.ply = len(game["moves"])
            ss.guide = False
            st.rerun()
    count = len(game["moves"])
    if not ss.replay:
        ss.ply = count
    ply = ss.ply
    shown_moves = game["moves"][:ply]
    board = board_at(shown_moves)
    current = game["analyses"][ply]
    turn = ply % 2 + 1
    replay_terminal = ss.replay and ply == count and bool(game["result"]) and game["reason"] != "기권"
    if game["result"]:
        winner_text = "무승부" if game["result"] == 3 else ("승리" if game["result"] == game["player"] else "AI 승리")
        st.success(f"{winner_text} · {game['reason']} · 총 {count}수")
    else:
        st.caption(f"{'복기 중' if ss.replay else '대국 중' if ai_pending else '내 차례'} · {'흑' if turn == 1 else '백'} · {ply}수")
    position_token = game["id"]+":"+str(ply)+":"+str(ss.replay)
    clicked = board_widget(moves=shown_moves, numbers=ss.get("numbers", False), guide=ss.guide,
                           guides=current.get("guides", []), lines=threat_lines(board),
                           disabled=replay_terminal or (not ss.replay and (bool(game["result"]) or ai_pending)), position=position_token,
                           acknowledged_event=ss.get("last_event"),
                           sound=ss.get("sound", True), game_id=game["id"],
                           key="board", default=None)
    if clicked and clicked.get("event") != ss.get("last_event"):
        ss.last_event = clicked.get("event")
        if clicked.get("position") == position_token and not replay_terminal and (ss.replay or (not game["result"] and turn == game["player"])):
            try:
                if ss.replay:
                    reset(branch_play(game, ply, clicked.get("x"), clicked.get("y")))
                else:
                    play(game, clicked.get("x"), clicked.get("y"))
                ss.guide = False
                st.rerun()
            except ValueError as error:
                ss.move_notice = str(error)
                st.rerun()
    def navigate(target):
        ss.replay = True
        ss.ply = target
        ss.guide = False
    nav = st.columns(4)
    for column, label, target in zip(nav, ["처음", "이전", "다음", "마지막"],
                                     [0, max(0, ply-1), min(count, ply+1), count]):
        column.button(label, use_container_width=True, on_click=navigate, args=(target,),
                      disabled=not count or (target == ply))
    if ss.replay and count:
        st.slider("복기 수순", 0, count, key="ply")
        st.caption("빈자리에 두면 이후 수순을 지우고 새 대국으로 이어 둡니다. 현재 차례의 돌을 내가 두고 상대는 AI가 둬요.")
    rate = current.get("black_winrate")
    if game["result"] and ply == count:
        rate = {1: 1., 2: 0., 3: .5}[game["result"]]
    if rate is not None:
        percent = max(0, min(100, rate*100))
        st.markdown(f'<div class="winbar" role="img" aria-label="흑 {percent:.1f}퍼센트 백 {100-percent:.1f}퍼센트"><span style="width:{percent}%;background:#20352d;color:white">흑 {percent:.1f}%</span><span style="flex:1;background:#fffdf6;color:#20352d">백 {100-percent:.1f}%</span></div>', unsafe_allow_html=True)
    else:
        st.info("이 국면에는 승률 평가가 없습니다. 질문 시 추천 수는 확인할 수 있어요.")
    st.caption(f"Rapfi classical · 탐색 깊이 {current.get('depth', 0)} · 승률은 엔진 평가의 추정치이며 실전 통계가 아닙니다.")
    if ss.guide:
        st.caption("주황: 공격 후보 · 파랑: 즉시 위협 방어 · 연결선: 3개 이상 연속된 돌")
        for i, guide in enumerate(current.get("guides", []), 1):
            st.caption(f"{i}. {guide['label']} · {guide['source']}")
        if st.button("가이드 숨기기"):
            ss.guide = False
            st.rerun()
    if ss.replay and ply and len(game["reviews"]) >= ply:
        review = game["reviews"][ply-1]
        st.info(f"{ply}수 {coord(*shown_moves[-1])} · {review['category']} · 당시 엔진 최선 {review['best']} · 승률 손실 {review['loss']}%p")

with chat_col:
    st.subheader("채팅 선생님")
    teacher = BazeTeacher.from_settings(settings)
    st.caption(f"BAZE · {teacher.model} · 현재 보고 있는 {ply}수 국면을 설명해요")
    if not teacher.api_key:
        st.info("BAZE 키를 설정하면 AI 해설이 연결돼요. 지금은 엔진 추천과 가이드를 사용할 수 있어요.")
    prompt = None
    quick = st.columns(2)
    if quick[0].button("최선의 수가 뭐야?", use_container_width=True):
        prompt = "현재 최선의 수와 그 이유를 알려줘."
    if quick[1].button("상대는 왜 저기에 뒀어?", use_container_width=True):
        prompt = "마지막 수를 상대가 왜 뒀을지, 그 수 직전 분석과 비교해서 설명해줘."
    with st.container(height=390):
        if not game["chat"]:
            with st.chat_message("assistant"):
                st.write("반가워요! 먼저 한 수 두어 보세요. 최선의 수나 상대의 의도가 궁금하면 질문해 주세요. 질문하면 판 위에도 가이드를 표시할게요.")
        for message in game["chat"]:
            with st.chat_message(message["role"]):
                st.caption(f"{message.get('ply', 0)}수 국면")
                st.write(message["content"])
    typed = st.chat_input("이 수를 막아야 하는 이유가 뭐야?", max_chars=4000)
    prompt = typed or prompt
    if prompt:
        ss.guide = True
        position = {"board": board, "moves": [coord(*m) for m in shown_moves], "side_to_move": turn,
                    "coordinate_system": "A~O 왼쪽→오른쪽, 1~15 위→아래. board[y][x], 0=빈칸 1=흑 2=백. 엔진 좌표는 0-based (x,y).",
                    "analysis": current, "last_move_analysis_before": game["analyses"][ply-1] if ply else None,
                    "last_move_review": game["reviews"][ply-1] if ply and len(game["reviews"]) >= ply else None,
                    "result": game["result"] if ply == count else 0}
        if time.time()-ss.get("last_question", 0) < 3:
            st.warning("잠시 기다린 뒤 질문해 주세요.")
        else:
            ss.last_question = time.time()
            try:
                if teacher.api_key:
                    with st.spinner("현재 국면을 설명하고 있어요…"):
                        answer = teacher.explain(prompt, position, game["chat"])
                else:
                    best = current.get("best_move")
                    answer = (f"엔진의 현재 추천은 {coord(*best)}입니다. 판 위 1번으로 표시했어요. " if best else "대국이 끝난 국면입니다. ") + "자세한 자연어 해설은 BAZE_API_KEY 설정 후 사용할 수 있어요."
                game["chat"] += [{"role": "user", "content": prompt, "ply": ply}, {"role": "assistant", "content": answer, "ply": ply}]
                game["chat"] = game["chat"][-100:]
                st.rerun()
            except TeacherError as error:
                st.error(str(error))
    st.divider()
    st.markdown("**오늘의 원리**")
    st.write("상대의 즉시 승리 위협을 먼저 확인하고, 공격과 방어를 동시에 하는 자리를 찾아보세요.")

st.divider()
st.subheader("대국 분석" if game["result"] else "기보와 기록")
if game["result"]:
    columns = st.columns(2)
    for color, column in zip([game["player"], 3-game["player"]], columns):
        reviews = [r for i, r in enumerate(game["reviews"]) if i%2+1 == color]
        valid = [r["accuracy"] for r in reviews if r["accuracy"] is not None]
        with column:
            st.markdown(f"**{'나' if color == game['player'] else 'AI'} · {'흑' if color == 1 else '백'}**")
            st.metric("수 정확도 (엔진 추정)", f"{sum(valid)/len(valid):.1f}%" if valid else "분석 없음")
            st.write(" · ".join(f"{name} {sum(r['category']==name for r in reviews)}" for name in ["좋은 수", "보통 수", "나쁜 수", "이상한 수"]))
    with st.expander("분석 기준"):
        st.write("최선 수 대비 승률 손실 3%p 이하: 좋은 수, 3~10%p 미만: 보통 수, 10~25%p 미만: 나쁜 수. 25%p 이상 또는 즉시 승리·필수 방어를 놓친 수: 이상한 수. 정확도는 100×exp(-손실/20)의 평균입니다. 제한 시간 탐색의 전후 평가를 비교하는 지표이며, 탐색 오차가 있고 공식 기력 점수가 아닙니다. 기권 자체는 수 정확도에 포함하지 않습니다.")
if game["moves"]:
    st.dataframe([{"수": i+1, "돌": "흑" if i%2 == 0 else "백", "좌표": coord(*m),
                   "분류": game["reviews"][i]["category"] if len(game["reviews"]) > i else "분석 대기"}
                  for i, m in enumerate(game["moves"])], hide_index=True, height=180, width="stretch")
    actions = st.columns(3)
    actions[0].download_button("기보 다운로드", export_game(game), file_name=f"renju-{game['id'][:8]}.json", mime="application/json", use_container_width=True)
    if actions[1].button("계정에 기록 저장", disabled=not bool(owner), use_container_width=True):
        try:
            store.save(owner, game)
            st.success("대국과 해설을 저장했어요.")
        except Exception:
            st.error("기록을 저장하지 못했습니다. DB 연결과 테이블 설정을 확인하세요.")
    if actions[2].button("전체 다시 분석", use_container_width=True):
        game["analyses"], game["reviews"] = [], []
        analysis_for.clear()
        st.rerun()
st.caption("오목 선생님 · 강화학습 없이 기존 Rapfi 엔진으로 대국·분석합니다. 게스트 기록은 현재 세션 동안 유지되며 기보 파일로 보관할 수 있어요.")

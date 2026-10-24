"""대국 상태와 기보 검증. 브라우저·업로드 데이터의 분석 결과는 신뢰하지 않는다."""
from datetime import datetime, timezone
from uuid import uuid4
import json
import math
import copy

from gomoku.rules import board_at, validate, winner_after, coord


def new_game(player=1):
    return {"id": str(uuid4()), "created_at": datetime.now(timezone.utc).isoformat(),
            "player": player, "moves": [], "analyses": [], "reviews": [],
            "result": 0, "reason": "", "chat": []}


def play(game, x, y):
    if game["result"]:
        raise ValueError("이미 끝난 대국입니다.")
    board = board_at(game["moves"])
    color = 1 + len(game["moves"]) % 2
    validate(board, x, y, color)
    board[y][x] = color
    game["moves"].append([x, y])
    game["result"], _ = winner_after(board, x, y, color)
    if game["result"]:
        game["reason"] = "판 채움" if game["result"] == 3 else "오목 완성"


def branch_play(game, ply, x, y):
    """과거 국면에 착수한 새 대국. 검증 실패 시 원래 대국은 보존한다."""
    if type(ply) is not int or not 0 <= ply <= len(game["moves"]):
        raise ValueError("유효한 수순을 선택해 주세요.")
    branch = new_game(1 + ply % 2)
    for move in game["moves"][:ply]:
        play(branch, *move)
    branch["analyses"] = copy.deepcopy(game["analyses"][:ply+1])
    branch["reviews"] = copy.deepcopy(game["reviews"][:ply])
    branch["chat"] = copy.deepcopy([m for m in game["chat"] if m.get("ply", 0) <= ply])
    if branch["analyses"] and branch["analyses"][-1].get("best_move") is None:
        branch["analyses"] = branch["analyses"][:ply]
    play(branch, x, y)
    return branch


def review_move(before, after, color, played):
    best = list(before["best_move"]) == list(played)
    forced_miss = bool(before.get("winning_moves")) and tuple(played) not in map(tuple, before["winning_moves"])
    missed_block = (bool(before.get("opponent_winning_moves"))
                    and tuple(played) not in map(tuple, before["opponent_winning_moves"])
                    and tuple(played) not in map(tuple, before.get("winning_moves", [])))
    a, b = before.get("black_winrate"), after.get("black_winrate")
    if a is None or b is None:
        return {"accuracy": None, "loss": None, "category": "분석 없음", "best": coord(*before["best_move"])}
    loss = 0 if best else max(0., (a-b) * (1 if color == 1 else -1) * 100)
    category = "이상한 수" if forced_miss or missed_block or loss >= 25 else "나쁜 수" if loss >= 10 else "좋은 수" if loss <= 3 else "보통 수"
    return {"accuracy": round(100*math.exp(-loss/20), 1), "loss": round(loss, 1),
            "category": category, "best": coord(*before["best_move"])}


def export_game(game):
    return json.dumps({"format": "gomoku-teacher-v1", "player": game["player"],
                       "moves": game["moves"], "result": game["result"], "reason": game["reason"]},
                      ensure_ascii=False, indent=2)


def import_game(raw):
    try:
        data = json.loads(raw)
        if data.get("format") != "gomoku-teacher-v1" or type(data.get("player")) is not int or data.get("player") not in (1, 2):
            raise ValueError
        moves = data["moves"]
        if not isinstance(moves, list) or len(moves) > 225:
            raise ValueError
        game = new_game(data["player"])
        for move in moves:
            if not isinstance(move, list) or len(move) != 2:
                raise ValueError
            play(game, *move)
        if not game["result"] and data.get("reason") == "기권" and data.get("result") in (1, 2):
            game["result"], game["reason"] = data["result"], "기권"
        return game
    except (ValueError, TypeError, KeyError, AttributeError):
        raise ValueError("유효한 렌주 기보 JSON 파일이 아닙니다.") from None

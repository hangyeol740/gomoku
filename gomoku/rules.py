"""15×15 렌주 규칙. renju의 재귀 금수 판정기를 사용한다."""
from functools import lru_cache
from renju.check_forbid import get_foul_type

SIZE = 15
DIRECTIONS = ((1, 0), (0, 1), (1, 1), (1, -1))
FOULS = {1: "쌍삼", 2: "쌍사", 3: "장목"}


def coord(x, y):
    return f"{chr(65 + x)}{y + 1}"


def board_at(moves):
    board = [[0] * SIZE for _ in range(SIZE)]
    for i, (x, y) in enumerate(moves):
        board[y][x] = 1 + i % 2
    return board


def lines(board, x, y, color):
    result = []
    for dx, dy in DIRECTIONS:
        group = [(x, y)]
        for sign in (-1, 1):
            a, b = x + dx * sign, y + dy * sign
            while 0 <= a < SIZE and 0 <= b < SIZE and board[b][a] == color:
                group.append((a, b))
                a, b = a + dx * sign, b + dy * sign
        result.append(group)
    return result


@lru_cache(maxsize=12000)
def _foul(frozen, x, y):
    # checker는 board[first_axis][second_axis]를 사용한다. 행·열을 함께 넘긴다.
    return get_foul_type([list(row) for row in frozen], y, x)


def forbidden(board, x, y, color=1):
    if color != 1:
        return 0
    return _foul(tuple(map(tuple, board)), x, y)


def validate(board, x, y, color):
    if type(x) is not int or type(y) is not int or not (0 <= x < SIZE and 0 <= y < SIZE):
        raise ValueError("판 안의 교차점을 선택해 주세요.")
    if board[y][x]:
        raise ValueError("이미 돌이 있는 자리입니다.")
    foul = forbidden(board, x, y, color)
    if foul:
        raise ValueError(f"흑의 {FOULS[foul]} 금수입니다. 다른 곳에 두세요.")


def winner_after(board, x, y, color):
    for group in lines(board, x, y, color):
        if (color == 1 and len(group) == 5) or (color == 2 and len(group) >= 5):
            return color, group
    if all(all(row) for row in board):
        return 3, []
    return 0, []


def candidates(board):
    stones = [(x, y) for y in range(SIZE) for x in range(SIZE) if board[y][x]]
    if not stones:
        return [(7, 7)]
    return sorted({(a, b) for x, y in stones for a in range(max(0, x-2), min(SIZE, x+3))
                   for b in range(max(0, y-2), min(SIZE, y+3)) if not board[b][a]})


def winning_moves(board, color):
    wins = []
    for x, y in candidates(board):
        board[y][x] = color
        win = any(len(g) == 5 if color == 1 else len(g) >= 5 for g in lines(board, x, y, color))
        board[y][x] = 0
        if win and not forbidden(board, x, y, color):
            wins.append((x, y))
    return wins


def threat_lines(board):
    groups = []
    seen = set()
    for y in range(SIZE):
        for x in range(SIZE):
            if not board[y][x]:
                continue
            for group in lines(board, x, y, board[y][x]):
                key = tuple(sorted(group))
                if len(group) >= 3 and key not in seen:
                    seen.add(key)
                    groups.append({"points": list(key), "color": board[y][x]})
    return groups

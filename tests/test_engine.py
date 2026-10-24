"""RAPFI_PATH가 지정된 환경에서 실제 기존 엔진을 검사한다."""
import os
import unittest
from gomoku.engine import analyze
from gomoku.rules import board_at, validate


@unittest.skipUnless(os.environ.get("RAPFI_PATH"), "실제 엔진 검증에는 RAPFI_PATH 필요")
class EngineTests(unittest.TestCase):
    def test_white_perspective_and_legal_move(self):
        moves = [(7, 7)]
        info = analyze(moves, 300)
        validate(board_at(moves), *info["best_move"], 2)
        self.assertIsNotNone(info["black_winrate"])
        self.assertTrue(0 <= info["black_winrate"] <= 1)

    def test_takes_immediate_win(self):
        moves = [(3, 7), (0, 0), (4, 7), (1, 0), (5, 7), (2, 0), (6, 7), (10, 10)]
        info = analyze(moves, 300)
        self.assertIn(tuple(info["best_move"]), [(2, 7), (7, 7)])

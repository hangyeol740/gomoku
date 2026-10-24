import unittest
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from gomoku.game import new_game, play

APP = str(Path(__file__).resolve().parents[1] / "streamlit_app.py")


def test_analysis(moves, budget):
    return {"engine": "test", "best_move": (7, 7) if not moves else (7, 6),
            "black_winrate": .5, "depth": 1, "guides": [],
            "winning_moves": [], "opponent_winning_moves": []}


class AppTests(unittest.TestCase):
    @patch("gomoku.engine.analyze", side_effect=test_analysis)
    def test_guest_start_white_ai_move_and_replay(self, _):
        app = AppTest.from_file(APP).run(timeout=30)
        self.assertFalse(app.exception)
        app.radio[0].set_value(2).run()
        next(b for b in app.button if b.label == "새 대국 시작").click().run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["game"]["moves"], [[7, 7]])
        next(b for b in app.button if b.label == "복기 보기").click().run()
        next(b for b in app.button if b.label == "처음").click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state["ply"], 0)
        next(b for b in app.button if b.label == "다음").click().run()
        self.assertEqual(app.session_state["ply"], 1)

    @patch("gomoku.engine.analyze", side_effect=test_analysis)
    def test_finished_game_summary_and_replay(self, _):
        app = AppTest.from_file(APP).run(timeout=30)
        game = new_game()
        for move in [(3, 7), (0, 0), (4, 7), (1, 0), (5, 7), (2, 0), (6, 7), (3, 0), (7, 7)]:
            play(game, *move)
        app.session_state["game"] = game
        app.run(timeout=30)
        self.assertFalse(app.exception)
        self.assertEqual(len(app.metric), 2)
        self.assertTrue(app.session_state["replay"])
        self.assertEqual(len(app.session_state["game"]["reviews"]), 9)

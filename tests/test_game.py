import tempfile
import unittest
from pathlib import Path

from gomoku.rules import board_at, forbidden, winner_after, validate
from gomoku.game import new_game, play, branch_play, export_game, import_game, review_move
from gomoku.storage import GameStore


class RulesTests(unittest.TestCase):
    def test_branch_from_previous_move_and_invalid_branch_preserves_original(self):
        game = new_game()
        for move in [(7, 7), (7, 6), (8, 8), (6, 6)]:
            play(game, *move)
        branch = branch_play(game, 1, 8, 7)
        self.assertEqual(branch["moves"], [[7, 7], [8, 7]])
        self.assertEqual(branch["player"], 2)
        self.assertNotEqual(branch["id"], game["id"])
        with self.assertRaises(ValueError):
            branch_play(game, 1, 7, 7)
        self.assertEqual(len(game["moves"]), 4)

    def board(self, black=(), white=()):
        b = board_at([])
        for x, y in black:
            b[y][x] = 1
        for x, y in white:
            b[y][x] = 2
        return b

    def test_double_three(self):
        b = self.board([(6, 7), (8, 7), (7, 6), (7, 8)])
        self.assertEqual(forbidden(b, 7, 7), 1)
        with self.assertRaises(ValueError):
            validate(b, 7, 7, 1)
        self.assertEqual(forbidden(b, 7, 7, 2), 0)

    def test_double_four(self):
        b = self.board([(5, 7), (6, 7), (8, 7), (7, 5), (7, 6), (7, 8)])
        self.assertEqual(forbidden(b, 7, 7), 2)

    def test_overline_and_white_win(self):
        b = self.board([(x, 7) for x in [3, 4, 5, 7, 8]])
        self.assertEqual(forbidden(b, 6, 7), 3)
        b = self.board(white=[(x, 7) for x in range(3, 9)])
        self.assertEqual(winner_after(b, 6, 7, 2)[0], 2)

    def test_exact_five_priority(self):
        b = self.board([(x, 7) for x in [3, 4, 5, 6]] + [(7, 5), (7, 6), (7, 8)])
        self.assertEqual(forbidden(b, 7, 7), 0)

    def test_edge_is_not_open_three(self):
        b = self.board([(0, 1), (0, 2), (1, 0), (2, 0)])
        self.assertEqual(forbidden(b, 0, 0), 0)

    def test_play_export_import_and_terminal(self):
        game = new_game()
        for move in [(3, 7), (0, 0), (4, 7), (1, 0), (5, 7), (2, 0), (6, 7), (3, 0), (7, 7)]:
            play(game, *move)
        self.assertEqual(game["result"], 1)
        self.assertEqual(import_game(export_game(game))["moves"], game["moves"])
        with self.assertRaises(ValueError):
            play(game, 10, 10)

    def test_bad_imports(self):
        for moves in [[[7, 7], [7, 7]], [[-1, 0]], [[True, 7]], [[15, 0]]]:
            import json
            with self.assertRaises(ValueError):
                import_game(json.dumps({"format": "gomoku-teacher-v1", "player": 1, "moves": moves}))

    def test_tactical_miss_and_perspective(self):
        before = {"best_move": [2, 2], "black_winrate": .3, "opponent_winning_moves": [[2, 2]]}
        result = review_move(before, {"black_winrate": .9}, 2, [3, 3])
        self.assertEqual(result["loss"], 60)
        self.assertEqual(result["category"], "이상한 수")


class StorageTests(unittest.TestCase):
    def test_owner_isolation_and_upsert(self):
        with tempfile.TemporaryDirectory() as folder:
            store = GameStore(local_path=str(Path(folder)/"games.db"))
            game = new_game()
            store.save("alice", game)
            game["chat"] = [{"role": "user", "content": "질문"}]
            store.save("alice", game)
            self.assertEqual(len(store.list("alice")), 1)
            self.assertEqual(store.list("bob"), [])
            store.delete("bob", game["id"])
            self.assertEqual(len(store.list("alice")), 1)
            store.delete("alice", game["id"])
            self.assertEqual(store.list("alice"), [])

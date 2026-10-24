"""서버에서 검증된 Google subject로만 계정별 기록에 접근한다."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class GameStore:
    def __init__(self, database_url="", local_path="data/games.sqlite3"):
        self.database_url = database_url
        self.local_path = local_path

    @contextmanager
    def _connect(self):
        if self.database_url:
            import psycopg
            connection = psycopg.connect(self.database_url, connect_timeout=10)
        else:
            Path(self.local_path).parent.mkdir(parents=True, exist_ok=True)
            connection = sqlite3.connect(self.local_path)
            connection.execute("CREATE TABLE IF NOT EXISTS saved_games (id TEXT NOT NULL, owner TEXT NOT NULL, created_at TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(id, owner))")
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save(self, owner, game):
        if not owner:
            raise ValueError("로그인이 필요합니다.")
        marker = "%s" if self.database_url else "?"
        with self._connect() as db:
            db.execute(f"INSERT INTO saved_games (id,owner,created_at,payload) VALUES ({','.join([marker]*4)}) ON CONFLICT(id,owner) DO UPDATE SET payload=excluded.payload",
                       (game["id"], owner, game["created_at"], json.dumps(game, ensure_ascii=False)))

    def list(self, owner):
        if not owner:
            return []
        marker = "%s" if self.database_url else "?"
        with self._connect() as db:
            rows = db.execute(f"SELECT payload FROM saved_games WHERE owner={marker} ORDER BY created_at DESC LIMIT 100", (owner,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def delete(self, owner, game_id):
        if not owner:
            raise ValueError("로그인이 필요합니다.")
        marker = "%s" if self.database_url else "?"
        with self._connect() as db:
            db.execute(f"DELETE FROM saved_games WHERE owner={marker} AND id={marker}", (owner, game_id))

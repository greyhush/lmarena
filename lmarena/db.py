"""SQLite storage for arena results."""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_DB_DIR = Path.home() / ".lmarena"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "lmarena.db"


class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                models TEXT NOT NULL,
                system_prompt TEXT DEFAULT '',
                created_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS battles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                experiment_id INTEGER NOT NULL,
                prompt TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            );

            CREATE TABLE IF NOT EXISTS responses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                battle_id INTEGER NOT NULL,
                model TEXT NOT NULL,
                provider TEXT NOT NULL,
                response TEXT NOT NULL,
                tokens INTEGER DEFAULT 0,
                latency REAL DEFAULT 0,
                rating INTEGER,
                notes TEXT DEFAULT '',
                FOREIGN KEY (battle_id) REFERENCES battles(id)
            );

            CREATE INDEX IF NOT EXISTS idx_battles_exp
                ON battles(experiment_id);
            CREATE INDEX IF NOT EXISTS idx_responses_battle
                ON responses(battle_id);
        """)
        self.conn.commit()

    def create_experiment(self, name: str, models: List[str],
                          system_prompt: str = "") -> int:
        cur = self.conn.execute(
            "INSERT INTO experiments (name, models, system_prompt, created_at) VALUES (?, ?, ?, ?)",
            (name, json.dumps(models), system_prompt, time.time())
        )
        self.conn.commit()
        return cur.lastrowid

    def create_battle(self, experiment_id: int, prompt: str) -> int:
        cur = self.conn.execute(
            "INSERT INTO battles (experiment_id, prompt, created_at) VALUES (?, ?, ?)",
            (experiment_id, prompt, time.time())
        )
        self.conn.commit()
        return cur.lastrowid

    def save_response(self, battle_id: int, model: str, provider: str,
                      response: str, tokens: int = 0, latency: float = 0) -> int:
        cur = self.conn.execute(
            "INSERT INTO responses (battle_id, model, provider, response, tokens, latency) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (battle_id, model, provider, response, tokens, latency)
        )
        self.conn.commit()
        return cur.lastrowid

    def rate_response(self, response_id: int, rating: int, notes: str = ""):
        self.conn.execute(
            "UPDATE responses SET rating=?, notes=? WHERE id=?",
            (rating, notes, response_id)
        )
        self.conn.commit()

    def get_experiment(self, exp_id: int) -> Optional[Dict]:
        row = self.conn.execute("SELECT * FROM experiments WHERE id=?", (exp_id,)).fetchone()
        if row:
            d = dict(row)
            d["models"] = json.loads(d["models"])
            return d
        return None

    def list_experiments(self, limit: int = 20) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            d["models"] = json.loads(d["models"])
            result.append(d)
        return result

    def get_battles(self, experiment_id: int) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM battles WHERE experiment_id=? ORDER BY created_at", (experiment_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_battle_responses(self, battle_id: int) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT * FROM responses WHERE battle_id=? ORDER BY id", (battle_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_leaderboard(self, experiment_id: int) -> Dict:
        """Calculate ELO-style leaderboard for an experiment."""
        rows = self.conn.execute("""
            SELECT r.model,
                   COUNT(*) as battles,
                   AVG(r.rating) as avg_rating,
                   AVG(r.latency) as avg_latency,
                   AVG(r.tokens) as avg_tokens
            FROM responses r
            JOIN battles b ON r.battle_id = b.id
            WHERE b.experiment_id=? AND r.rating IS NOT NULL
            GROUP BY r.model
            ORDER BY avg_rating DESC
        """, (experiment_id,)).fetchall()

        return [dict(r) for r in rows]

    def get_model_stats(self, model: str) -> Dict:
        """Get overall stats for a model across all experiments."""
        row = self.conn.execute("""
            SELECT COUNT(*) as total_battles,
                   AVG(rating) as avg_rating,
                   AVG(latency) as avg_latency,
                   AVG(tokens) as avg_tokens,
                   MIN(rating) as min_rating,
                   MAX(rating) as max_rating
            FROM responses
            WHERE model=? AND rating IS NOT NULL
        """, (model,)).fetchone()
        return dict(row) if row else {}

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

import os
from pathlib import Path
import urllib.parse as urlparse
import re
HAS_POSTGRES = True
HAS_SQLITE = True
try:
    import psycopg2
except ImportError:
    HAS_POSTGRES = False
try:
    import sqlite3
except ImportError:
    HAS_SQLITE = False

class DBHelper:
    def __init__(self):
        self.is_enabled = False
        self.type = None
        if HAS_POSTGRES and os.environ.get("DATABASE_URL"):
            self.provider = psycopg2
            urlparse.uses_netloc.append("postgres")
            url = urlparse.urlparse(os.environ["DATABASE_URL"])
            self.conn = psycopg2.connect(
                database=url.path[1:],
                user=url.username,
                password=url.password,
                host=url.hostname,
                port=url.port
            )
            self.cur = self.conn.cursor()
            self.is_enabled = True
            self.type = "POSTGRES"
        elif HAS_SQLITE:
            self.provider = sqlite3
            db_path = Path(__file__).parent / 'database.db'
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.cur = self.conn.cursor()
            self.is_enabled = True
            self.type = "SQLITE"

    def setup(self):
        if not self.is_enabled: return
        self.cur.execute("CREATE TABLE IF NOT EXISTS Users (chat_id integer PRIMARY KEY, state text)")
        self.conn.commit()

    def dump_users(self):
        if not self.is_enabled: return []
        self.cur.execute("SELECT * FROM Users")
        return self.cur.fetchall()

    def set_state(self, chat_id, par):
        if not self.is_enabled: return
        self.execute("INSERT INTO Users (chat_id, state) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET state = EXCLUDED.state;", (chat_id, par))
        self.conn.commit()

    def get_state(self, chat_id):
        if not self.is_enabled: return ""
        self.execute("SELECT state FROM Users WHERE chat_id = (%s)", (chat_id, ))
        row = self.cur.fetchone()
        if row is not None:
            return row[0]
        return ""

    def execute(self, stmt, attr=()):
        if not self.is_enabled: return
        if self.type == "SQLITE":
            stmt = re.sub('%s', '?', stmt)
        self.cur.execute(stmt, attr)

    def add_columns_to_users(self, columns):
        if not self.is_enabled: return
        for column in columns:
            if self.type == "POSTGRES":
                self.cur.execute(f"ALTER TABLE Users ADD COLUMN IF NOT EXISTS  {column[0]} {column[1]}")
            elif self.type == "SQLITE":
                try:
                    self.cur.execute(f"SELECT {column[0]} FROM Users LIMIT 1")
                except self.provider.OperationalError:
                    self.cur.execute(f"ALTER TABLE Users ADD {column[0]} {column[1]}")
        self.conn.commit()

    def insert_or_update(self, table, column, chat_id, par):
        if not self.is_enabled: return
        if self.type == "POSTGRES":
            self.cur.execute(f"INSERT INTO {table} (chat_id, {column}) VALUES (%s, %s) ON CONFLICT (chat_id) DO UPDATE SET {column} = EXCLUDED.{column};", (chat_id, par))
        elif self.type == "SQLITE":
            self.cur.execute(f"SELECT {column} FROM {table} WHERE chat_id = (?)", (chat_id, ))
            row = self.cur.fetchone()
            if row is None: self.cur.execute(f"INSERT INTO {table} (chat_id, {column}) VALUES (?, ?)", (chat_id, par))
            else: self.cur.execute(f"UPDATE {table} SET {column} = (?) WHERE chat_id = (?)", (par, chat_id))

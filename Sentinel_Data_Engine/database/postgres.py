"""
============================================================
Sentinel Data Engine

PostgreSQL Database Connection Manager
============================================================
"""

from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

from config.settings import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD
)


class PostgreSQL:

    def __init__(self):

        self.connection = None

    # =====================================================

    def connect(self):

        if self.connection is None or self.connection.closed:

            self.connection = psycopg2.connect(

                host=DB_HOST,

                port=DB_PORT,

                database=DB_NAME,

                user=DB_USER,

                password=DB_PASSWORD,

                cursor_factory=RealDictCursor

            )

        return self.connection

    # =====================================================

    @contextmanager
    def cursor(self):

        connection = self.connect()

        cursor = connection.cursor()

        try:

            yield cursor

            connection.commit()

        except Exception:

            connection.rollback()

            raise

        finally:

            cursor.close()

    # =====================================================

    def execute(self, query, params=None):

        with self.cursor() as cur:

            cur.execute(query, params)

    # =====================================================

    def fetchone(self, query, params=None):

        with self.cursor() as cur:

            cur.execute(query, params)

            return cur.fetchone()

    # =====================================================

    def fetchall(self, query, params=None):

        with self.cursor() as cur:

            cur.execute(query, params)

            return cur.fetchall()

    # =====================================================

    def executemany(self, query, values):

        with self.cursor() as cur:

            cur.executemany(query, values)

    # =====================================================

    def close(self):

        if self.connection and not self.connection.closed:

            self.connection.close()

            self.connection = None


# ==========================================================
# Singleton Instance
# ==========================================================

db = PostgreSQL()


# ==========================================================
# Test
# ==========================================================

if __name__ == "__main__":

    try:

        db.connect()

        print("Connected to PostgreSQL Successfully.")

        result = db.fetchone("SELECT version();")

        print(result)

    finally:

        db.close()
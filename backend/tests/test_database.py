import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from app import database
from app.categories import PRIMARY_CATEGORIES


class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "test.db"
        self.patch = patch.object(database, "DATABASE_PATH", self.path)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def test_upgrade_preserves_existing_articles_and_can_repeat(self):
        with closing(sqlite3.connect(self.path)) as connection:
            connection.execute("""
                CREATE TABLE articles (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE, source TEXT NOT NULL,
                    published_at TEXT,
                    collected_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    content TEXT, category TEXT,
                    severity TEXT CHECK (severity IN ('Low','Medium','High','Critical'))
                )
            """)
            connection.execute("""
                INSERT INTO articles (id, title, url, source, content, category, severity)
                VALUES (42, 'Existing story', 'https://example.test/old',
                        'Existing publisher', 'Original text', 'Malware', 'High')
            """)
            connection.commit()
        before = database.get_articles()
        database.initialise_database()
        database.initialise_database()
        self.assertEqual(database.get_articles(), before)
        with closing(database.get_connection()) as connection:
            labels = {row[0] for row in connection.execute('SELECT name FROM categories')}
            self.assertEqual(labels, set(PRIMARY_CATEGORIES))
            self.assertEqual(connection.execute('SELECT count(*) FROM report_analysis').fetchone()[0], 0)

    def test_multiple_sources_and_tags_for_one_primary_category(self):
        database.initialise_database()
        with closing(database.get_connection()) as connection, connection:
            connection.execute("INSERT INTO reports (id, title) VALUES (1, 'Ransomware incident')")
            for article_id in (1, 2, 3):
                connection.execute(
                    'INSERT INTO articles (id, title, url, source) VALUES (?, ?, ?, ?)',
                    (article_id, 'Original coverage', f'https://example.test/{article_id}', f'Publisher {article_id}'),
                )
                connection.execute('INSERT INTO report_articles VALUES (1, ?)', (article_id,))
            connection.execute("""
                INSERT INTO report_analysis
                (report_id, primary_category, predicted_severity, final_severity, severity_reason)
                VALUES (1, 'Ransomware', 'High', 'Critical', 'Confirmed critical-service disruption')
            """)
            connection.executemany('INSERT INTO report_tags VALUES (1, ?)', [('phishing',), ('data theft',)])
            self.assertEqual(connection.execute('SELECT count(*) FROM report_articles').fetchone()[0], 3)
            self.assertEqual(connection.execute('SELECT count(*) FROM report_tags').fetchone()[0], 2)
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute("INSERT INTO report_analysis (report_id, primary_category) VALUES (1, 'Phishing')")
        database.initialise_database()
        with closing(database.get_connection()) as connection:
            row = connection.execute('SELECT * FROM report_analysis WHERE report_id = 1').fetchone()
            self.assertEqual(row['primary_category'], 'Ransomware')
            self.assertEqual(row['predicted_severity'], 'High')
            self.assertEqual(row['final_severity'], 'Critical')
            self.assertEqual(connection.execute('SELECT count(*) FROM report_articles').fetchone()[0], 3)

    def test_constraints_reject_invalid_analysis_and_orphan_links(self):
        database.initialise_database()
        with closing(database.get_connection()) as connection, connection:
            connection.execute("INSERT INTO reports (id, title) VALUES (1, 'Report')")
            bad_statements = [
                "INSERT INTO report_analysis (report_id, primary_category) VALUES (1, 'Malware')",
                "INSERT INTO report_analysis (report_id, final_severity) VALUES (1, 'Urgent')",
                "INSERT INTO report_analysis (report_id, category_confidence) VALUES (1, 1.5)",
                "INSERT INTO report_articles VALUES (1, 999)",
                "INSERT INTO report_tags VALUES (999, 'phishing')",
            ]
            for statement in bad_statements:
                with self.subTest(statement=statement), self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(statement)

    def test_duplicate_urls_blocked_and_report_delete_preserves_articles(self):
        database.initialise_database()
        with closing(database.get_connection()) as connection, connection:
            sql = 'INSERT INTO articles (title, url, source) VALUES (?, ?, ?)'
            values = ('Story', 'https://example.test/story', 'Publisher')
            article_id = connection.execute(sql, values).lastrowid
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute(sql, values)
            connection.execute("INSERT INTO reports (id, title) VALUES (1, 'Report')")
            connection.execute('INSERT INTO report_articles VALUES (1, ?)', (article_id,))
            with self.assertRaises(sqlite3.IntegrityError):
                connection.execute('DELETE FROM articles WHERE id = ?', (article_id,))
            connection.execute('DELETE FROM reports WHERE id = 1')
            self.assertEqual(connection.execute('SELECT count(*) FROM report_articles').fetchone()[0], 0)
            self.assertEqual(connection.execute('SELECT count(*) FROM articles').fetchone()[0], 1)


if __name__ == '__main__':
    unittest.main()

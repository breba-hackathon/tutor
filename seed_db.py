import os
import sqlite3
from pathlib import Path


def create_db(db_path='study_material.db'):
    # Connect to (or create) the database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create the table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject TEXT NOT NULL,
        topic TEXT NOT NULL,
        text TEXT NOT NULL,
        authors TEXT NOT NULL
    )
    """)
    # Save and close
    conn.commit()
    conn.close()


def insert_books_to_db(base_path=Path('books'), db_path='study_material.db'):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for subject_path in base_path.iterdir():
        if not subject_path.is_dir():
            continue

        subject = subject_path.name

        # Read authors.txt (default to "Unknown" if missing)
        authors_file = subject_path / "authors.txt"
        authors = authors_file.read_text(encoding="utf-8").strip() if authors_file.exists() else "Unknown"

        # Read topic files
        for file_path in subject_path.glob("*.txt"):
            if file_path.name == "authors.txt":
                continue

            topic = file_path.stem.split(" - ", 1)[1] if " - " in file_path.stem else file_path.stem
            text = file_path.read_text(encoding="utf-8").strip()

            cursor.execute("""
                    INSERT INTO topics (subject, topic, text, authors)
                    VALUES (?, ?, ?, ?)
                """, (subject, topic, text, authors))

    conn.commit()
    conn.close()

# create_db()

# Call the function
insert_books_to_db()
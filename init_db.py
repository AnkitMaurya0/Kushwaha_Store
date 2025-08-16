import sqlite3

# Database file path
DB_PATH = "database.db"

def init_db():
    # Connect to SQLite database
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Read SQL schema file
    with open("schema.sql", "r", encoding="utf-8") as f:
        schema_sql = f.read()

    # Execute schema SQL to create tables
    cur.executescript(schema_sql)

    # Commit changes and close connection
    conn.commit()
    conn.close()

    print("✅ Database initialized successfully!")

if __name__ == "__main__":
    init_db()

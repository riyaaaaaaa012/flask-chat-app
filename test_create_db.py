from chat_app import app, db
from chat_app.models import User, ChatMessage

with app.app_context():
    print("Creating tables...")
    db.create_all()
    print("Tables created!")

    # Check tables via raw SQL
    conn = db.engine.raw_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables in DB:", tables)
    conn.close()

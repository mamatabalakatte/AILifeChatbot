import sqlite3
import json
from datetime import datetime

DB_FILE = "edugenie.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Create table for progress tracking
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS progress (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        topic TEXT,
        score INTEGER,
        total INTEGER,
        timestamp DATETIME
    )
    ''')
    
    # Create table for weak topics
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS weak_topics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        topic TEXT,
        mistake_count INTEGER
    )
    ''')
    
    # Create table for chat history (optional for hackathon, but good for persistence)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        role TEXT,
        content TEXT,
        timestamp DATETIME
    )
    ''')
    
    conn.commit()
    conn.close()

def save_quiz_score(user_id: str, topic: str, score: int, total: int):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO progress (user_id, topic, score, total, timestamp) VALUES (?, ?, ?, ?, ?)",
        (user_id, topic, score, total, datetime.now())
    )
    # If score is low, increment mistake count
    if score < total / 2:
        cursor.execute("SELECT mistake_count FROM weak_topics WHERE user_id=? AND topic=?", (user_id, topic))
        result = cursor.fetchone()
        if result:
            cursor.execute("UPDATE weak_topics SET mistake_count = mistake_count + 1 WHERE user_id=? AND topic=?", (user_id, topic))
        else:
            cursor.execute("INSERT INTO weak_topics (user_id, topic, mistake_count) VALUES (?, ?, 1)", (user_id, topic))
    
    conn.commit()
    conn.close()

def get_progress(user_id: str):
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT topic, score, total, timestamp FROM progress WHERE user_id=? ORDER BY timestamp DESC LIMIT 10", (user_id,))
    recent_scores = [dict(row) for row in cursor.fetchall()]
    
    cursor.execute("SELECT topic, mistake_count FROM weak_topics WHERE user_id=? ORDER BY mistake_count DESC LIMIT 5", (user_id,))
    weak_topics = [dict(row) for row in cursor.fetchall()]
    
    conn.close()
    
    # Calculate overall average
    avg_score = 0
    if recent_scores:
        total_score = sum([row['score'] for row in recent_scores])
        total_possible = sum([row['total'] for row in recent_scores])
        if total_possible > 0:
            avg_score = round((total_score / total_possible) * 100)
            
    return {
        "recent_scores": recent_scores,
        "weak_topics": weak_topics,
        "average_score_percent": avg_score
    }

def record_mistake(user_id: str, topic: str):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT mistake_count FROM weak_topics WHERE user_id=? AND topic=?", (user_id, topic))
    result = cursor.fetchone()
    if result:
        cursor.execute("UPDATE weak_topics SET mistake_count = mistake_count + 1 WHERE user_id=? AND topic=?", (user_id, topic))
    else:
        cursor.execute("INSERT INTO weak_topics (user_id, topic, mistake_count) VALUES (?, ?, 1)", (user_id, topic))
    conn.commit()
    conn.close()

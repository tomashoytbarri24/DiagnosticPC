import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "hardware_health.db")

def init_db():
    """Inicializa la base de datos local SQLite con la tabla de telemetría."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            cpu_usage REAL,
            ram_usage REAL,
            smart_reallocated_sectors INTEGER,
            smart_pending_sectors INTEGER,
            health_score REAL
        )
    """)
    conn.commit()
    conn.close()

def save_telemetry_record(cpu, ram, reallocated, pending, health_score):
    """Guarda una lectura en la base de datos SQLite."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO telemetry_history 
            (cpu_usage, ram_usage, smart_reallocated_sectors, smart_pending_sectors, health_score)
            VALUES (?, ?, ?, ?, ?)
        """, (cpu, ram, reallocated, pending, health_score))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error guardando en la Base de Datos: {e}")
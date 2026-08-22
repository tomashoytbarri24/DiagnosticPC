import sqlite3
import os
import logging
from platformdirs import user_data_dir

# 1. Configurar ruta usando platformdirs (%LOCALAPPDATA% en Win, ~/.local/share en Linux)
APP_DATA_DIR = user_data_dir("DiagnosticPC", "CorePulse")
os.makedirs(APP_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DATA_DIR, "hardware_health.db")

logger = logging.getLogger("DiagnosticPC")

def init_db():
    """Inicializa la base de datos local SQLite y purga registros antiguos."""
    try:
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
        
        # Purga de mantenimiento al iniciar
        purge_old_records(days_to_keep=90)
    except Exception as e:
        logger.error(f"Error inicializando la Base de Datos: {e}")

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
        logger.error(f"Error guardando en la Base de Datos: {e}")

def purge_old_records(days_to_keep=90):
    """Purga registros más antiguos a N días para controlar el tamaño de la DB."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM telemetry_history 
            WHERE timestamp < datetime('now', '-' || ? || ' days')
        """, (days_to_keep,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Error purgando registros antiguos de la Base de Datos: {e}")
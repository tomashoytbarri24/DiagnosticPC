"""Gestiona la base SQLite utilizada para almacenar muestras históricas de telemetría."""
# Código refactorizado: nombres estables y documentación en español.
import sqlite3
import os
import logging
from platformdirs import user_data_dir
APP_DATA_DIR = user_data_dir('CorePulse', 'CorePulse')
os.makedirs(APP_DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DATA_DIR, 'hardware_health.db')
logger = logging.getLogger('CorePulse')

def initialize_database():
    """Crea la base de datos y su tabla histórica si todavía no existen."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('\n            CREATE TABLE IF NOT EXISTS telemetry_history (\n                id INTEGER PRIMARY KEY AUTOINCREMENT,\n                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,\n                cpu_usage REAL,\n                ram_usage REAL,\n                smart_reallocated_sectors INTEGER,\n                smart_pending_sectors INTEGER,\n                health_score REAL\n            )\n        ')
        conn.commit()
        conn.close()
        purge_old_records(days_to_keep=90)
    except Exception as e:
        logger.error(f'Error inicializando la Base de Datos: {e}')

def save_telemetry_record(cpu, ram, reallocated, pending, health_score):
    """Guarda una muestra histórica de telemetría utilizando parámetros SQL seguros."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('\n            INSERT INTO telemetry_history \n            (cpu_usage, ram_usage, smart_reallocated_sectors, smart_pending_sectors, health_score)\n            VALUES (?, ?, ?, ?, ?)\n        ', (cpu, ram, reallocated, pending, health_score))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f'Error guardando en la Base de Datos: {e}')

def purge_old_records(days_to_keep=90):
    """Elimina registros anteriores al período de retención configurado."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("\n            DELETE FROM telemetry_history \n            WHERE timestamp < datetime('now', '-' || ? || ' days')\n        ", (days_to_keep,))
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f'Error purgando registros antiguos de la Base de Datos: {e}')

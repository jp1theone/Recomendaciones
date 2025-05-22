# /epics_recommendation_flask/database.py

import mysql.connector
import os

DB_HOST = os.environ.get('DB_HOST', 'localhost')
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASSWORD = os.environ.get('DB_PASSWORD', '')
DB_NAME = os.environ.get('DB_NAME', 'reco')
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), 'schema_mysql.sql')

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Error de conexión a MySQL: {err}")
        return None

def init_db(app_context_needed=False):
    try:
        conn = get_db_connection()
        if conn is None:
            print(f"No se pudo conectar a la base de datos '{DB_NAME}' para la inicialización/verificación.")
            return

        cursor = conn.cursor()
        cursor.execute("SHOW TABLES LIKE 'Usuarios'")
        result = cursor.fetchone()
        
        if not result:
            print(f"ADVERTENCIA: La tabla 'Usuarios' no existe en la base de datos '{DB_NAME}'.")
            print(f"Por favor, ejecuta manualmente el script '{SCHEMA_PATH}' en tu base de datos MySQL.")
        else:
            print(f"Conexión a MySQL exitosa. La tabla 'Usuarios' existe en '{DB_NAME}'.")
        
        cursor.close()
        conn.close()
    except mysql.connector.Error as err:
        print(f"Error durante la inicialización/verificación de la BD MySQL: {err}")


def query_db(query, args=None, one=False, dictionary=True):
    conn = get_db_connection()
    if conn is None: return None
    cur = conn.cursor(dictionary=dictionary)
    results = None
    try:
        cur.execute(query, args if args else ())
        rv = cur.fetchall()
        results = (rv[0] if rv else None) if one else rv
    except mysql.connector.Error as err:
        print(f"Error en query_db ejecutando '{query}' con args {args}: {err}")
    finally:
        if cur: cur.close()
        if conn: conn.close()
    return results

def execute_db(query, args=None):
    conn = get_db_connection()
    if conn is None: return None
    cur = conn.cursor()
    last_row_id = None
    try:
        cur.execute(query, args if args else ())
        last_row_id = cur.lastrowid
        conn.commit()
    except mysql.connector.Error as err:
        print(f"Error en execute_db ejecutando '{query}' con args {args}: {err}")
        if conn: conn.rollback()
    finally:
        if cur: cur.close()
        if conn: conn.close()
    return last_row_id

if __name__ == '__main__':
    conn_test = get_db_connection()
    if conn_test:
        print(f"Conexión de prueba a MySQL (BD: {DB_NAME}) exitosa desde database.py.")
        conn_test.close()
    else:
        print(f"Falló la conexión de prueba a MySQL (BD: {DB_NAME}) desde database.py.")
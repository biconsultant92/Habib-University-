import pyodbc
import pandas as pd
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_connection():
    """
    Establishes and returns a connection to the SQL Server database.
    Using Windows Authentication (Trusted_Connection=yes) by default.
    """
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_NAME")
    
    # Windows Authentication connection string
    conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    
    # If using SQL Server Authentication, use this instead:
    # user = os.getenv("DB_USER")
    # password = os.getenv("DB_PASS")
    # conn_str = f"DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={server};DATABASE={database};UID={user};PWD={password};"
    
    try:
        conn = pyodbc.connect(conn_str)
        return conn
    except Exception as e:
        print(f"Database Connection Error: {e}")
        return None

def fetch_data(query, params=None):
    """
    Fetches data from the database and returns a Pandas DataFrame.
    """
    conn = get_connection()
    if conn:
        if params:
            df = pd.read_sql(query, conn, params=params)
        else:
            df = pd.read_sql(query, conn)
        conn.close()
        return df
    return pd.DataFrame()

def execute_query(query, params):
    """
    Executes an INSERT, UPDATE, or DELETE query.
    """
    conn = get_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute(query, params)
        conn.commit()
        cursor.close()
        conn.close()
        return True
    return False
"""
Database Connection Manager for MySQL
Ye file MySQL database connection handle karti hai
Using PyMySQL instead of mysql-connector-python
"""

import pymysql
import pymysql.cursors
from pymysql import Error
from contextlib import contextmanager
from typing import Optional
import os

# MySQL Configuration
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = "root"
MYSQL_PASSWORD = "Cogent@2025"
MYSQL_DB = "crm"

# Connection Pool - PyMySQL doesn't have built-in pooling, so we'll use simple connections
connection_pool = None

def init_connection_pool():
    """MySQL connection pool - PyMySQL uses direct connections"""
    global connection_pool
    try:
        # Test connection
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB
        )
        conn.close()
        print(f"✅ MySQL connection verified for database: {MYSQL_DB}")
        connection_pool = True  # Mark as initialized
        return True
    except Error as e:
        print(f"❌ Error initializing connection: {e}")
        return False

def get_connection():
    """Direct MySQL connection return karta hai with DictCursor"""
    global connection_pool
    if connection_pool is None:
        # Lazy initialization
        if not create_database_if_not_exists():
            raise Exception("Failed to create/connect to database")
        if not init_connection_pool():
            raise Exception("Failed to initialize connection")
    
    try:
        return pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            cursorclass=pymysql.cursors.DictCursor  # Dictionary cursor for dict-like results
        )
    except Error as e:
        print(f"❌ Error getting connection: {e}")
        raise

@contextmanager
def get_db():
    """
    Context manager for database connection
    Automatically connection close kar deta hai after use
    
    Usage:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
            results = cursor.fetchall()
    """
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        print(f"❌ Database error, rolling back: {e}")
        raise
    finally:
        conn.close()

def create_database_if_not_exists():
    """Agar database exist nahi karta toh create kar deta hai"""
    try:
        # Pehle bina database ke connect karo
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD
        )
        cursor = conn.cursor()
        
        # Database create karo agar exist nahi karta
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {MYSQL_DB}")
        cursor.execute(f"USE {MYSQL_DB}")
        
        print(f"✅ Database '{MYSQL_DB}' ready!")
        
        cursor.close()
        conn.close()
        return True
        
    except Error as e:
        print(f"❌ Error creating database: {e}")
        return False

def test_connection():
    """Database connection test karta hai"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            if result:
                print("✅ MySQL database connection successful!")
                return True
            return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False

# Initialize connection pool on import - with error handling
# Disabled auto-init to prevent import-time crashes
# Call manually when needed
if __name__ != "__main__":
    pass  # Don't auto-initialize
    # Uncomment below to enable auto-init:
    # try:
    #     create_database_if_not_exists()
    #     init_connection_pool()
    # except Exception as e:
    #     print(f"⚠️ Warning: Database initialization failed: {e}")
    #     print("⚠️ Please check MySQL service and credentials")

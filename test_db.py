#!/usr/bin/env python3
"""
Smart Forest Geo-Fencing & Emergency Monitoring System
Database Connection Diagnostics Tool
"""

import os
import sys
from dotenv import load_dotenv
import pymysql

# Load environment variables
load_dotenv()

DB_TYPE = os.getenv("DB_TYPE", "mysql").lower()
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
# Prevent pytest from treating this CLI diagnostics tool as a test suite
__test__ = False

def test_database_connection():
    print("=" * 60)
    print("SMART FOREST MONITORING SYSTEM - DATABASE DIAGNOSTICS")
    print("=" * 60)
    print(f"Database Type:   {DB_TYPE.upper()}")

    if DB_TYPE == "sqlite":
        db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "smart_forest.db"))
        print(f"SQLite File:     {db_path}")
        print("-" * 60)
        try:
            print("[1/2] Connecting to SQLite database...")
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
            conn.close()
            print(f"[2/2] Existing tables ({len(tables)}): {tables if tables else 'None yet (will auto-create on server start)'}")
            print("=" * 60)
            print("[OK] DATABASE CONNECTION VERIFIED: SQLite is ready for application use.")
            print("=" * 60)
            return True
        except Exception as e:
            print(f"[ERROR] SQLite error: {e}")
            return False

    print(f"Target Host:     {DB_HOST}")
    print(f"Target Port:     {DB_PORT}")
    print(f"Database Name:   {DB_NAME}")
    print(f"Database User:   {DB_USER}")
    print(f"Password Set:    {'YES' if DB_PASSWORD else 'NO (Empty)'}")
    print("-" * 60)

    # 1. Test Server Connectivity
    try:
        print("[1/3] Testing connection to MySQL Server...")
        conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            charset="utf8mb4",
            connect_timeout=5
        )
        print("  [SUCCESS] Connected to MySQL Server successfully!")
        
        # 2. Check / Create Database
        print(f"[2/3] Checking if database '{DB_NAME}' exists...")
        with conn.cursor() as cursor:
            cursor.execute("SHOW DATABASES LIKE %s;", (DB_NAME,))
            result = cursor.fetchone()
            if result:
                print(f"  [SUCCESS] Database '{DB_NAME}' already exists.")
            else:
                print(f"  [INFO] Database '{DB_NAME}' not found. Creating database...")
                cursor.execute(f"CREATE DATABASE `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
                print(f"  [SUCCESS] Database '{DB_NAME}' created successfully!")
        
        # 3. Test Database Selection & Query
        print(f"[3/3] Testing database operations on '{DB_NAME}'...")
        conn.select_db(DB_NAME)
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES;")
            tables = [row[0] for row in cursor.fetchall()]
            print(f"  [SUCCESS] Connected to '{DB_NAME}'. Existing tables ({len(tables)}): {tables if tables else 'None yet'}")
            
        conn.close()
        print("=" * 60)
        print("[OK] DATABASE CONNECTION VERIFIED: MySQL is ready for application use.")
        print("=" * 60)
        return True

    except pymysql.err.OperationalError as e:
        code, msg = e.args if len(e.args) >= 2 else (0, str(e))
        print("=" * 60)
        print("[ERROR] DATABASE CONNECTION ERROR:")
        print(f"  Error Code:  {code}")
        print(f"  Host:        {DB_HOST}:{DB_PORT}")
        print(f"  User:        {DB_USER}")
        print(f"  Target DB:   {DB_NAME}")
        print(f"  Reason:      {msg}")
        print("-" * 60)
        print("[INFO] TROUBLESHOOTING INSTRUCTIONS:")
        print("  1. Ensure MySQL Server is running (check Windows Services -> MySQL80).")
        print("  2. Verify credentials in your '.env' file (DB_USER, DB_PASSWORD).")
        print("  3. To update credentials, edit the .env file in the project root.")
        print("=" * 60)
        return False
        
    except Exception as e:
        print("=" * 60)
        print(f"[ERROR] UNEXPECTED DATABASE ERROR: {e}")
        print("=" * 60)
        return False

if __name__ == "__main__":
    success = test_database_connection()
    sys.exit(0 if success else 1)

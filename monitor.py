import time
import socket
import urllib.request
import os
import sys

import urllib.error

# Define configuration
DB_PORT = 5432
BACKEND_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:5173"
LOG_FILE = "monitor.log"

def log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    entry = f"[{timestamp}] {message}"
    print(entry, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(entry + "\n")

def check_port(port, service_name):
    try:
        with socket.create_connection(("localhost", port), timeout=2):
            return True
    except Exception:
        return False

def check_http(url, service_name):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return True
    except urllib.error.HTTPError as e:
        # If the server responded with an HTTP status code (even 404), it is alive
        return True
    except Exception:
        return False


def check_db_seeded():
    # Attempt to query the backend database endpoint to verify seeding is complete
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/api/customers", timeout=2) as response:
            if response.status == 200:
                import json
                data = json.loads(response.read().decode('utf-8'))
                if isinstance(data, list) and len(data) > 0:
                    return f"Yes (Found {len(data)} seeded customer profiles)"
                return "No (Database empty or unseeded)"
    except Exception as e:
        return f"Unknown (Backend offline: {e})"
    return "No"

def main():
    log("=========================================")
    log("SYSTEM MONITOR STARTED")
    log("=========================================")
    
    # Initialize monitor file
    if os.path.exists(LOG_FILE):
        try:
            os.remove(LOG_FILE)
        except Exception:
            pass

    try:
        while True:
            # 1. Check PostgreSQL
            db_alive = check_port(DB_PORT, "PostgreSQL")
            db_status = "ONLINE" if db_alive else "OFFLINE"
            
            # 2. Check Backend API
            backend_alive = check_http(BACKEND_URL, "FastAPI Backend")
            backend_status = "ONLINE" if backend_alive else "OFFLINE"
            
            # 3. Check Database Seeding status
            seeded_status = "N/A (Backend offline)"
            if backend_alive:
                seeded_status = check_db_seeded()
                
            # 4. Check Frontend
            frontend_alive = check_http(FRONTEND_URL, "Vite Frontend")
            frontend_status = "ONLINE" if frontend_alive else "OFFLINE"
            
            # Log summary
            log(f"STATUS -> Postgres (Port {DB_PORT}): {db_status} | Backend: {backend_status} (Seeded: {seeded_status}) | Frontend: {frontend_status}")
            
            time.sleep(10)
    except KeyboardInterrupt:
        log("System monitor stopped by user.")
    except Exception as e:
        log(f"System monitor encountered error: {e}")

if __name__ == "__main__":
    main()

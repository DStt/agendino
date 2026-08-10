#!/usr/bin/env python
"""
Quick start script for running Agendino with Celery task queue.
This script shows how to set up and run both the FastAPI app and Celery worker.
"""

import subprocess
import sys
import os
import time

def main():
    print("🚀 Agendino Celery Setup")
    print("=" * 50)
    
    # Step 1: Install dependencies
    print("\n1️⃣  Installing dependencies...")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], cwd=".")
    if result.returncode != 0:
        print("❌ Failed to install dependencies")
        return False
    
    print("✅ Dependencies installed")
    
    # Step 2: Check Redis
    print("\n2️⃣  Checking Redis connection...")
    try:
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0)
        r.ping()
        print("✅ Redis is running and accessible")
    except Exception as e:
        print(f"⚠️  Redis not found at localhost:6379")
        print(f"   Error: {e}")
        print("\n   To start Redis:")
        print("   - On Linux/Mac: redis-server")
        print("   - On Docker: docker run -p 6379:6379 redis")
        print("   - On Windows: Use Windows Subsystem for Linux or Docker")
        return False
    
    # Step 3: Start Celery worker
    print("\n3️⃣  Starting Celery worker...")
    print("   Run this command in a new terminal:")
    print("   $ cd src && celery -A celery_tasks worker --loglevel=info")
    print()
    
    # Step 4: Start FastAPI app
    print("4️⃣  Starting FastAPI application...")
    print("   Run this command:")
    print("   $ cd src && uvicorn main:app --reload")
    print()
    
    print("=" * 50)
    print("📝 NEXT STEPS:")
    print()
    print("1. In Terminal 1 (if not already running):")
    print("   $ redis-server")
    print()
    print("2. In Terminal 2:")
    print("   $ cd src && celery -A celery_tasks worker --loglevel=info")
    print()
    print("3. In Terminal 3:")
    print("   $ cd src && uvicorn main:app --reload --host 0.0.0.0")
    print()
    print("4. Open browser: http://localhost:8000")
    print()
    print("=" * 50)
    print()
    print("✨ Your transcription, summarization, and task generation")
    print("   requests will now be handled by Celery workers!")
    print()
    print("💡 TIP: You can now scale by adding more Celery workers:")
    print("   $ celery -A celery_tasks worker --loglevel=info")
    print()

if __name__ == "__main__":
    main()

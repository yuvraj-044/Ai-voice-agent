#!/usr/bin/env bash
# ResumeFlow Interview Studio — local run script
# Starts the server on http://localhost:8005 (port 8000 is used by another local app)
cd "$(dirname "$0")"
exec .venv/bin/uvicorn backend.app:app --host 127.0.0.1 --port 8005 --reload

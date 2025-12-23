#!/bin/bash
export FLASK_APP=app.py
export FLASK_ENV=development
if [ -d ".venv" ]; then
    ./.venv/bin/python app.py
else
    python3 app.py
fi

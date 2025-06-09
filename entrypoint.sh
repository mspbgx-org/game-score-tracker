#!/bin/sh
echo "Running DB migration..."
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
echo "Starting Gunicorn..."
exec gunicorn --bind 0.0.0.0:5000 app:app
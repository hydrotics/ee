"""
WSGI entry point for Gunicorn
This file allows Gunicorn to import the Flask app separately from the Discord bot
"""
from main import app

if __name__ == "__main__":
    app.run()

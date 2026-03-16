"""
run.py — Ponto de entrada Luzinete Turismo

Desenvolvimento:
    python run.py

Producao (recomendado):
    pip install gunicorn
    gunicorn "backend.app:create_app()" -w 2 -b 0.0.0.0:5000 --timeout 120
"""
import os
from backend.app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.getenv("FLASK_ENV", "development") == "development"
    port  = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=debug)

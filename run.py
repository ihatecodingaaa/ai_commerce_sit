"""Development entrypoint. Run: python run.py

For anything resembling production, use a real WSGI server (gunicorn/
waitress) -- see README.md. This lab still binds Flask's dev server since
the target is a small, single-tenant EC2 training instance.
"""
from app import create_app
from app.config import config

app = create_app()

if __name__ == "__main__":
    # threaded=True matters here specifically: a chatbot request can take
    # 20s-2min on CPU-only inference (see docs/instructor-guide.md). Without
    # it, Werkzeug's dev server handles one request at a time, so an
    # in-flight chat POST would block every other request -- including
    # simple page navigations -- until it finished.
    app.run(host=config.FLASK_HOST, port=config.FLASK_PORT, debug=config.FLASK_DEBUG, threaded=True)

import threading
import time

import webview
from app import app  # Your Flask app

def start_flask():
    app.run(debug=False, use_reloader=False)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=start_flask)
    flask_thread.daemon = True
    flask_thread.start()

    time.sleep(1.5)  # wait for Flask to start

    webview.create_window("Pantry Organizer", "http://127.0.0.1:5000")

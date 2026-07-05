import os
import sys

if __package__ is None or __package__ == "":
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from backend.factory import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.debug, port=5000)

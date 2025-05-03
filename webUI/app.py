# webUI/app.py

from webUI import create_app

def start_webUI():
    app = create_app()
    app.run(debug=True, port=5000, use_reloader=False)

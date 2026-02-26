"""
WSGI entry point for the Framework Mapper application.
"""
from run import create_app

app = create_app()

if __name__ == "__main__":
    app.run()

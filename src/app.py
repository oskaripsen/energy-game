from flask import Flask
from api.endpoints import register_endpoints

def create_app():
    app = Flask(__name__)
    
    # Register API endpoints
    register_endpoints(app)

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
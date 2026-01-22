from flask import Flask

def create_app():
    app = Flask(__name__)

    from .teacher.routes import teacher_bp
    app.register_blueprint(teacher_bp)

    @app.route('/')
    def index():
        return "Cook.ai Backend is running with the new structure!"

    return app
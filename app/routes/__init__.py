def register_routes(app):
    from app.routes.events import events_bp
    from app.routes.urls import urls_bp
    from app.routes.users import users_bp

    app.register_blueprint(users_bp)
    app.register_blueprint(urls_bp)
    app.register_blueprint(events_bp)

    app.register_blueprint(users_bp, url_prefix="/v1", name="users_v1")
    app.register_blueprint(urls_bp, url_prefix="/v1", name="urls_v1")
    app.register_blueprint(events_bp, url_prefix="/v1", name="events_v1")

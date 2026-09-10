def register_blueprints(app):
    from app.api.auth_routes import bp as auth_bp
    from app.api.users import bp as users_bp
    from app.api.patients import bp as patients_bp
    from app.api.screening import bp as screening_bp
    from app.api.device import bp as device_bp
    from app.api.referrals import bp as referrals_bp
    from app.api.dashboard import bp as dashboard_bp

    for bp in (auth_bp, users_bp, patients_bp, screening_bp, device_bp, referrals_bp, dashboard_bp):
        app.register_blueprint(bp)

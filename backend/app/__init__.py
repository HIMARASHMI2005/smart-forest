import os
from flask import Flask
from backend.app.config import Config
from backend.app.extensions import db, jwt, cors, socketio


def create_app(config_class=Config):
    """
    Flask Application Factory.
    Creates and configures the Smart Forest Monitoring System application.
    """
    # Template and static folders are in frontend/
    project_root = Config.PROJECT_ROOT
    template_dir = os.path.join(project_root, "frontend", "templates")
    static_dir   = os.path.join(project_root, "frontend", "static")

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
        static_url_path="/static"
    )
    app.config.from_object(config_class)

    # Initialize Flask extensions
    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    socketio.init_app(app)

    # Ensure upload directories exist
    for folder_key in ["UPLOAD_FOLDER", "SNAPSHOTS_FOLDER", "FACES_UPLOAD_FOLDER", "SOS_FOLDER"]:
        folder = app.config.get(folder_key)
        if folder:
            os.makedirs(folder, exist_ok=True)

    # Register all route blueprints
    from backend.app.routes import (
        auth_bp, user_bp, admin_bp, ai_bp,
        geofence_bp, sos_bp, views_bp, visitor_bp, location_bp
    )
    app.register_blueprint(views_bp)
    app.register_blueprint(visitor_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(user_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(ai_bp)
    app.register_blueprint(geofence_bp)
    app.register_blueprint(sos_bp)
    app.register_blueprint(location_bp)

    # Register SocketIO events
    _register_socketio_events(socketio)

    # Create DB tables and seed initial data
    with app.app_context():
        _initialize_database(app)
        from backend.app.services.visitor_service import init_visitor_tables, reload_embeddings_cache
        init_visitor_tables()
        reload_embeddings_cache()

    return app


def _register_socketio_events(sio):
    """Socket.IO connection/disconnection event handlers."""

    @sio.on("connect")
    def handle_connect():
        print("[SocketIO] Client connected.")

    @sio.on("disconnect")
    def handle_disconnect():
        print("[SocketIO] Client disconnected.")

    @sio.on("join_admin")
    def handle_join_admin(data=None):
        from flask_socketio import join_room
        join_room("admin_room")
        sio.emit("joined", {"message": "Joined admin room."})


def _initialize_database(app):
    """Creates tables and seeds initial zones if database is empty."""
    try:
        db.create_all()
        # Safe migration check for columns on existing tables
        try:
            from sqlalchemy import text
            with db.engine.connect() as conn:
                def get_cols(table_name):
                    if db.engine.name == "sqlite":
                        return [row[1] for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()]
                    else:
                        return [row[0] for row in conn.execute(text(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='{table_name}'")).fetchall()]

                # locations
                loc_cols = get_cols("locations")
                for col_name in ["altitude", "heading", "speed"]:
                    if col_name not in loc_cols:
                        conn.execute(text(f"ALTER TABLE locations ADD COLUMN {col_name} FLOAT"))
                        conn.commit()

                # users
                user_cols = get_cols("users")
                if "forest_user_id" not in user_cols:
                    conn.execute(text("ALTER TABLE users ADD COLUMN forest_user_id VARCHAR(50)"))
                    conn.commit()

                # sos_events
                sos_cols = get_cols("sos_events")
                if "video_filename" not in sos_cols:
                    conn.execute(text("ALTER TABLE sos_events ADD COLUMN video_filename VARCHAR(255)"))
                    conn.commit()
        except Exception as col_err:
            app.logger.warning(f"Column migration check: {col_err}")
        app.logger.info("[SUCCESS] Database tables created/verified.")
        _seed_initial_data()
    except Exception as e:
        app.logger.error(f"[ERROR] Database initialization error: {e}")
        app.logger.error(
            f"  Check MySQL is running and credentials in .env are correct.\n"
            f"  DB_HOST={app.config.get('DB_HOST')} "
            f"DB_PORT={app.config.get('DB_PORT')} "
            f"DB_NAME={app.config.get('DB_NAME')} "
            f"DB_USER={app.config.get('DB_USER')}"
        )


def _seed_initial_data():
    """Seeds default admin user and sample forest zones if tables are empty."""
    from backend.app.models import User, ForestZone

    # Ensure all existing users have forest_user_id
    for u in User.query.filter((User.forest_user_id == None) | (User.forest_user_id == "")).all():
        u.forest_user_id = User.generate_forest_id()
    db.session.commit()

    # Seed admin user
    if not User.query.filter_by(email="admin@smartforest.org").first():
        admin = User(
            forest_user_id="FOR-AD0001",
            name="Chief Warden",
            email="admin@smartforest.org",
            phone="+91 9000000001",
            role="ADMIN",
            emergency_contact="+91 9000000000",
            status="ACTIVE"
        )
        admin.set_password("Admin@123")
        db.session.add(admin)

    # Seed sample registered users Rahul and Priya
    if not User.query.filter_by(email="rahul.test@forest.gov").first():
        rahul = User(
            forest_user_id="FOR-RH1001",
            name="Rahul",
            email="rahul.test@forest.gov",
            phone="+91 9876543201",
            role="USER",
            emergency_contact="+91 9876543200",
            status="ACTIVE"
        )
        rahul.set_password("SecurePass123!")
        db.session.add(rahul)

    if not User.query.filter_by(email="priya.test@forest.gov").first():
        priya = User(
            forest_user_id="FOR-PR1002",
            name="Priya",
            email="priya.test@forest.gov",
            phone="+91 9876543202",
            role="USER",
            emergency_contact="+91 9876543200",
            status="ACTIVE"
        )
        priya.set_password("SecurePass123!")
        db.session.add(priya)
    db.session.commit()

    # Seed sample forest zones (Nilgiri region)
    if ForestZone.query.count() == 0:
        zones = [
            ForestZone(
                name="North Visitor Eco-Trail",
                code="ZONE-SAFE-01",
                boundary_geojson={
                    "type": "Polygon",
                    "coordinates": [[[76.620, 11.650], [76.635, 11.650],
                                     [76.635, 11.662], [76.620, 11.662], [76.620, 11.650]]]
                },
                risk_level="LOW",
                description="Authorized tourism and eco-trail area.",
                is_active=True
            ),
            ForestZone(
                name="Pine Ridge Buffer Zone",
                code="ZONE-MED-02",
                boundary_geojson={
                    "type": "Polygon",
                    "coordinates": [[[76.635, 11.650], [76.655, 11.650],
                                     [76.655, 11.668], [76.635, 11.668], [76.635, 11.650]]]
                },
                risk_level="MEDIUM",
                description="Semi-restricted buffer zone with limited night access.",
                is_active=True
            ),
            ForestZone(
                name="Wild Elephant Corridor",
                code="ZONE-HIGH-03",
                boundary_geojson={
                    "type": "Polygon",
                    "coordinates": [[[76.615, 11.665], [76.640, 11.665],
                                     [76.640, 11.685], [76.615, 11.685], [76.615, 11.665]]]
                },
                risk_level="HIGH",
                description="Active wildlife movement zone ? entry requires escort.",
                is_active=True
            ),
            ForestZone(
                name="Blackwood Gorge Critical Zone",
                code="ZONE-CRIT-04",
                boundary_geojson={
                    "type": "Polygon",
                    "coordinates": [[[76.645, 11.670], [76.670, 11.670],
                                     [76.670, 11.695], [76.645, 11.695], [76.645, 11.670]]]
                },
                risk_level="CRITICAL",
                description="Hazardous terrain with unstable cliffs. Strictly no entry.",
                is_active=True
            ),
        ]
        db.session.add_all(zones)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[Seed Data Error]: {e}")

from flask import Blueprint, render_template, redirect, url_for

views_bp = Blueprint("views", __name__)


@views_bp.route("/")
@views_bp.route("/portal")
def index():
    return render_template("index.html")

@views_bp.route("/officer")
@views_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")

@views_bp.route("/register")
def register():
    return render_template("register.html")

@views_bp.route("/login")
def login():
    return render_template("login.html")

@views_bp.route("/live-monitor")
@views_bp.route("/live_monitor")
def live_monitor():
    return render_template("live_monitor.html")

@views_bp.route("/geofence")
def geofence():
    return render_template("geofence.html")

@views_bp.route("/sos")
def sos():
    return render_template("sos.html")

@views_bp.route("/face-register")
@views_bp.route("/face_register")
def face_register():
    return render_template("face_register.html")

@views_bp.route("/profile")
def profile():
    return render_template("profile.html")

@views_bp.route("/alerts")
def alerts():
    return redirect("/officer#alerts")

@views_bp.route("/admin")
@views_bp.route("/admin_dashboard")
def admin_dashboard():
    return render_template("admin_dashboard.html")



"""사서 로그인 / 로그아웃."""
from functools import wraps
from urllib.parse import urlsplit

from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from .db import query_one

bp = Blueprint("auth", __name__)


def safe_next(default):
    """로그인 후 돌아갈 주소. 같은 사이트의 경로만 허용한다 (오픈 리다이렉트 방지)."""
    next_url = request.args.get("next", "")
    if not next_url or any(ord(ch) < 32 for ch in next_url) or "\\" in next_url:
        return default
    parts = urlsplit(next_url)
    if parts.scheme or parts.netloc or not parts.path.startswith("/") or parts.path.startswith("//"):
        return default
    return next_url


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        staff = query_one(
            "SELECT staff_id, name, role, password_hash FROM staff WHERE login_id = %s",
            (request.form.get("login_id", "").strip(),),
        )
        if staff and check_password_hash(staff["password_hash"], request.form.get("password", "")):
            for key in ("staff_id", "staff_name", "staff_role"):
                session.pop(key, None)
            session["staff_id"] = staff["staff_id"]
            session["staff_name"] = staff["name"]
            session["staff_role"] = staff["role"]
            return redirect(safe_next(url_for("main.index")))
        flash("아이디 또는 비밀번호가 올바르지 않습니다.", "error")
    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    for key in ("staff_id", "staff_name", "staff_role"):
        session.pop(key, None)
    return redirect(url_for("auth.login"))


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if session.get("staff_role") != "관리자":
            flash("관리자만 처리할 수 있습니다.", "error")
            return redirect(request.referrer or url_for("main.index"))
        return view(*args, **kwargs)

    return wrapped

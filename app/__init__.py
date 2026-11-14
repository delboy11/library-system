from datetime import date
from pathlib import Path

from urllib.parse import urlsplit

from flask import Flask, abort, redirect, request, session, url_for

from config import Config

from . import db

# 로그인 없이 접근 가능한 화면
PUBLIC_ENDPOINTS = {None, "static", "auth.login", "portal.login"}


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.jinja_env.add_extension("jinja2.ext.do")
    db.init_app(app)

    from . import auth, books, closed_days, loans, main, members, overdue, portal, stats

    for module in (auth, main, books, members, loans, overdue, closed_days, stats, portal):
        app.register_blueprint(module.bp)

    @app.before_request
    def check_same_origin():
        # CSRF 방어: 상태를 바꾸는 POST 는 같은 사이트에서 온 요청만 받는다
        if request.method != "POST":
            return None
        source = request.headers.get("Origin") or request.headers.get("Referer")
        if source and urlsplit(source).netloc != request.host:
            abort(403)
        return None

    @app.before_request
    def require_login():
        endpoint = request.endpoint
        if endpoint in PUBLIC_ENDPOINTS:
            return None
        # 회원 포털(/my)은 회원 로그인, 나머지는 사서 로그인이 필요하다
        if endpoint.startswith("portal."):
            if "member_id" not in session:
                return redirect(url_for("portal.login", next=request.full_path))
        elif "staff_id" not in session:
            return redirect(url_for("auth.login", next=request.full_path))
        return None

    @app.template_filter("won")
    def won(value):
        return f"{int(value or 0):,}원"

    @app.template_filter("d")
    def format_date(value, fmt="%Y-%m-%d"):
        return value.strftime(fmt) if value else "-"

    @app.context_processor
    def inject_globals():
        # asset_v : 스타일시트가 바뀌면 주소가 달라져 브라우저가 옛 파일을 쓰지 않는다
        css = Path(app.static_folder) / "style.css"
        return {"today": date.today(), "asset_v": int(css.stat().st_mtime)}

    return app

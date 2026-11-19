import socket
from datetime import date
from pathlib import Path

from urllib.parse import urlsplit

import pymysql
from flask import Flask, abort, redirect, render_template, request, session, url_for

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
        return {"today": date.today(), "asset_v": int(css.stat().st_mtime), "system_info": system_info}

    def system_info():
        """화면 아래 시스템 구성 줄 : 브라우저 → 웹 서버 → DB 서버 (사서 화면에서만 호출)"""
        try:
            info = db.server_info()
        except pymysql.MySQLError:
            info = None
        return {"browser": request.remote_addr, "app_host": socket.gethostname(), "db": info}

    @app.errorhandler(pymysql.MySQLError)
    def database_unavailable(exc):
        # DB 서버(다른 PC)에 닿지 못하면 오류 화면 대신 원인과 점검 순서를 보여 준다
        if not db.is_connection_error(exc):
            raise exc
        app.logger.error("DB 서버 연결 실패: %s", exc)
        return render_template("db_error.html", error=exc, db_host=app.config["DB_HOST"],
                               db_port=app.config["DB_PORT"]), 503

    return app

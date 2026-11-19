"""웹 서버(Flask) 실행.

DB 서버는 다른 PC 다. 접속할 DB 서버는 환경변수 DB_HOST 로 정한다 (config.py).
  APP_HOST : 웹 서버가 받을 주소. 기본 127.0.0.1(이 PC 브라우저만). 0.0.0.0 이면 폰 등 다른 기기에서도 접속
  APP_PORT : 기본 5000
"""
import os

import pymysql

from app import create_app

app = create_app()


def check_db():
    """시작하기 전에 DB 서버에 닿는지 확인하고 결과를 한 줄로 보여 준다."""
    cfg = app.config
    try:
        conn = pymysql.connect(host=cfg["DB_HOST"], port=cfg["DB_PORT"], user=cfg["DB_USER"],
                               password=cfg["DB_PASSWORD"], database=cfg["DB_NAME"], connect_timeout=5)
        with conn.cursor() as cur:
            cur.execute("SELECT @@hostname, @@version, USER(), NOW()")
            hostname, version, user, now = cur.fetchone()
        conn.close()
        print(f" * DB 서버 연결 OK : {cfg['DB_HOST']}:{cfg['DB_PORT']} (호스트 {hostname}, MySQL {version}, "
              f"접속 계정 {user}, DB 시각 {now:%Y-%m-%d %H:%M})")
    except pymysql.MySQLError as e:
        print(f" * DB 서버 연결 실패 : {cfg['DB_HOST']}:{cfg['DB_PORT']} → {e}")
        print("   Tailscale 연결, DB 서버의 MySQL 실행 여부, DB_HOST 값을 확인하세요. (README 'DB 서버 분리')")


if __name__ == "__main__":
    host = os.environ.get("APP_HOST", "127.0.0.1")
    port = int(os.environ.get("APP_PORT", "5000"))
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":     # debug 재시작 프로세스에서는 다시 검사하지 않음
        check_db()
    # 디버거는 브라우저에서 코드를 실행할 수 있으므로 다른 기기에 열 때(0.0.0.0 등)는 끈다
    app.run(host=host, port=port, debug=host in ("127.0.0.1", "localhost"))

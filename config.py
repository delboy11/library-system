import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "library-dev-secret")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"     # 다른 사이트에서 보낸 POST 에는 세션 쿠키가 실리지 않음
    DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.environ.get("DB_PORT", "3306"))
    DB_USER = os.environ.get("DB_USER", "library")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "library1234")
    DB_NAME = os.environ.get("DB_NAME", "library_db")

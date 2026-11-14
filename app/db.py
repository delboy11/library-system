"""MySQL 연결 및 쿼리 헬퍼 (PyMySQL)."""
from contextlib import contextmanager

import pymysql
from flask import current_app, g

# 제약조건 이름 → 사용자에게 보여줄 메시지
CONSTRAINT_MESSAGES = {
    "uq_member_no": "이미 등록된 학번(교번)입니다.",
    "uq_member_phone": "이미 등록된 전화번호입니다.",
    "uq_member_email": "이미 등록된 이메일입니다.",
    "ck_member_no": "학번(교번)은 영문·숫자 4~20자여야 합니다.",
    "ck_member_phone": "전화번호 형식이 올바르지 않습니다. (예: 010-1234-5678)",
    "book.PRIMARY": "이미 등록된 ISBN입니다.",
    "ck_book_isbn": "ISBN은 978 또는 979로 시작하는 13자리 숫자여야 합니다.",
    "ck_book_pub_year": "발행연도가 올바르지 않습니다.",
    "uq_book_copy_reg_no": "이미 사용 중인 등록번호입니다.",
    "uq_loan_active_copy": "이미 대출 중인 복본입니다.",
    "ck_suspension_reason": "정지 사유가 올바르지 않습니다.",
    "fk_loan_copy": "대출 이력이 있는 도서는 삭제할 수 없습니다. 복본을 폐기 처리하세요.",
    "fk_member_type": "존재하지 않는 회원구분입니다.",
}

# MySQL 오류 코드 → 기본 메시지
ERROR_MESSAGES = {
    1048: "필수 항목이 비어 있습니다.",
    1062: "중복된 값입니다.",
    1406: "입력값이 너무 깁니다.",
    1451: "다른 데이터에서 참조 중이라 삭제할 수 없습니다.",
    1452: "참조하는 데이터가 존재하지 않습니다.",
    3819: "입력값이 제약조건을 위반했습니다.",
}


def get_db():
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["DB_HOST"],
            port=cfg["DB_PORT"],
            user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"],
            database=cfg["DB_NAME"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
        )
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def query(sql, args=None):
    with get_db().cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def query_one(sql, args=None):
    rows = query(sql, args)
    return rows[0] if rows else None


@contextmanager
def transaction():
    """여러 SQL을 하나의 트랜잭션으로 묶는다. 예외 발생 시 롤백."""
    db = get_db()
    try:
        with db.cursor() as cur:
            yield cur
        db.commit()
    except Exception:
        db.rollback()
        raise


def execute(sql, args=None):
    with transaction() as cur:
        cur.execute(sql, args)
        return cur.lastrowid


def execute_rowcount(sql, args=None):
    """UPDATE/DELETE 를 실행하고 바뀐 행 수를 돌려준다."""
    with transaction() as cur:
        return cur.execute(sql, args)


def call_proc(name, *args):
    """저장 프로시저를 호출하고 첫 번째 결과 행을 반환한다."""
    placeholders = ", ".join(["%s"] * len(args))
    with transaction() as cur:
        cur.execute(f"CALL {name}({placeholders})", args)
        row = cur.fetchone()
        while cur.nextset():
            pass
    return row


def error_message(exc):
    """pymysql 예외를 화면에 표시할 한국어 메시지로 변환."""
    code = exc.args[0] if exc.args else None
    detail = exc.args[1] if len(exc.args) > 1 else str(exc)
    if code == 1644:  # 프로시저/트리거의 SIGNAL SQLSTATE '45000'
        return detail
    for name, msg in CONSTRAINT_MESSAGES.items():
        if f"'{name}'" in detail or f".{name}'" in detail or f"`{name}`" in detail:
            return msg
    if code in ERROR_MESSAGES:
        return ERROR_MESSAGES[code]
    current_app.logger.warning("MySQL 오류 %s: %s", code, detail)
    return f"처리 중 오류가 발생했습니다. (오류 코드 {code})"

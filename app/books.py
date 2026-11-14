"""도서 관리 : 도서 등록(국립중앙도서관 API 조회), 정보 수정, 폐기 처리, 도서 검색, 복본 관리."""
import re
from datetime import date

import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from . import nl_api
from .db import error_message, execute, query, query_one, transaction

bp = Blueprint("books", __name__, url_prefix="/books")

# 사서가 직접 바꿀 수 있는 복본 상태 ('대출중'은 대출·반납 처리로만 바뀐다)
COPY_STATUSES_MANUAL = ("대출가능", "분실", "폐기")


EXTRA_ROLES = ("엮은이", "그림")


def split_names(text):
    """'홍길동, 김철수' → ['홍길동', '김철수'] (중복 제거, 순서 유지)"""
    names = [n.strip() for n in (text or "").split(",")]
    return list(dict.fromkeys(n for n in names if n))


def parse_writer(text):
    """'홍길동 (엮은이)' → ('홍길동', '엮은이'),  '홍길동' → ('홍길동', '지은이')"""
    m = re.fullmatch(r"(.+?)\s*\((지은이|엮은이|그림)\)", text)
    return (m.group(1).strip(), m.group(2)) if m else (text, "지은이")


def format_writers(authors):
    """book_author 행 → 지은이 입력란 문자열 (엮은이·그림은 역할을 괄호로 표시해 수정 시 보존)"""
    return ", ".join(a["author_name"] if a["author_role"] == "지은이" else f"{a['author_name']} ({a['author_role']})"
                     for a in authors if a["author_role"] != "옮긴이")


def form_int(name, default, low, high):
    """폼의 정수 값을 범위 안으로 읽는다 (숫자가 아니면 기본값)"""
    value = request.form.get(name, type=int)
    return default if value is None else max(low, min(high, value))


def get_or_create(cur, select_sql, insert_sql, value):
    cur.execute(select_sql, (value,))
    row = cur.fetchone()
    if row:
        return next(iter(row.values()))
    cur.execute(insert_sql, (value,))
    return cur.lastrowid


def save_authors(cur, isbn, writers, translators):
    cur.execute("DELETE FROM book_author WHERE isbn = %s", (isbn,))
    order = 0
    seen = set()
    entries = [parse_writer(w) for w in writers] + [(t, "옮긴이") for t in translators]
    for name, role in entries:
        author_id = get_or_create(
            cur,
            "SELECT author_id FROM author WHERE author_name = %s ORDER BY author_id LIMIT 1",
            "INSERT INTO author (author_name) VALUES (%s)",
            name,
        )
        if author_id in seen:       # 같은 사람이 두 역할이면 처음 역할만 (PK: isbn, author_id)
            continue
        seen.add(author_id)
        order += 1
        cur.execute(
            "INSERT INTO book_author (isbn, author_id, author_role, author_order) VALUES (%s, %s, %s, %s)",
            (isbn, author_id, role, order),
        )


def add_copies(cur, isbn, count, location, call_no):
    """복본을 count권 등록한다. 등록번호는 마지막 번호 다음부터 부여."""
    cur.execute("SELECT COALESCE(MAX(CAST(SUBSTRING(reg_no, 3) AS UNSIGNED)), 0) AS n FROM book_copy")
    next_no = int(cur.fetchone()["n"]) + 1
    cur.execute("SELECT COUNT(*) AS n FROM book_copy WHERE isbn = %s", (isbn,))
    existing = cur.fetchone()["n"]
    for i in range(count):
        seq = existing + i + 1
        cur.execute(
            "INSERT INTO book_copy (reg_no, isbn, call_no, location) VALUES (%s, %s, %s, %s)",
            (f"EM{next_no + i:06d}", isbn, call_no if seq == 1 else f"{call_no} c.{seq}", location),
        )


def book_form_values(form):
    pub_year = form.get("pub_year", "").strip()
    price = form.get("price", "").strip()
    kdc_no = form.get("kdc_no", "").strip() or None
    return {
        "isbn": re.sub(r"[^0-9]", "", form.get("isbn", "")),
        "title": form.get("title", "").strip(),
        "publisher_name": form.get("publisher_name", "").strip(),
        "category_code": form.get("category_code", "") or nl_api.kdc_main(kdc_no) or "000",
        "kdc_no": kdc_no,
        "pub_year": int(pub_year) if pub_year.isdigit() else None,
        "pub_year_text": pub_year,
        "price": int(price) if price.isdigit() else None,
        "writers": form.get("writers", ""),
        "translators": form.get("translators", ""),
    }


def validate_book(values):
    """입력 검증. 문제가 있으면 메시지, 없으면 None"""
    if not values["title"] or not values["publisher_name"] or not split_names(values["writers"]):
        return "서명, 출판사, 지은이는 필수입니다."
    if values["pub_year_text"] and values["pub_year"] is None:
        return "발행연도는 숫자로 입력하세요."
    if values["pub_year"] and values["pub_year"] > date.today().year + 1:
        return "발행연도가 올바르지 않습니다. (내년 이후 불가)"
    return None


def categories():
    return query("SELECT category_code, category_name FROM category ORDER BY category_code")


def save_book(cur, values, is_new):
    publisher_id = get_or_create(
        cur,
        "SELECT publisher_id FROM publisher WHERE publisher_name = %s",
        "INSERT INTO publisher (publisher_name) VALUES (%s)",
        values["publisher_name"],
    )
    if is_new:
        cur.execute(
            """INSERT INTO book (isbn, title, publisher_id, category_code, kdc_no, pub_year, price)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (values["isbn"], values["title"], publisher_id, values["category_code"], values["kdc_no"],
             values["pub_year"], values["price"]),
        )
    else:
        cur.execute(
            """UPDATE book SET title = %s, publisher_id = %s, category_code = %s, kdc_no = %s,
                               pub_year = %s, price = %s
                WHERE isbn = %s""",
            (values["title"], publisher_id, values["category_code"], values["kdc_no"],
             values["pub_year"], values["price"], values["isbn"]),
        )
    save_authors(cur, values["isbn"], split_names(values["writers"]), split_names(values["translators"]))


@bp.route("/")
def list_books():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "")
    like = f"%{q}%"
    books = query(
        """
        SELECT * FROM v_book_summary
         WHERE (%s = '' OR title LIKE %s OR authors LIKE %s OR publisher_name LIKE %s OR isbn = %s)
           AND (%s = '' OR category_code = %s)
         ORDER BY title
        """,
        (q, like, like, like, q, category, category),
    )
    return render_template("books/list.html", books=books, q=q, category=category, categories=categories())


@bp.route("/<isbn>")
def detail(isbn):
    book = query_one("SELECT * FROM v_book_summary WHERE isbn = %s", (isbn,))
    if not book:
        abort(404)
    copies = query(
        """
        SELECT bc.copy_id, bc.reg_no, bc.call_no, bc.location, bc.status, bc.acquired_date, bc.removed_date,
               l.loan_id, l.due_date, m.member_id, m.name AS member_name
          FROM book_copy bc
          LEFT JOIN loan l   ON l.copy_id = bc.copy_id AND l.return_date IS NULL
          LEFT JOIN member m ON m.member_id = l.member_id
         WHERE bc.isbn = %s
         ORDER BY bc.reg_no
        """,
        (isbn,),
    )
    loan_count = query_one(
        "SELECT COUNT(*) AS n FROM loan l JOIN book_copy bc ON bc.copy_id = l.copy_id WHERE bc.isbn = %s",
        (isbn,),
    )["n"]
    return render_template("books/detail.html", book=book, copies=copies, loan_count=loan_count,
                           manual_statuses=COPY_STATUSES_MANUAL)


@bp.route("/new", methods=["GET", "POST"])
def new():
    values = {"copy_count": 1, "location": "종합자료실"}
    lookup_isbn = re.sub(r"[^0-9]", "", request.args.get("lookup", ""))
    if request.method == "GET" and lookup_isbn:
        # 국립중앙도서관 API 로 ISBN 서지정보를 불러와 입력란을 채운다
        try:
            found = nl_api.fetch_by_isbn(lookup_isbn)
            if found:
                values.update(found)
                values["publisher_name"] = found["publisher"]
                values["writers"] = ", ".join(n if r == "지은이" else f"{n} ({r})"
                                              for n, r in found["authors"] if r != "옮긴이")
                values["translators"] = ", ".join(n for n, r in found["authors"] if r == "옮긴이")
                flash("국립중앙도서관에서 서지정보를 불러왔습니다. 확인 후 등록하세요.", "info")
            else:
                values["isbn"] = lookup_isbn
                flash("국립중앙도서관에 해당 ISBN 의 서지정보가 없습니다.", "warning")
        except nl_api.NLApiError as e:
            values["isbn"] = lookup_isbn
            flash(str(e), "error")
    if request.method == "POST":
        values = book_form_values(request.form)
        values["copy_count"] = form_int("copy_count", 1, 0, 10)
        values["location"] = request.form.get("location", "").strip() or "종합자료실"
        values["call_no"] = request.form.get("call_no", "").strip() or values["kdc_no"] or values["category_code"]
        problem = validate_book(values)
        if problem:
            flash(problem, "error")
        else:
            try:
                with transaction() as cur:
                    save_book(cur, values, is_new=True)
                    add_copies(cur, values["isbn"], values["copy_count"], values["location"], values["call_no"])
                flash(f"'{values['title']}' 도서를 등록했습니다.", "success")
                return redirect(url_for("books.detail", isbn=values["isbn"]))
            except pymysql.MySQLError as e:
                flash(error_message(e), "error")
    return render_template("books/form.html", values=values, categories=categories(), is_new=True,
                           api_enabled=bool(nl_api.cert_key()))


@bp.route("/<isbn>/edit", methods=["GET", "POST"])
def edit(isbn):
    book = query_one("SELECT * FROM v_book_summary WHERE isbn = %s", (isbn,))
    if not book:
        abort(404)
    if request.method == "POST":
        values = book_form_values(request.form)
        values["isbn"] = isbn
        problem = validate_book(values)
        if problem:
            flash(problem, "error")
        else:
            try:
                with transaction() as cur:
                    save_book(cur, values, is_new=False)
                flash("도서 정보를 수정했습니다.", "success")
                return redirect(url_for("books.detail", isbn=isbn))
            except pymysql.MySQLError as e:
                flash(error_message(e), "error")
    else:
        authors = query(
            """SELECT a.author_name, ba.author_role FROM book_author ba
                 JOIN author a ON a.author_id = ba.author_id
                WHERE ba.isbn = %s ORDER BY ba.author_order""",
            (isbn,),
        )
        values = dict(book)
        values["writers"] = format_writers(authors)
        values["translators"] = ", ".join(a["author_name"] for a in authors if a["author_role"] == "옮긴이")
    return render_template("books/form.html", values=values, categories=categories(), is_new=False,
                           api_enabled=False)


@bp.route("/<isbn>/delete", methods=["POST"])
def delete(isbn):
    try:
        execute("DELETE FROM book WHERE isbn = %s", (isbn,))
        flash("도서를 삭제했습니다.", "success")
        return redirect(url_for("books.list_books"))
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
        return redirect(url_for("books.detail", isbn=isbn))


@bp.route("/<isbn>/copies", methods=["POST"])
def add_copy(isbn):
    book = query_one("SELECT category_code, kdc_no FROM book WHERE isbn = %s", (isbn,))
    if not book:
        abort(404)
    count = form_int("count", 1, 1, 10)
    location = request.form.get("location", "").strip() or "종합자료실"
    first = query_one("SELECT call_no FROM book_copy WHERE isbn = %s ORDER BY copy_id LIMIT 1", (isbn,))
    call_no = request.form.get("call_no", "").strip() or (
        first["call_no"].split(" c.")[0] if first else (book["kdc_no"] or book["category_code"])
    )
    try:
        with transaction() as cur:
            add_copies(cur, isbn, count, location, call_no)
        flash(f"복본 {count}권을 추가했습니다.", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(url_for("books.detail", isbn=isbn))


@bp.route("/copies/<int:copy_id>/status", methods=["POST"])
def change_copy_status(copy_id):
    copy = query_one("SELECT isbn, reg_no, status FROM book_copy WHERE copy_id = %s", (copy_id,))
    if not copy:
        abort(404)
    status = request.form.get("status")
    if status not in COPY_STATUSES_MANUAL:
        abort(400)
    try:
        # 대출 중인 복본의 폐기·분실 차단과 처리일 기록은 트리거(trg_book_copy_status_guard)가 담당
        execute("UPDATE book_copy SET status = %s WHERE copy_id = %s", (status, copy_id))
        flash(f"{copy['reg_no']} 복본을 '{status}' 상태로 변경했습니다.", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(url_for("books.detail", isbn=copy["isbn"]))

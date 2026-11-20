"""회원 포털 (/my) : 학번으로 로그인해 도서 검색, 본인 대출 내역 조회, 연장 신청."""
import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .auth import safe_next
from .books import also_borrowed
from .db import call_proc, error_message, execute, query, query_one

bp = Blueprint("portal", __name__, url_prefix="/my")

MEMBER_KEYS = ("member_id", "member_name", "member_no")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        member = query_one(
            "SELECT member_id, member_no, name, status, password_hash FROM member WHERE member_no = %s",
            (request.form.get("member_no", "").strip(),),
        )
        if not member or not check_password_hash(member["password_hash"], request.form.get("password", "")):
            flash("학번(교번) 또는 비밀번호가 올바르지 않습니다.", "error")
        elif member["status"] == "탈퇴":
            flash("탈퇴한 회원입니다.", "error")
        else:
            for key in MEMBER_KEYS:
                session.pop(key, None)
            session["member_id"] = member["member_id"]
            session["member_name"] = member["name"]
            session["member_no"] = member["member_no"]
            return redirect(safe_next(url_for("portal.index")))
    return render_template("portal/login.html")


@bp.route("/logout")
def logout():
    for key in MEMBER_KEYS:
        session.pop(key, None)
    return redirect(url_for("portal.login"))


@bp.route("/")
def index():
    member_id = session["member_id"]
    member = query_one("SELECT * FROM v_member_status WHERE member_id = %s", (member_id,))
    loans = query(
        "SELECT * FROM v_loan_detail WHERE member_id = %s AND return_date IS NULL ORDER BY due_date",
        (member_id,),
    )
    history = query(
        """SELECT * FROM v_loan_detail WHERE member_id = %s AND return_date IS NOT NULL
            ORDER BY return_date DESC LIMIT 30""",
        (member_id,),
    )
    fines = query(
        """SELECT f.*, b.title FROM fine f
             JOIN loan l ON l.loan_id = f.loan_id
             JOIN book_copy bc ON bc.copy_id = l.copy_id
             JOIN book b ON b.isbn = bc.isbn
            WHERE l.member_id = %s ORDER BY f.imposed_date DESC""",
        (member_id,),
    )
    suspensions = query(
        "SELECT * FROM suspension WHERE member_id = %s ORDER BY start_date DESC LIMIT 10", (member_id,)
    )
    return render_template("portal/index.html", member=member, loans=loans, history=history,
                           fines=fines, suspensions=suspensions)


@bp.route("/loans/<int:loan_id>/renew", methods=["POST"])
def renew(loan_id):
    try:
        row = call_proc("sp_renew", loan_id, "홈페이지", None, session["member_id"])
        flash(f"'{row['title']}' 연장 완료 · 새 반납예정일 {row['due_date']:%Y-%m-%d} "
              f"(연장 {row['renew_count']}회째)", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(url_for("portal.index"))


@bp.route("/books")
def books():
    q = request.args.get("q", "").strip()
    rows = []
    if q:
        like = f"%{q}%"
        rows = query(
            """SELECT * FROM v_book_summary
                WHERE title LIKE %s OR authors LIKE %s OR publisher_name LIKE %s OR isbn = %s
                ORDER BY title LIMIT 100""",
            (like, like, like, q),
        )
    return render_template("portal/books.html", books=rows, q=q)


@bp.route("/books/<isbn>")
def book_detail(isbn):
    book = query_one("SELECT * FROM v_book_summary WHERE isbn = %s", (isbn,))
    if not book:
        abort(404)
    # 회원에게는 누가 빌렸는지 숨기고 상태·반납예정일만 보여 준다
    copies = query(
        """SELECT bc.reg_no, bc.call_no, bc.location, bc.status, l.due_date
             FROM book_copy bc
             LEFT JOIN loan l ON l.copy_id = bc.copy_id AND l.return_date IS NULL
            WHERE bc.isbn = %s AND bc.status IN ('대출가능', '대출중')
            ORDER BY bc.reg_no""",
        (isbn,),
    )
    return render_template("portal/book_detail.html", book=book, copies=copies,
                           also_borrowed=also_borrowed(isbn))


@bp.route("/password", methods=["GET", "POST"])
def password():
    if request.method == "POST":
        member = query_one("SELECT password_hash FROM member WHERE member_id = %s", (session["member_id"],))
        current = request.form.get("current", "")
        new = request.form.get("new", "")
        if not check_password_hash(member["password_hash"], current):
            flash("현재 비밀번호가 올바르지 않습니다.", "error")
        elif len(new) < 8:
            flash("새 비밀번호는 8자 이상이어야 합니다.", "error")
        elif new != request.form.get("confirm", ""):
            flash("새 비밀번호 확인이 일치하지 않습니다.", "error")
        else:
            execute("UPDATE member SET password_hash = %s WHERE member_id = %s",
                    (generate_password_hash(new), session["member_id"]))
            flash("비밀번호를 변경했습니다.", "success")
            return redirect(url_for("portal.index"))
    return render_template("portal/password.html")

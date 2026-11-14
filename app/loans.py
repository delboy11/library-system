"""대출 관리 · 반납 관리 : 대출 가능 여부 검사, 대출 처리, 대출 내역 조회, 반납 처리, 연장, 분실 처리."""
import pymysql
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .db import call_proc, error_message, query, query_one

bp = Blueprint("loans", __name__, url_prefix="/loans")

LOAN_FILTERS = {
    "active": "return_date IS NULL",
    "overdue": "loan_state = '연체'",
    "returned": "return_date IS NOT NULL",
    "all": "1 = 1",
}


def penalty_message(row):
    parts = []
    if row.get("overdue_days"):
        parts.append(f"연체 {row['overdue_days']}일")
    if row.get("fine_amount"):
        parts.append(f"연체료 {row['fine_amount']:,}원 부과")
    return " · ".join(parts)


@bp.route("/borrow", methods=["GET", "POST"])
def borrow():
    if request.method == "POST":
        member_no = request.form.get("member_no", "").strip()
        reg_no = request.form.get("reg_no", "").strip().upper()
        try:
            row = call_proc("sp_borrow", member_no, reg_no, session["staff_id"])
            flash(f"'{row['title']}' 대출 완료 · {row['member_name']} · 반납예정일 {row['due_date']:%Y-%m-%d}",
                  "success")
        except pymysql.MySQLError as e:
            flash(error_message(e), "error")
        return redirect(url_for("loans.borrow", member_no=member_no))

    member_no = request.args.get("member_no", "").strip()
    member, active_loans = None, []
    if member_no:
        member = query_one("SELECT * FROM v_member_status WHERE member_no = %s", (member_no,))
        if member:
            active_loans = query(
                "SELECT * FROM v_loan_detail WHERE member_id = %s AND return_date IS NULL ORDER BY due_date",
                (member["member_id"],),
            )
        else:
            flash("존재하지 않는 학번(교번)입니다.", "error")
    return render_template("loans/borrow.html", member_no=member_no, member=member, active_loans=active_loans)


@bp.route("/return", methods=["GET", "POST"])
def return_book():
    if request.method == "POST":
        reg_no = request.form.get("reg_no", "").strip().upper()
        try:
            row = call_proc("sp_return", reg_no, session["staff_id"])
            penalty = penalty_message(row)
            flash(f"'{row['title']}' 반납 완료 · {row['member_name']}" + (f" · {penalty}" if penalty else ""),
                  "warning" if penalty else "success")
        except pymysql.MySQLError as e:
            flash(error_message(e), "error")
        return redirect(url_for("loans.return_book"))

    returned_today = query(
        "SELECT * FROM v_loan_detail WHERE DATE(return_date) = CURDATE() ORDER BY return_date DESC"
    )
    return render_template("loans/return.html", returned_today=returned_today)


@bp.route("/")
def list_loans():
    state = request.args.get("state", "active")
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    where = LOAN_FILTERS.get(state, LOAN_FILTERS["active"])
    loans = query(
        f"""
        SELECT * FROM v_loan_detail
         WHERE {where}
           AND (%s = '' OR member_name LIKE %s OR member_no = %s OR title LIKE %s OR reg_no = %s)
         ORDER BY (return_date IS NULL) DESC, due_date, loan_id DESC
         LIMIT 300
        """,
        (q, like, q, like, q.upper()),
    )
    return render_template("loans/list.html", loans=loans, state=state, q=q)


@bp.route("/<int:loan_id>/renew", methods=["POST"])
def renew(loan_id):
    try:
        row = call_proc("sp_renew", loan_id, "사서", session["staff_id"], None)
        flash(f"'{row['title']}' 연장 완료 · 새 반납예정일 {row['due_date']:%Y-%m-%d} "
              f"(연장 {row['renew_count']}회째)", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(request.referrer or url_for("loans.list_loans"))


@bp.route("/<int:loan_id>/lost", methods=["POST"])
def report_lost(loan_id):
    try:
        row = call_proc("sp_report_lost", loan_id, session["staff_id"])
        penalty = penalty_message(row)
        compensation = (f"변상금 기준액 {row['compensation']:,}원" if row["compensation"] else "정가 정보 없음")
        flash(f"'{row['title']}' 분실 처리 완료 · {row['member_name']} · 동일 도서로 변상 원칙 "
              f"(불가 시 {compensation})" + (f" · {penalty}" if penalty else ""), "warning")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(request.referrer or url_for("loans.list_loans"))

"""연체 관리 : 연체자 조회, 대출정지 적용·해제, 연체료 납부·면제."""
import pymysql
from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from .auth import admin_required
from .db import call_proc, error_message, query, query_one

bp = Blueprint("overdue", __name__, url_prefix="/overdue")

SUSPENSION_REASONS = ("장기연체", "자료훼손", "규정위반", "기타")


@bp.route("/")
def index():
    overdue_loans = query("SELECT * FROM v_loan_detail WHERE loan_state = '연체' ORDER BY overdue_days DESC")
    suspended = query(
        """SELECT s.*, m.member_no, m.name, m.phone, st.name AS staff_name
             FROM suspension s
             JOIN member m ON m.member_id = s.member_id
             JOIN staff st ON st.staff_id = s.staff_id
            WHERE s.released_date IS NULL AND CURDATE() BETWEEN s.start_date AND s.end_date
            ORDER BY s.end_date DESC"""
    )
    # 미반납 연체 도서를 지금 반납하면 부과될 예상 연체료
    pending = query_one(
        """SELECT COUNT(*) AS cnt, COALESCE(SUM(v.overdue_days * t.fine_per_day), 0) AS amount
             FROM v_loan_detail v
             JOIN member m      ON m.member_id = v.member_id
             JOIN member_type t ON t.type_code = m.type_code
            WHERE v.loan_state = '연체'"""
    )
    return render_template("overdue/index.html", overdue_loans=overdue_loans, suspended=suspended,
                           pending=pending, reasons=SUSPENSION_REASONS)


@bp.route("/suspend", methods=["POST"])
def suspend():
    member_no = request.form.get("member_no", "").strip()
    member = query_one("SELECT member_id FROM member WHERE member_no = %s", (member_no,))
    if not member:
        flash("존재하지 않는 학번(교번)입니다.", "error")
        return redirect(request.referrer or url_for("overdue.index"))
    try:
        row = call_proc("sp_suspend_member", member["member_id"], request.form.get("reason", "기타"),
                        int(request.form.get("days", "0") or 0), request.form.get("memo", "").strip() or None,
                        session["staff_id"])
        flash(f"대출정지 적용 · {row['end_date']:%Y-%m-%d}까지", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    except ValueError:
        flash("정지 일수는 숫자로 입력하세요.", "error")
    return redirect(request.referrer or url_for("overdue.index"))


@bp.route("/suspensions/<int:suspension_id>/release", methods=["POST"])
def release(suspension_id):
    try:
        call_proc("sp_release_suspension", suspension_id, session["staff_id"])
        flash("대출정지를 해제했습니다.", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(request.referrer or url_for("overdue.index"))


@bp.route("/fines")
def fines():
    status = request.args.get("status", "미납")
    q = request.args.get("q", "").strip()
    like = f"%{q}%"
    rows = query(
        """
        SELECT f.*, l.member_id, m.member_no, m.name AS member_name, m.phone, b.title, bc.reg_no,
               l.due_date, l.return_date, l.return_type, s.name AS staff_name
          FROM fine f
          JOIN loan l       ON l.loan_id = f.loan_id
          JOIN member m     ON m.member_id = l.member_id
          JOIN book_copy bc ON bc.copy_id = l.copy_id
          JOIN book b       ON b.isbn = bc.isbn
          LEFT JOIN staff s ON s.staff_id = f.staff_id
         WHERE (%s = '' OR f.status = %s)
           AND (%s = '' OR m.name LIKE %s OR m.member_no = %s)
         ORDER BY f.imposed_date DESC, f.fine_id DESC
        """,
        (status, status, q, like, q),
    )
    total = sum(f["amount"] for f in rows)
    return render_template("overdue/fines.html", fines=rows, total=total, status=status, q=q)


@bp.route("/fines/<int:fine_id>/pay", methods=["POST"])
def pay(fine_id):
    try:
        call_proc("sp_settle_fine", fine_id, "납부", session["staff_id"])
        flash("연체료 납부를 처리했습니다.", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(request.referrer or url_for("overdue.fines"))


@bp.route("/fines/<int:fine_id>/waive", methods=["POST"])
@admin_required
def waive(fine_id):
    try:
        call_proc("sp_settle_fine", fine_id, "면제", session["staff_id"])
        flash("연체료를 면제 처리했습니다.", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(request.referrer or url_for("overdue.fines"))

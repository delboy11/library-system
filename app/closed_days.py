"""휴관일 관리 (관리자) : 휴관일 등록·삭제. 등록 시 그날이 반납예정일인 대출을 다음 개관일로 옮긴다."""
import calendar
from datetime import date

import pymysql
from flask import Blueprint, flash, redirect, render_template, request, url_for

from .auth import admin_required
from .db import call_proc, error_message, execute_rowcount, query

bp = Blueprint("closed_days", __name__, url_prefix="/closed-days")


@bp.route("/")
def index():
    year = request.args.get("year", type=int) or date.today().year
    if not 1900 <= year <= 2200:
        year = date.today().year
    rows = query(
        """SELECT c.closed_date, c.reason,
                  (SELECT COUNT(*) FROM loan l WHERE l.return_date IS NULL
                      AND l.due_date = c.closed_date + INTERVAL 1 DAY) AS next_day_due
             FROM closed_day c
            WHERE YEAR(c.closed_date) = %s
            ORDER BY c.closed_date""",
        (year,),
    )
    closed = {r["closed_date"]: r["reason"] for r in rows}
    weeks = calendar.Calendar(firstweekday=6)          # 일요일부터
    months = [{"month": m,
               "weeks": weeks.monthdatescalendar(year, m),
               "extra": [r for r in rows if r["closed_date"].month == m and r["reason"] != "일요일"]}
              for m in range(1, 13)]
    return render_template("closed_days/index.html", months=months, closed=closed, year=year)


@bp.route("/new", methods=["POST"])
@admin_required
def new():
    try:
        row = call_proc("sp_add_closed_day", request.form.get("closed_date"),
                        request.form.get("reason", "").strip() or "임시휴관")
        flash(f"휴관일을 등록했습니다. 반납예정일이 조정된 대출 {row['moved_loans']}건", "success")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    year = (request.form.get("closed_date") or "")[:4]
    return redirect(url_for("closed_days.index", year=year if year.isdigit() else None))


@bp.route("/<closed_date>/delete", methods=["POST"])
@admin_required
def delete(closed_date):
    deleted = execute_rowcount("DELETE FROM closed_day WHERE closed_date = %s AND closed_date >= CURDATE()",
                               (closed_date,))
    if deleted:
        flash("휴관일을 삭제했습니다. (이미 조정된 반납예정일은 그대로 유지됩니다)", "success")
    else:
        flash("오늘 이전의 휴관일이나 등록되지 않은 날짜는 삭제할 수 없습니다.", "error")
    return redirect(url_for("closed_days.index", year=closed_date[:4] if closed_date[:4].isdigit() else None))

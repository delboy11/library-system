"""대시보드."""
import calendar
from datetime import date, timedelta

from flask import Blueprint, render_template

from .db import query, query_one

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    summary = query_one(
        """
        SELECT (SELECT COUNT(*) FROM book) AS titles,
               (SELECT COUNT(*) FROM book_copy WHERE status IN ('대출가능', '대출중')) AS copies,
               (SELECT COUNT(*) FROM member WHERE status = '정상') AS members,
               (SELECT COUNT(*) FROM loan WHERE return_date IS NULL) AS active_loans,
               (SELECT COUNT(*) FROM loan WHERE return_date IS NULL AND due_date < CURDATE()) AS overdue_loans,
               (SELECT COUNT(DISTINCT member_id) FROM suspension
                 WHERE released_date IS NULL AND CURDATE() BETWEEN start_date AND end_date) AS suspended,
               (SELECT COALESCE(SUM(amount), 0) FROM fine WHERE status = '미납') AS unpaid_total,
               (SELECT COUNT(*) FROM loan WHERE DATE(loan_date) = CURDATE()) AS loans_today,
               (SELECT COUNT(*) FROM loan WHERE DATE(return_date) = CURDATE()) AS returns_today
        """
    )
    due_soon = query(
        """
        SELECT * FROM v_loan_detail
         WHERE return_date IS NULL AND due_date BETWEEN CURDATE() AND CURDATE() + INTERVAL 2 DAY
         ORDER BY due_date, member_name
        """
    )
    overdue = query(
        "SELECT * FROM v_loan_detail WHERE loan_state = '연체' ORDER BY overdue_days DESC, due_date LIMIT 10"
    )
    today = date.today()
    first = today.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)          # 다음 달 1일
    rows = query(
        "SELECT closed_date, reason FROM closed_day WHERE closed_date >= %s AND closed_date < %s ORDER BY closed_date",
        (first, (nxt + timedelta(days=32)).replace(day=1)),
    )
    weeks = calendar.Calendar(firstweekday=6)                   # 일요일부터
    months = [{"month": d.month,
               "weeks": weeks.monthdatescalendar(d.year, d.month),
               "extra": [r for r in rows if r["closed_date"].month == d.month and r["reason"] != "일요일"]}
              for d in (first, nxt)]
    return render_template("index.html", summary=summary, due_soon=due_soon, overdue=overdue,
                           months=months, closed={r["closed_date"]: r["reason"] for r in rows})

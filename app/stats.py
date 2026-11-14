"""통계 (월별 대출, 인기 도서, 분류별 대출, 다독 회원)."""
from datetime import date

from flask import Blueprint, render_template

from .db import query, query_one

bp = Blueprint("stats", __name__, url_prefix="/stats")


def recent_months(n):
    today = date.today()
    months = []
    y, m = today.year, today.month
    for _ in range(n):
        months.append(f"{y:04d}-{m:02d}")
        y, m = (y, m - 1) if m > 1 else (y - 1, 12)
    return list(reversed(months))


@bp.route("/")
def index():
    rows = query(
        """
        SELECT DATE_FORMAT(loan_date, '%Y-%m') AS ym, COUNT(*) AS cnt
          FROM loan
         WHERE loan_date >= DATE_FORMAT(CURDATE() - INTERVAL 5 MONTH, '%Y-%m-01')
         GROUP BY ym
        """
    )
    counts = {r["ym"]: r["cnt"] for r in rows}
    monthly = [{"ym": ym, "cnt": counts.get(ym, 0)} for ym in recent_months(6)]

    # 윈도우 함수 RANK() 로 인기 순위 산출
    top_books = query(
        """
        SELECT RANK() OVER (ORDER BY COUNT(*) DESC) AS rnk,
               b.isbn, b.title, COUNT(*) AS cnt
          FROM loan l
          JOIN book_copy bc ON bc.copy_id = l.copy_id
          JOIN book b       ON b.isbn = bc.isbn
         GROUP BY b.isbn, b.title
         ORDER BY rnk, b.title
         LIMIT 10
        """
    )
    by_category = query(
        """
        SELECT c.category_code, c.category_name, COUNT(l.loan_id) AS cnt
          FROM category c
          LEFT JOIN book b       ON b.category_code = c.category_code
          LEFT JOIN book_copy bc ON bc.isbn = b.isbn
          LEFT JOIN loan l       ON l.copy_id = bc.copy_id
         GROUP BY c.category_code, c.category_name
         ORDER BY cnt DESC, c.category_code
        """
    )
    top_members = query(
        """
        SELECT RANK() OVER (ORDER BY COUNT(*) DESC) AS rnk,
               m.member_id, m.member_no, m.name, g.type_name, COUNT(*) AS cnt
          FROM loan l
          JOIN member m       ON m.member_id = l.member_id
          JOIN member_type g ON g.type_code = m.type_code
         GROUP BY m.member_id, m.member_no, m.name, g.type_name
         ORDER BY rnk, m.member_id
         LIMIT 5
        """
    )
    overdue = query_one(
        """
        SELECT COUNT(*) AS returned,
               SUM(EXISTS (SELECT 1 FROM fine f WHERE f.loan_id = l.loan_id)) AS late
          FROM loan l WHERE l.return_date IS NOT NULL
        """
    )
    late_rate = (overdue["late"] or 0) / overdue["returned"] * 100 if overdue["returned"] else 0
    return render_template(
        "stats/index.html",
        monthly=monthly,
        monthly_max=max([m["cnt"] for m in monthly] + [1]),
        top_books=top_books,
        top_books_max=max([b["cnt"] for b in top_books] + [1]),
        by_category=by_category,
        category_max=max([c["cnt"] for c in by_category] + [1]),
        top_members=top_members,
        overdue=overdue,
        late_rate=late_rate,
    )

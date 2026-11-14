"""회원 관리 : 회원 등록, 정보 수정, 탈퇴 처리, 회원 조회."""
import pymysql
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from .db import error_message, execute, execute_rowcount, query, query_one

bp = Blueprint("members", __name__, url_prefix="/members")

LOAN_STATES = ("대출가능", "대출정지", "탈퇴")


def member_types():
    return query("SELECT * FROM member_type ORDER BY max_loan_count, type_code")


def member_form_values(form):
    return {
        "member_no": form.get("member_no", "").strip(),
        "name": form.get("name", "").strip(),
        "type_code": form.get("type_code", ""),
        "department": form.get("department", "").strip() or None,
        "phone": form.get("phone", "").strip(),
        "email": form.get("email", "").strip() or None,
    }


@bp.route("/")
def list_members():
    q = request.args.get("q", "").strip()
    state = request.args.get("state", "")
    like = f"%{q}%"
    members = query(
        """
        SELECT * FROM v_member_status
         WHERE (%s = '' OR name LIKE %s OR member_no LIKE %s OR phone LIKE %s OR department LIKE %s)
           AND (%s = '' OR loan_state = %s)
         ORDER BY member_id
        """,
        (q, like, like, like, like, state, state),
    )
    return render_template("members/list.html", members=members, q=q, state=state, states=LOAN_STATES)


@bp.route("/<int:member_id>")
def detail(member_id):
    member = query_one("SELECT * FROM v_member_status WHERE member_id = %s", (member_id,))
    if not member:
        abort(404)
    active_loans = query(
        "SELECT * FROM v_loan_detail WHERE member_id = %s AND return_date IS NULL ORDER BY due_date",
        (member_id,),
    )
    history = query(
        """SELECT * FROM v_loan_detail WHERE member_id = %s AND return_date IS NOT NULL
            ORDER BY return_date DESC LIMIT 20""",
        (member_id,),
    )
    fines = query(
        """
        SELECT f.*, b.title, l.due_date, l.return_date
          FROM fine f
          JOIN loan l       ON l.loan_id = f.loan_id
          JOIN book_copy bc ON bc.copy_id = l.copy_id
          JOIN book b       ON b.isbn = bc.isbn
         WHERE l.member_id = %s
         ORDER BY f.imposed_date DESC
        """,
        (member_id,),
    )
    suspensions = query(
        """SELECT s.*, st.name AS staff_name, rs.name AS released_staff_name
             FROM suspension s
             LEFT JOIN staff st ON st.staff_id = s.staff_id
             LEFT JOIN staff rs ON rs.staff_id = s.released_staff_id
            WHERE s.member_id = %s ORDER BY s.start_date DESC""",
        (member_id,),
    )
    return render_template("members/detail.html", member=member, active_loans=active_loans,
                           history=history, fines=fines, suspensions=suspensions)


@bp.route("/new", methods=["GET", "POST"])
def new():
    values = {"type_code": "UG"}
    if request.method == "POST":
        values = member_form_values(request.form)
        password = request.form.get("password", "")
        if not values["member_no"] or not values["name"] or not values["phone"]:
            flash("학번(교번), 이름, 전화번호는 필수입니다.", "error")
        elif len(password) < 8:
            flash("초기 비밀번호는 8자 이상이어야 합니다.", "error")
        else:
            try:
                member_id = execute(
                    """INSERT INTO member (member_no, password_hash, name, type_code, department, phone, email)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (values["member_no"], generate_password_hash(password), values["name"], values["type_code"],
                     values["department"], values["phone"], values["email"]),
                )
                flash(f"{values['name']} 회원을 등록했습니다. (회원번호 {member_id})", "success")
                return redirect(url_for("members.detail", member_id=member_id))
            except pymysql.MySQLError as e:
                flash(error_message(e), "error")
    return render_template("members/form.html", values=values, types=member_types(), is_new=True)


@bp.route("/<int:member_id>/edit", methods=["GET", "POST"])
def edit(member_id):
    member = query_one("SELECT * FROM member WHERE member_id = %s", (member_id,))
    if not member:
        abort(404)
    if member["status"] == "탈퇴":
        flash("탈퇴한 회원의 정보는 수정할 수 없습니다.", "error")
        return redirect(url_for("members.detail", member_id=member_id))
    values = member
    if request.method == "POST":
        values = member_form_values(request.form)
        values["member_id"] = member_id
        if not values["member_no"] or not values["name"] or not values["phone"]:
            flash("학번(교번), 이름, 전화번호는 필수입니다.", "error")
        else:
            try:
                execute(
                    """UPDATE member SET member_no = %s, name = %s, type_code = %s, department = %s,
                                         phone = %s, email = %s
                        WHERE member_id = %s""",
                    (values["member_no"], values["name"], values["type_code"], values["department"],
                     values["phone"], values["email"], member_id),
                )
                password = request.form.get("password", "")
                if password:
                    if len(password) < 8:
                        flash("비밀번호는 8자 이상이어야 해서 변경하지 않았습니다.", "warning")
                    else:
                        execute("UPDATE member SET password_hash = %s WHERE member_id = %s",
                                (generate_password_hash(password), member_id))
                flash("회원 정보를 수정했습니다.", "success")
                return redirect(url_for("members.detail", member_id=member_id))
            except pymysql.MySQLError as e:
                flash(error_message(e), "error")
    return render_template("members/form.html", values=values, types=member_types(), is_new=False)


@bp.route("/<int:member_id>/withdraw", methods=["POST"])
def withdraw(member_id):
    try:
        # 미반납 도서·미납 연체료 검사와 탈퇴일 기록은 트리거(trg_member_withdraw_check)가 담당
        changed = execute_rowcount("UPDATE member SET status = '탈퇴' WHERE member_id = %s AND status = '정상'",
                                   (member_id,))
        if changed:
            flash("탈퇴 처리했습니다.", "success")
        else:
            flash("이미 탈퇴한 회원입니다.", "warning")
    except pymysql.MySQLError as e:
        flash(error_message(e), "error")
    return redirect(url_for("members.detail", member_id=member_id))

"""업무 규칙 통합 테스트 : 실제 MySQL DB 를 초기화한 뒤 화면(Flask)과 프로시저를 통해 검증한다.

실행 : .venv/bin/python -m unittest -v tests.test_scenarios
※ library_db 를 초기화하므로 시연 데이터가 처음 상태로 돌아간다.
"""
import re
import subprocess
import unittest
from html import unescape
from pathlib import Path

import pymysql

from app import create_app

ROOT = Path(__file__).resolve().parent.parent


def flashes(resp):
    return [unescape(m.strip()) for _, m in re.findall(r'<div class="flash (\w+)"[^>]*>(.*?)</div>', resp.data.decode(), re.S)]


class LibraryScenarioTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([str(ROOT / "scripts" / "init_db.sh")], check=True, capture_output=True)
        cls.app = create_app()
        cfg = cls.app.config                                   # DB_HOST 를 주면 다른 PC 의 DB 서버로 테스트
        cls.db = pymysql.connect(host=cfg["DB_HOST"], port=cfg["DB_PORT"], user="library", password="library1234",
                                 database="library_db", charset="utf8mb4",
                                 cursorclass=pymysql.cursors.DictCursor, autocommit=True)

    @classmethod
    def tearDownClass(cls):
        cls.db.close()
        subprocess.run([str(ROOT / "scripts" / "init_db.sh")], check=True, capture_output=True)

    # ---- 헬퍼 ------------------------------------------------------------------------
    def sql(self, query, args=None):
        with self.db.cursor() as cur:
            cur.execute(query, args)
            return cur.fetchall()

    def one(self, query, args=None):
        rows = self.sql(query, args)
        return rows[0] if rows else None

    def staff(self, login_id="lib01", password="lib1234"):
        c = self.app.test_client()
        c.post("/login", data={"login_id": login_id, "password": password})
        return c

    def member(self, member_no, password="member1234"):
        c = self.app.test_client()
        c.post("/my/login", data={"member_no": member_no, "password": password})
        return c

    def post(self, client, url, data=None):
        return flashes(client.post(url, data=data or {}, follow_redirects=True))

    def available_reg_no(self, exclude=()):
        row = self.one("SELECT reg_no FROM book_copy WHERE status = '대출가능' AND reg_no NOT IN %s "
                       "ORDER BY copy_id LIMIT 1", (tuple(exclude) or ("",),))
        return row["reg_no"]

    def active_loan(self, member_no):
        return self.one("SELECT * FROM v_loan_detail WHERE member_no = %s AND return_date IS NULL "
                        "ORDER BY loan_id DESC LIMIT 1", (member_no,))

    # ---- 1. 대출 가능 여부 검사 ----------------------------------------------------------
    def test_01_borrow_blocked_for_overdue_member(self):
        msg = self.post(self.staff(), "/loans/borrow", {"member_no": "20241102", "reg_no": self.available_reg_no()})
        self.assertIn("연체 중인 도서가 있어 대출할 수 없습니다", msg[0])

    def test_02_borrow_blocked_for_unpaid_fine(self):
        msg = self.post(self.staff(), "/loans/borrow", {"member_no": "20214410", "reg_no": self.available_reg_no()})
        self.assertIn("미납 연체료", msg[0])

    def test_03_borrow_blocked_for_suspended_and_withdrawn(self):
        c = self.staff()
        msg = self.post(c, "/loans/borrow", {"member_no": "20193321", "reg_no": self.available_reg_no()})
        self.assertRegex(msg[0], r"대출정지 기간입니다\. \(\d{4}-\d{2}-\d{2}까지\)")
        msg = self.post(c, "/loans/borrow", {"member_no": "20193579", "reg_no": self.available_reg_no()})
        self.assertIn("탈퇴한 회원", msg[0])

    def test_04_borrow_success_sets_due_date_on_open_day(self):
        reg_no = self.available_reg_no()
        msg = self.post(self.staff(), "/loans/borrow", {"member_no": "20257001", "reg_no": reg_no.lower()})
        self.assertIn("대출 완료", msg[0])
        loan = self.active_loan("20257001")
        expected = self.one("SELECT fn_next_open_day(CURDATE() + INTERVAL 30 DAY) AS d")["d"]   # 대학원생 30일
        self.assertEqual(loan["due_date"], expected)
        self.assertIsNone(self.one("SELECT 1 FROM closed_day WHERE closed_date = %s", (loan["due_date"],)))
        self.assertEqual(self.one("SELECT status FROM book_copy WHERE reg_no = %s", (reg_no,))["status"], "대출중")

    def test_05_borrow_limit(self):
        c = self.staff()
        used = []
        current = self.one("SELECT active_loans FROM v_member_status WHERE member_no = '20231234'")["active_loans"]
        for _ in range(10 - current):                              # 학부생 한도 10권까지 채움
            reg_no = self.available_reg_no(used)
            used.append(reg_no)
            self.assertIn("대출 완료", self.post(c, "/loans/borrow", {"member_no": "20231234", "reg_no": reg_no})[0])
        msg = self.post(c, "/loans/borrow", {"member_no": "20231234", "reg_no": self.available_reg_no(used)})
        self.assertIn("대출 한도(10권)를 초과합니다", msg[0])
        for reg_no in used:                                        # 원상 복구
            self.post(c, "/loans/return", {"reg_no": reg_no})

    def test_06_borrow_blocked_for_unavailable_copies(self):
        c = self.staff()
        on_loan = self.one("SELECT reg_no FROM book_copy WHERE status = '대출중' LIMIT 1")["reg_no"]
        lost = self.one("SELECT reg_no FROM book_copy WHERE status = '분실' LIMIT 1")["reg_no"]
        for reg_no, state in ((on_loan, "대출중"), (lost, "분실")):
            msg = self.post(c, "/loans/borrow", {"member_no": "20221999", "reg_no": reg_no})
            self.assertIn(f"현재 상태: {state}", msg[0])
        msg = self.post(c, "/loans/borrow", {"member_no": "20221999", "reg_no": "EM999999"})
        self.assertIn("존재하지 않는 등록번호", msg[0])

    # ---- 2. 연장 --------------------------------------------------------------------
    def test_10_renew_from_member_portal(self):
        loan = self.one("SELECT * FROM v_loan_detail WHERE member_no = '20231234' AND return_date IS NULL "
                        "AND renew_count = 0 ORDER BY loan_id LIMIT 1")
        msg = self.post(self.member("20231234"), f"/my/loans/{loan['loan_id']}/renew")
        self.assertIn("연장 완료", msg[0])
        expected = self.one("SELECT fn_next_open_day(CURDATE() + INTERVAL 14 DAY) AS d")["d"]   # 연장한 날 + 14일
        self.assertEqual(self.one("SELECT due_date FROM loan WHERE loan_id = %s", (loan["loan_id"],))["due_date"], expected)
        r = self.one("SELECT * FROM renewal WHERE loan_id = %s ORDER BY renewal_id DESC LIMIT 1", (loan["loan_id"],))
        self.assertEqual((r["channel"], r["prev_due_date"], r["staff_id"]), ("홈페이지", loan["due_date"], None))

    def test_11_renew_rules(self):
        c = self.staff()
        same_day = self.active_loan("20221057")                       # 오늘 대출
        self.assertIn("대출 당일에는 연장할 수 없습니다", self.post(c, f"/loans/{same_day['loan_id']}/renew")[0])
        used_up = self.active_loan("20232245")                        # 연장 2회 사용
        self.assertIn("연장 가능 횟수(2회)", self.post(c, f"/loans/{used_up['loan_id']}/renew")[0])
        overdue = self.active_loan("20211388")
        self.assertIn("연체 중인 도서가 있어 연장할 수 없습니다", self.post(c, f"/loans/{overdue['loan_id']}/renew")[0])
        professor = self.one("SELECT * FROM v_loan_detail WHERE member_no = 'F2008011' AND renew_count = 1 "
                             "AND return_date IS NULL")
        self.assertIn("연장 가능 횟수(1회)", self.post(c, f"/loans/{professor['loan_id']}/renew")[0])

    def test_12_member_cannot_renew_others_loan(self):
        others = self.active_loan("20257001")
        msg = self.post(self.member("20231234"), f"/my/loans/{others['loan_id']}/renew")
        self.assertIn("연장할 수 있는 대출이 아닙니다", msg[0])

    # ---- 3. 반납 · 연체료 ----------------------------------------------------------------
    def test_20_overdue_return_creates_fine_then_pay_unblocks(self):
        c = self.staff()
        loan = self.active_loan("20241102")
        expected_days = self.one("SELECT fn_overdue_days(%s, CURDATE()) AS d", (loan["due_date"],))["d"]
        msg = self.post(c, "/loans/return", {"reg_no": loan["reg_no"]})
        self.assertIn(f"연체 {expected_days}일", msg[0])
        self.assertIn(f"연체료 {expected_days * 100:,}원 부과", msg[0])
        fine = self.one("SELECT * FROM fine WHERE loan_id = %s", (loan["loan_id"],))
        self.assertEqual((fine["overdue_days"], fine["amount"], fine["status"]), (expected_days, expected_days * 100, "미납"))
        self.assertEqual(self.one("SELECT status FROM book_copy WHERE copy_id = %s", (loan["copy_id"],))["status"], "대출가능")
        # 미납 상태에서는 대출 불가 → 납부 후 대출 가능
        reg_no = self.available_reg_no()
        self.assertIn("미납 연체료", self.post(c, "/loans/borrow", {"member_no": "20241102", "reg_no": reg_no})[0])
        self.assertIn("납부를 처리했습니다", self.post(c, f"/overdue/fines/{fine['fine_id']}/pay")[0])
        self.assertIn("대출 완료", self.post(c, "/loans/borrow", {"member_no": "20241102", "reg_no": reg_no})[0])

    def test_21_overdue_days_exclude_closed_days(self):
        sunday = self.one("SELECT MIN(closed_date) AS d FROM closed_day WHERE reason = '일요일' "
                          "AND closed_date > CURDATE() + INTERVAL 30 DAY "
                          "AND closed_date - INTERVAL 1 DAY NOT IN (SELECT closed_date FROM closed_day) "
                          "AND closed_date + INTERVAL 1 DAY NOT IN (SELECT closed_date FROM closed_day)")["d"]
        r = self.one("SELECT fn_next_open_day(%s) AS next_day, fn_overdue_days(%s - INTERVAL 1 DAY, %s + INTERVAL 1 DAY) AS days",
                     (sunday, sunday, sunday))
        self.assertEqual(str(r["next_day"]), str(self.one("SELECT %s + INTERVAL 1 DAY AS d", (sunday,))["d"]))
        self.assertEqual(r["days"], 1)          # 토요일 반납예정 → 월요일 반납 : 일요일 제외 1일

    def test_23_new_closed_day_moves_due_dates(self):
        loan = self.one("SELECT loan_id, due_date FROM loan WHERE return_date IS NULL AND due_date > CURDATE() "
                        "ORDER BY due_date LIMIT 1")
        day = loan["due_date"]
        self.assertIn("관리자만", self.post(self.staff(), "/closed-days/new", {"closed_date": str(day), "reason": "임시휴관"})[0])
        msg = self.post(self.staff("admin", "admin1234"), "/closed-days/new", {"closed_date": str(day), "reason": "임시휴관"})
        self.assertIn("휴관일을 등록했습니다", msg[0])
        moved = self.one("SELECT due_date FROM loan WHERE loan_id = %s", (loan["loan_id"],))["due_date"]
        self.assertGreater(moved, day)
        self.assertIsNone(self.one("SELECT 1 FROM closed_day WHERE closed_date = %s", (moved,)))
        msg = self.post(self.staff("admin", "admin1234"), "/closed-days/new", {"closed_date": "2020-01-01", "reason": "x"})
        self.assertIn("지난 날짜", msg[0])

    def test_22_waive_requires_admin(self):
        loan = self.active_loan("20233678")                       # 장기 연체 도서를 반납해 연체료를 새로 만든다
        self.post(self.staff(), "/loans/return", {"reg_no": loan["reg_no"]})
        fine = self.one("SELECT fine_id FROM fine WHERE loan_id = %s", (loan["loan_id"],))
        self.assertIn("관리자만", self.post(self.staff(), f"/overdue/fines/{fine['fine_id']}/waive")[0])
        self.assertIn("면제 처리", self.post(self.staff("admin", "admin1234"), f"/overdue/fines/{fine['fine_id']}/waive")[0])
        self.assertIn("이미 처리된", self.post(self.staff(), f"/overdue/fines/{fine['fine_id']}/pay")[0])

    # ---- 4. 분실 · 폐기 ----------------------------------------------------------------
    def test_30_report_lost(self):
        loan = self.active_loan("20211388")                     # 연체 중인 대출을 분실 처리
        msg = self.post(self.staff(), f"/loans/{loan['loan_id']}/lost")
        self.assertIn("분실 처리 완료", msg[0])
        self.assertIn("변상금 기준액", msg[0])
        row = self.one("SELECT l.return_type, bc.status, bc.removed_date FROM loan l JOIN book_copy bc "
                       "ON bc.copy_id = l.copy_id WHERE l.loan_id = %s", (loan["loan_id"],))
        self.assertEqual((row["return_type"], row["status"]), ("분실", "분실"))
        self.assertIsNotNone(row["removed_date"])
        self.assertIsNotNone(self.one("SELECT 1 FROM fine WHERE loan_id = %s", (loan["loan_id"],)))

    def test_31_discard_guard(self):
        c = self.staff()
        on_loan = self.one("SELECT copy_id FROM book_copy WHERE status = '대출중' LIMIT 1")["copy_id"]
        self.assertIn("반납(또는 분실 처리) 후", self.post(c, f"/books/copies/{on_loan}/status", {"status": "폐기"})[0])
        free = self.one("SELECT copy_id FROM book_copy WHERE status = '대출가능' ORDER BY copy_id DESC LIMIT 1")["copy_id"]
        self.post(c, f"/books/copies/{free}/status", {"status": "폐기"})
        self.assertIsNotNone(self.one("SELECT removed_date FROM book_copy WHERE copy_id = %s", (free,))["removed_date"])
        self.post(c, f"/books/copies/{free}/status", {"status": "대출가능"})
        self.assertIsNone(self.one("SELECT removed_date FROM book_copy WHERE copy_id = %s", (free,))["removed_date"])

    def test_32_book_with_history_cannot_be_deleted(self):
        isbn = self.one("SELECT bc.isbn FROM loan l JOIN book_copy bc ON bc.copy_id = l.copy_id LIMIT 1")["isbn"]
        self.assertIn("대출 이력이 있는 도서는 삭제할 수 없습니다", self.post(self.staff(), f"/books/{isbn}/delete")[0])

    # ---- 5. 회원 관리 ------------------------------------------------------------------
    def test_40_member_register_validation(self):
        c = self.staff()
        base = {"member_no": "20269999", "name": "홍길동", "type_code": "UG", "phone": "010-9999-0000", "password": "password1"}
        self.assertIn("전화번호 형식", self.post(c, "/members/new", {**base, "phone": "01099990000"})[0])
        self.assertIn("이미 등록된 학번", self.post(c, "/members/new", {**base, "member_no": "20231234"})[0])
        self.assertIn("8자 이상", self.post(c, "/members/new", {**base, "password": "short"})[0])
        self.assertIn("회원을 등록했습니다", self.post(c, "/members/new", base)[0])
        # 새 회원은 회원 포털에 로그인할 수 있다
        r = self.app.test_client().post("/my/login", data={"member_no": "20269999", "password": "password1"})
        self.assertEqual(r.headers.get("Location"), "/my/")

    def test_41_withdraw_rules(self):
        c = self.staff()
        self.assertIn("반납하지 않은 도서", self.post(c, "/members/10022/withdraw")[0])   # 대출 중
        self.assertIn("미납 연체료", self.post(c, "/members/10009/withdraw")[0])         # 미납
        self.assertIn("탈퇴 처리했습니다", self.post(c, "/members/10019/withdraw")[0])
        m = self.one("SELECT status, withdraw_date FROM member WHERE member_id = 10019")
        self.assertEqual(m["status"], "탈퇴")
        self.assertIsNotNone(m["withdraw_date"])                                       # 트리거가 탈퇴일 기록
        r = self.app.test_client().post("/my/login", data={"member_no": "20224680", "password": "member1234"},
                                        follow_redirects=True)
        self.assertIn("탈퇴한 회원", flashes(r)[0])

    def test_42_member_state_matches_borrow_rules(self):
        # 미납 연체료만 있는 회원도 '대출정지' — sp_borrow 가 거부하는 조건(정지·연체·미납)과 같다
        m = self.one("SELECT unpaid_fine, overdue_loans, suspend_until, loan_state FROM v_member_status "
                     "WHERE member_no = '20214410'")
        self.assertEqual((m["overdue_loans"], m["suspend_until"], m["loan_state"]), (0, None, "대출정지"))
        self.assertGreater(m["unpaid_fine"], 0)
        self.assertIn("20214410", self.staff().get("/members/?state=대출정지").data.decode())
        self.assertNotIn("20214410", self.staff().get("/members/?state=대출가능").data.decode())

    # ---- 6. 대출정지 적용·해제 -------------------------------------------------------------
    def test_50_suspend_and_release(self):
        c = self.staff()
        msg = self.post(c, "/overdue/suspend", {"member_no": "20243150", "reason": "규정위반", "days": "7", "memo": "테스트"})
        self.assertIn("대출정지 적용", msg[0])
        self.assertIn("대출정지 기간", self.post(c, "/loans/borrow", {"member_no": "20243150", "reg_no": self.available_reg_no()})[0])
        s = self.one("SELECT suspension_id, end_date, DATEDIFF(end_date, start_date) AS span FROM suspension "
                     "WHERE member_id = 10014 ORDER BY suspension_id DESC LIMIT 1")
        self.assertEqual(s["span"], 6)                                                   # 오늘 포함 7일
        self.assertIn("해제했습니다", self.post(c, f"/overdue/suspensions/{s['suspension_id']}/release")[0])
        self.assertIn("이미 해제된", self.post(c, f"/overdue/suspensions/{s['suspension_id']}/release")[0])
        self.assertIn("대출 완료", self.post(c, "/loans/borrow", {"member_no": "20243150", "reg_no": self.available_reg_no()})[0])

    # ---- 7. 무결성 제약 -----------------------------------------------------------------
    def test_60_db_constraints(self):
        active = self.one("SELECT copy_id FROM loan WHERE return_date IS NULL LIMIT 1")["copy_id"]
        with self.assertRaises(pymysql.err.IntegrityError) as e:          # 같은 복본 이중 대출
            self.sql("INSERT INTO loan (copy_id, member_id, staff_id, due_date) VALUES (%s, 10013, 2, CURDATE())", (active,))
        self.assertIn("uq_loan_active_copy", str(e.exception))
        with self.assertRaises(pymysql.err.OperationalError) as e:        # CHECK: ISBN 형식
            self.sql("INSERT INTO book (isbn, title, publisher_id, category_code) VALUES ('1234567890123', 'x', 1, '000')")
        self.assertIn("ck_book_isbn", str(e.exception))
        with self.assertRaises(pymysql.err.OperationalError) as e:        # CHECK: 반납구분과 반납일시 짝
            self.sql("UPDATE loan SET return_type = '반납' WHERE return_date IS NULL LIMIT 1")
        self.assertIn("ck_loan_returned", str(e.exception))
        with self.assertRaises(pymysql.err.OperationalError) as e:        # CHECK: 회원 상태값 도메인
            self.sql("UPDATE member SET status = '정지' WHERE member_id = 10013")
        self.assertIn("ck_member_status", str(e.exception))

    def test_61_app_account_has_no_ddl_privilege(self):
        with self.assertRaises(pymysql.err.OperationalError):
            self.sql("DROP TABLE closed_day")

    def test_33_book_form_keeps_author_roles_and_rejects_bad_input(self):
        c = self.staff()
        base = {"isbn": "9791100099990", "title": "테스트 도서", "writers": "홍길동, 김철수 (엮은이)",
                "translators": "", "publisher_name": "테스트출판", "category_code": "000", "pub_year": "2024",
                "copy_count": "abc", "location": "", "call_no": ""}
        self.assertIn("발행연도가 올바르지 않습니다", self.post(c, "/books/new", {**base, "pub_year": "2999"})[0])
        self.assertIn("도서를 등록했습니다", self.post(c, "/books/new", base)[0])   # 복본 수가 숫자가 아니면 기본값
        roles = self.sql("SELECT a.author_name, ba.author_role FROM book_author ba JOIN author a USING (author_id) "
                         "WHERE ba.isbn = '9791100099990' ORDER BY ba.author_order")
        self.assertEqual([(r["author_name"], r["author_role"]) for r in roles], [("홍길동", "지은이"), ("김철수", "엮은이")])
        page = c.get("/books/9791100099990/edit").data.decode()
        self.assertIn("김철수 (엮은이)", page)                                        # 수정 화면에서도 역할 유지
        self.post(c, "/books/9791100099990/edit", {**base, "title": "테스트 도서 2"})
        self.assertEqual(self.one("SELECT author_role FROM book_author ba JOIN author a USING (author_id) "
                                  "WHERE ba.isbn = '9791100099990' AND a.author_name = '김철수'")["author_role"], "엮은이")
        self.assertEqual(c.post("/books/9791100099990/copies", data={"count": "x"}).status_code, 302)

    # ---- 8. 접근 권한 ------------------------------------------------------------------
    def test_70_access_control(self):
        anon = self.app.test_client()
        self.assertEqual(anon.get("/loans/").headers["Location"], "/login?next=/loans/?")
        self.assertEqual(anon.get("/my/").headers["Location"], "/my/login?next=/my/?")
        member = self.member("20231234")
        self.assertTrue(member.get("/members/").headers["Location"].startswith("/login"))   # 회원은 사서 화면 불가
        self.assertEqual(member.get("/my/").status_code, 200)
        page = member.get("/my/").data.decode()
        self.assertNotIn("20257001", page)                                               # 다른 회원 정보 노출 없음

    def test_71_pages_with_suspension_and_overdue_render(self):
        self.assertEqual(self.staff().get("/members/10011").status_code, 200)           # 대출정지 이력 있는 회원
        self.assertEqual(self.member("20193321").get("/my/").status_code, 200)
        page = self.member("20211388").get("/my/").data.decode()                       # 연체만 있는 회원
        self.assertIn("연체 중인 도서가", page)
        self.assertNotIn("-까지 대출이 정지", page)
        self.assertEqual(self.staff().get("/closed-days/?year=abc").status_code, 200)

    def test_65_also_borrowed(self):
        # 뷰는 2명 이상이 함께 빌린 도서 쌍만 돌려준다 (한 사람의 대출 기록이 드러나지 않게)
        self.assertEqual(self.one("SELECT COUNT(*) AS n FROM v_also_borrowed WHERE borrower_count < 2")["n"], 0)
        self.assertEqual(self.one("SELECT COUNT(*) AS n FROM v_also_borrowed WHERE isbn = other_isbn")["n"], 0)
        top = self.one("SELECT isbn, other_isbn, borrower_count FROM v_also_borrowed "
                       "ORDER BY borrower_count DESC, isbn, other_isbn LIMIT 1")
        # 뷰의 회원 수가 대출 테이블에서 직접 센 값과 같다
        direct = self.one(
            """SELECT COUNT(*) AS n FROM (
                 SELECT l.member_id FROM loan l JOIN book_copy bc ON bc.copy_id = l.copy_id
                  WHERE bc.isbn IN (%s, %s) GROUP BY l.member_id HAVING COUNT(DISTINCT bc.isbn) = 2) x""",
            (top["isbn"], top["other_isbn"]))["n"]
        self.assertEqual(top["borrower_count"], direct)
        other_title = self.one("SELECT title FROM book WHERE isbn = %s", (top["other_isbn"],))["title"]
        for client, url in ((self.staff(), f"/books/{top['isbn']}"), (self.member("20231234"), f"/my/books/{top['isbn']}")):
            page = unescape(client.get(url).data.decode())
            self.assertIn("함께 대출한 책", page)
            self.assertIn(other_title, page)
        # 대출 이력이 없는 새 도서는 추천이 비어 있다
        self.sql("INSERT INTO book (isbn, title, publisher_id, category_code) VALUES ('9791100000017', '추천 없는 책', 1, '000')")
        try:
            self.assertIn("아직 함께 대출된 책이 없습니다", self.staff().get("/books/9791100000017").data.decode())
        finally:
            self.sql("DELETE FROM book WHERE isbn = '9791100000017'")

    def test_72_csrf_and_open_redirect(self):
        c = self.staff()
        self.assertEqual(c.post("/loans/return", data={"reg_no": "EM000001"},
                                headers={"Origin": "https://evil.example"}).status_code, 403)
        for bad in ("//evil.example", "\t//evil.example", "https://evil.example/"):
            r = self.app.test_client().post("/login?next=" + bad.replace("\t", "%09"),
                                            data={"login_id": "lib01", "password": "lib1234"})
            self.assertEqual(r.headers["Location"], "/")

    # ---- 9. DB 서버 분리 ---------------------------------------------------------------
    def test_80_system_info_shows_db_server(self):
        page = self.staff().get("/").data.decode()
        self.assertIn("DB 서버", page)
        self.assertRegex(page, r"library@[\w.:%-]+")                 # DB 서버가 본 접속 주소
        self.assertNotIn("DB 서버", self.member("20231234").get("/my/").data.decode())   # 회원 화면에는 없음

    def test_81_db_server_unreachable_shows_guide(self):
        app = create_app()
        app.config.update(DB_HOST="127.0.0.1", DB_PORT=1)             # 아무도 받지 않는 포트
        with self.assertLogs(app.logger, "ERROR"):                    # 연결 실패를 로그로 남긴다
            r = app.test_client().post("/login", data={"login_id": "lib01", "password": "lib1234"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("DB 서버에 연결할 수 없습니다", r.data.decode())


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""샘플 데이터 SQL 생성기.

  data/books.csv  →  sql/04_books.sql          (도서·출판사·저자·도서저자·도서복본)
  (생성 규칙)     →  sql/05_sample_loans.sql   (대출·연장·연체료·대출정지 이력)

대출 일자는 실행 시점(CURDATE) 기준 "며칠 전"으로 저장하고, 실제 날짜 계산(휴관일이면
앞당기기, 반납예정일, 연체일수)은 DB 함수(fn_next_open_day, fn_overdue_days)가 하므로
언제 DB 를 초기화해도 연체·반납예정 상황이 그대로 재현된다.

실행 : .venv/bin/python scripts/build_seed.py
"""
import csv
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOKS_CSV = ROOT / "data" / "books.csv"
BOOKS_SQL = ROOT / "sql" / "04_books.sql"
LOANS_SQL = ROOT / "sql" / "05_sample_loans.sql"

CHOSEONG = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
LOCATION = {
    "000": "3층 과학기술자료실", "400": "3층 과학기술자료실", "500": "3층 과학기술자료실",
    "100": "2층 인문사회자료실", "200": "2층 인문사회자료실", "300": "2층 인문사회자료실",
    "900": "2층 인문사회자료실",
    "600": "4층 어문예술자료실", "700": "4층 어문예술자료실", "800": "4층 어문예술자료실",
}

# 회원 : (member_id, 회원구분, 대출기간, 최대권수)  ※ 03_base_data.sql 과 일치해야 함
MEMBERS = {
    10001: ("UG", 14, 10), 10002: ("UG", 14, 10), 10003: ("UG", 14, 10), 10004: ("UG", 14, 10),
    10005: ("UG", 14, 10), 10006: ("UG", 14, 10), 10007: ("UG", 14, 10), 10008: ("UG", 14, 10),
    10009: ("UG", 14, 10), 10010: ("UG", 14, 10), 10011: ("UG", 14, 10), 10012: ("UG", 14, 10),
    10013: ("UG", 14, 10), 10014: ("UG", 14, 10), 10015: ("UG", 14, 10), 10016: ("UG", 14, 10),
    10017: ("UG", 14, 10), 10018: ("UG", 14, 10), 10019: ("UG", 14, 10), 10020: ("UG", 14, 10),
    10021: ("UGL", 14, 5), 10022: ("GR", 30, 15), 10023: ("GR", 30, 15), 10024: ("FAC", 180, 50),
    10025: ("FAC", 180, 50), 10026: ("STF", 30, 15), 10027: ("STF", 30, 15),
}
WITHDRAWN = {10020: 90}          # 회원: 며칠 전 탈퇴
HISTORY_DAYS = 200               # 이력 생성 범위 (며칠 전까지)
GAP = 6                          # 같은 복본의 앞 대출 반납 ~ 다음 대출 사이 최소 간격 (휴관일 보정 여유)
BUFFER = 5                       # 휴관일 보정으로 날짜가 앞뒤로 밀릴 수 있는 여유 (일)
# 시연용 대출정지 (회원, 시작 며칠 전, 종료 며칠 전 또는 해제 며칠 전) — 이 기간에는 대출·연장 이력을 만들지 않는다
SUSPENSIONS = {10011: (3, 0), 10005: (40, 30), 10013: (80, 66)}


def esc(s):
    return "NULL" if s is None or s == "" else "'" + str(s).replace("\\", "\\\\").replace("'", "''") + "'"


def initial(ch):
    """한글 음절의 초성 (가 → ㄱ). 한글이 아니면 그대로."""
    code = ord(ch) - 0xAC00
    return CHOSEONG[code // 588] if 0 <= code < 11172 else ch.upper()


def author_mark(author, title):
    """간이 저자기호: 저자 첫 글자 + 두 번째 글자 코드 기반 숫자 + 서명 첫 글자 초성 (예: 한12ㅅ)"""
    name = author.replace(" ", "") or "무"
    num = (ord(name[1]) % 90 + 10) if len(name) > 1 else 10
    first = next((c for c in title if c.strip() and c not in "\"'([<"), "ㅇ")
    return f"{name[0]}{num}{initial(first)}"


def copies_for(index):
    """도서 순번별 복본 수 (1~3권)"""
    return 3 if index % 7 == 0 else 2 if index % 3 == 0 else 1


def load_books():
    with BOOKS_CSV.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["authors"] = [tuple(a.rsplit(":", 1)) for a in r["authors"].split(";") if a]
    return rows


def build_books_sql(books):
    publishers, authors = {}, {}
    out = ["-- =====================================================================",
           "-- 도서 데이터 (scripts/build_seed.py 가 data/books.csv 에서 생성 — 직접 수정하지 말 것)",
           f"-- 실제 도서 {len(books)}종. 서지정보 출처는 data/books.csv 의 source 열 참고",
           "-- =====================================================================",
           "USE library_db;", ""]
    for b in books:
        publishers.setdefault(b["publisher"], len(publishers) + 1)
        # 같은 사람이 한 도서에 두 역할로 나오면 (isbn, author_id) PK 충돌 → 첫 역할만 남긴다
        b["authors"] = list({name: (name, role) for name, role in reversed(b["authors"])}.values())[::-1]
        for name, _ in b["authors"]:
            authors.setdefault(name, len(authors) + 1)
    out.append("INSERT INTO publisher (publisher_id, publisher_name) VALUES")
    out.append(",\n".join(f"  ({i}, {esc(n)})" for n, i in publishers.items()) + ";\n")
    out.append("INSERT INTO author (author_id, author_name) VALUES")
    out.append(",\n".join(f"  ({i}, {esc(n)})" for n, i in authors.items()) + ";\n")
    out.append("INSERT INTO book (isbn, title, publisher_id, category_code, kdc_no, pub_year, price) VALUES")
    out.append(",\n".join(
        f"  ({esc(b['isbn'])}, {esc(b['title'])}, {publishers[b['publisher']]}, {esc(b['category_code'])}, "
        f"{esc(b['kdc_no'])}, {b['pub_year'] or 'NULL'}, {b['price'] or 'NULL'})" for b in books) + ";\n")
    out.append("INSERT INTO book_author (isbn, author_id, author_role, author_order) VALUES")
    out.append(",\n".join(
        f"  ({esc(b['isbn'])}, {authors[name]}, {esc(role)}, {n})"
        for b in books for n, (name, role) in enumerate(b["authors"], 1)) + ";\n")
    copy_rows, copy_book = [], []
    for i, b in enumerate(books, 1):
        base = f"{b['kdc_no'] or b['category_code']}-{author_mark(b['authors'][0][0], b['title'])}"
        year = int(b["pub_year"] or 2000)
        acquired = "2024-03-02" if year < 2024 else f"{year}-03-02" if year < 2026 else "2026-03-02"
        for c in range(1, copies_for(i) + 1):
            copy_id = len(copy_rows) + 1
            call_no = base if c == 1 else f"{base} c.{c}"
            copy_rows.append(f"  ({copy_id}, 'EM{copy_id:06d}', {esc(b['isbn'])}, {esc(call_no)}, "
                             f"{esc(LOCATION[b['category_code']])}, '{acquired}')")
            copy_book.append(i)
    out.append("INSERT INTO book_copy (copy_id, reg_no, isbn, call_no, location, acquired_date) VALUES")
    out.append(",\n".join(copy_rows) + ";\n")
    BOOKS_SQL.write_text("\n".join(out), encoding="utf-8")
    return copy_book


class Planner:
    """복본·회원별 대출 구간이 겹치지 않도록 대출 이력을 배치한다. (값은 모두 '며칠 전')"""

    def __init__(self, n_copies):
        self.copy_busy = {c: [] for c in range(1, n_copies + 1)}   # [(시작, 끝)] 끝=0 이면 현재 대출 중
        self.member_busy = {m: [] for m in MEMBERS}
        self.blocked = {m: [] for m in MEMBERS}      # 대출·연장을 시작할 수 없는 기간 [(시작, 끝)] (연체·미납·정지)
        self.starts = {m: [] for m in MEMBERS}       # 회원이 대출·연장을 한 시점들
        self.rows = []
        self.removed = set()
        for member, (start, end) in SUSPENSIONS.items():
            self.blocked[member].append((start, end))

    def copy_free(self, copy_id, start, end):
        for s, e in self.copy_busy[copy_id]:
            if not (end - GAP >= s or start + GAP <= e):    # 겹치면 (간격 포함)
                return False
        return copy_id not in self.removed

    def member_ok(self, member, start, end):
        limit = MEMBERS[member][2]
        overlapping = sum(1 for s, e in self.member_busy[member] if not (end >= s or start <= e))
        return overlapping + 1 <= limit

    def is_blocked(self, member, ago):
        return any(start + BUFFER >= ago >= end - BUFFER for start, end in self.blocked[member])

    def new_block(self, member, loan_ago, return_ago, renews, fine_status):
        """이 대출 때문에 생기는 '대출 불가 기간' (연체 중 ~ 반납, 미납이면 지금까지)"""
        days = MEMBERS[member][1]
        due_ago = (renews[-1] if renews else loan_ago) - days
        if return_ago is None:
            return (due_ago, 0) if due_ago > 0 else None
        if return_ago < due_ago:                                  # 반납예정일 이후 반납 = 연체
            return (due_ago, 0 if fine_status == "미납" else return_ago)
        return None

    def allowed(self, member, loan_ago, return_ago, renews, fine_status):
        if any(self.is_blocked(member, ago) for ago in (loan_ago, *renews)):
            return False
        block = self.new_block(member, loan_ago, return_ago, renews, fine_status)
        return not block or not any(block[0] + BUFFER >= ago >= block[1] - BUFFER for ago in self.starts[member])

    def add(self, member, copy_id, loan_ago, return_ago=None, renews=(), fine_status="납부", lost=False):
        end = return_ago if return_ago is not None else 0
        assert self.copy_free(copy_id, loan_ago, end), (member, copy_id, loan_ago, return_ago)
        assert self.allowed(member, loan_ago, return_ago, renews, fine_status), (member, loan_ago, return_ago)
        block = self.new_block(member, loan_ago, return_ago, renews, fine_status)
        if block:
            self.blocked[member].append(block)
        self.starts[member].extend((loan_ago, *renews))
        self.copy_busy[copy_id].append((loan_ago, end))
        self.member_busy[member].append((loan_ago, end))
        self.rows.append((len(self.rows) + 1, copy_id, member, loan_ago, return_ago,
                          renews[0] if len(renews) > 0 else None, renews[1] if len(renews) > 1 else None,
                          fine_status, 1 if lost else 0))
        if lost:
            self.removed.add(copy_id)


def plan_loans(copy_book):
    rnd = random.Random(2026)
    n_copies = len(copy_book)
    p = Planner(n_copies)
    used = set()

    def pick(pred=lambda c: True, start=0, end=0):
        order = list(range(1, n_copies + 1))
        rnd.shuffle(order)
        for c in order:
            if c not in used and pred(c) and p.copy_free(c, start, end):
                used.add(c)
                return c
        raise RuntimeError("남은 복본이 없습니다")

    # ---- 시연 시나리오 (현재 상태) --------------------------------------------------------
    # 10001 김민준 : 정상 회원 (포털 시연 계정). 연장 가능한 대출 2건 + 지난 기록
    p.add(10001, pick(start=5), 5)
    p.add(10001, pick(start=9), 9, renews=(4,))
    # 10002 이서연 : 오늘 대출 → 대출 당일 연장 불가
    p.add(10002, pick(start=0), 0)
    # 10003 박지훈 : 연체 2권
    p.add(10003, pick(start=24), 24)
    p.add(10003, pick(start=20), 20)
    # 10004 최수아 : 연체 1권 (대출 거부 → 반납 시 연체료 부과 시연)
    p.add(10004, pick(start=25), 25)
    # 10006 강하은 : 연장 2회 모두 사용
    p.add(10006, pick(start=13), 13, renews=(9, 3))
    # 10008 윤지우 : 반납 예정 임박 (1~2일 후)
    p.add(10008, pick(start=12), 12)
    # 10009 장서준 : 미납 연체료 (연체 반납) → 대출 거부, 납부 후 대출 가능
    p.add(10009, pick(start=40, end=20), 40, 20, fine_status="미납")
    # 10011 한지민 : 대출정지 중 (아래 suspension)
    # 10012 오태양 : 장기 연체 (30일 이상)
    p.add(10012, pick(start=60), 60)
    # 10015 권나연 : 분실 처리 이력 (연체 후 분실, 연체료 납부)
    p.add(10015, pick(start=70, end=50), 70, 50, lost=True)
    # 10022 노현우 대학원생 : 30일 대출 3권
    for ago in (3, 11, 22):
        p.add(10022, pick(start=ago), ago)
    # 10024 이정훈 교수 : 180일 대출 6권, 1권은 연장 1회(최대) 사용
    for ago in (15, 40, 75, 100, 130):
        p.add(10024, pick(start=ago), ago)
    p.add(10024, pick(start=170), 170, renews=(150,))
    # 10025 박미경 교수 : 3권
    for ago in (8, 33, 61):
        p.add(10025, pick(start=ago), ago)
    # 10026, 10027 직원·비전임교원
    p.add(10026, pick(start=12), 12)
    p.add(10027, pick(start=26), 26)
    # 10023 유가은 대학원생 : 연체 (30일 대출)
    p.add(10023, pick(start=38), 38)
    # 10013 서유진 : 30일 이상 장기 연체 후 반납 → 아래 '장기연체' 대출정지의 근거
    p.add(10013, pick(start=135, end=82), 135, 82)
    # 10020 문성훈 : 탈퇴 전 이력
    for ago in (150, 125, 100):
        p.add(10020, pick(start=ago, end=ago - 10), ago, ago - 10)

    # ---- 지난 대출 이력 (무작위, 결정적) -------------------------------------------------
    popular = [c for c in range(1, n_copies + 1) if copy_book[c - 1] % 4 == 1]
    regular_members = [m for m in MEMBERS if m not in WITHDRAWN]
    target = 230
    tries = 0
    while len(p.rows) < target and tries < 20000:
        tries += 1
        member = rnd.choice(regular_members)
        _, days, limit = MEMBERS[member]
        if member in (10024, 10025):                    # 교수는 이력보다 장기 대출 위주
            continue
        loan_ago = rnd.randint(days + 8, HISTORY_DAYS)
        late = rnd.random() < 0.15
        held = days + rnd.randint(4, 12) if late else rnd.randint(3, days - 1)
        return_ago = loan_ago - held
        if return_ago < 1:
            continue
        renews = ()
        if not late and rnd.random() < 0.15 and held > 6:
            renews = (loan_ago - rnd.randint(2, 5),)     # 대출 며칠 뒤 연장
            held = min(held + days // 2, loan_ago - 1)
            return_ago = loan_ago - held
        pool = popular if rnd.random() < 0.5 else range(1, n_copies + 1)
        candidates = [c for c in pool if p.copy_free(c, loan_ago, return_ago)]
        status = "납부" if rnd.random() < 0.85 else "면제"
        if (not candidates or not p.member_ok(member, loan_ago, return_ago)
                or not p.allowed(member, loan_ago, return_ago, renews, status)):
            continue
        p.add(member, rnd.choice(candidates), loan_ago, return_ago, renews=renews, fine_status=status)
    return p


def build_loans_sql(p):
    rows = sorted(p.rows, key=lambda r: (-r[3], r[0]))        # 오래된 대출부터 loan_id 부여
    values = ",\n".join(
        f"  ({n}, {r[1]}, {r[2]}, {r[3]}, {'NULL' if r[4] is None else r[4]}, "
        f"{'NULL' if r[5] is None else r[5]}, {'NULL' if r[6] is None else r[6]}, '{r[7]}', {r[8]})"
        for n, r in enumerate(rows, 1))
    sql = f"""-- =====================================================================
-- 대출 이력 샘플 (scripts/build_seed.py 가 생성 — 직접 수정하지 말 것)
-- 값은 모두 '오늘로부터 며칠 전'. 날짜 계산은 DB 함수가 한다.
--   · 대출일·연장일·반납일이 휴관일이면 그 전 개관일로 앞당김
--   · 반납예정일 = fn_next_open_day(대출일 + 대출기간), 연장 = fn_next_open_day(연장일 + 대출기간)
--   · 연체 반납이면 fn_overdue_days(휴관일 제외)로 연체료 생성
-- 대출 {len(rows)}건 (현재 대출 중 {sum(1 for r in rows if r[4] is None)}건)
-- =====================================================================
USE library_db;

CREATE TEMPORARY TABLE tmp_loan (
  loan_id INT PRIMARY KEY, copy_id INT, member_id INT, loan_ago INT, return_ago INT NULL,
  renew1_ago INT NULL, renew2_ago INT NULL, fine_status VARCHAR(10), lost TINYINT
);
INSERT INTO tmp_loan VALUES
{values};

DELIMITER $$
DROP FUNCTION IF EXISTS fn_seed_open_day $$
CREATE FUNCTION fn_seed_open_day(p_date DATE) RETURNS DATE
READS SQL DATA
BEGIN
  DECLARE v_date DATE DEFAULT p_date;
  WHILE EXISTS (SELECT 1 FROM closed_day WHERE closed_date = v_date) DO
    SET v_date = v_date - INTERVAL 1 DAY;
  END WHILE;
  RETURN v_date;
END $$

DROP PROCEDURE IF EXISTS sp_seed_loans $$
CREATE PROCEDURE sp_seed_loans()
BEGIN
  DECLARE v_done INT DEFAULT 0;
  DECLARE v_id, v_copy, v_member, v_loan_ago, v_return_ago, v_r1, v_r2, v_lost, v_days, v_fine_day, v_od INT;
  DECLARE v_status VARCHAR(10);
  DECLARE v_loan, v_due, v_new_due, v_ren, v_ret DATE;
  DECLARE cur CURSOR FOR
    SELECT t.loan_id, t.copy_id, t.member_id, t.loan_ago, t.return_ago, t.renew1_ago, t.renew2_ago,
           t.fine_status, t.lost, mt.loan_days, mt.fine_per_day
      FROM tmp_loan t JOIN member m ON m.member_id = t.member_id JOIN member_type mt ON mt.type_code = m.type_code
     ORDER BY t.loan_id;
  DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = 1;

  OPEN cur;
  seed: LOOP
    FETCH cur INTO v_id, v_copy, v_member, v_loan_ago, v_return_ago, v_r1, v_r2, v_status, v_lost, v_days, v_fine_day;
    IF v_done THEN LEAVE seed; END IF;

    -- '오늘 대출' 시나리오는 초기화한 날이 휴관일이어도 오늘 날짜로 둔다 (대출 당일 연장 불가 시연용)
    SET v_loan = IF(v_loan_ago = 0, CURDATE(), fn_seed_open_day(CURDATE() - INTERVAL v_loan_ago DAY));
    SET v_due = fn_next_open_day(v_loan + INTERVAL v_days DAY);
    INSERT INTO loan (loan_id, copy_id, member_id, staff_id, loan_date, due_date)
    VALUES (v_id, v_copy, v_member, 2, TIMESTAMP(v_loan, '10:00:00'), v_due);

    -- 연장 (대출 다음 날 이후 + 연체 전 + 반납예정일이 실제로 늦어지는 경우만)
    IF v_r1 IS NOT NULL THEN
      SET v_ren = fn_seed_open_day(CURDATE() - INTERVAL v_r1 DAY);
      SET v_new_due = fn_next_open_day(v_ren + INTERVAL v_days DAY);
      IF v_ren > v_loan AND v_ren <= v_due AND v_new_due > v_due THEN
        INSERT INTO renewal (loan_id, renewed_at, prev_due_date, new_due_date, channel, staff_id)
        VALUES (v_id, TIMESTAMP(v_ren, '12:00:00'), v_due, v_new_due, '홈페이지', NULL);
        SET v_due = v_new_due;
      END IF;
    END IF;
    IF v_r2 IS NOT NULL THEN
      SET v_ren = fn_seed_open_day(CURDATE() - INTERVAL v_r2 DAY);
      SET v_new_due = fn_next_open_day(v_ren + INTERVAL v_days DAY);
      IF v_ren > v_loan AND v_ren <= v_due AND v_new_due > v_due THEN
        INSERT INTO renewal (loan_id, renewed_at, prev_due_date, new_due_date, channel, staff_id)
        VALUES (v_id, TIMESTAMP(v_ren, '13:00:00'), v_due, v_new_due, '사서', 2);
        SET v_due = v_new_due;
      END IF;
    END IF;
    UPDATE loan SET due_date = v_due WHERE loan_id = v_id;

    IF v_return_ago IS NOT NULL THEN
      SET v_ret = GREATEST(fn_seed_open_day(CURDATE() - INTERVAL v_return_ago DAY), v_loan);
      UPDATE loan SET return_date = TIMESTAMP(v_ret, '16:00:00'), return_type = IF(v_lost, '분실', '반납'),
                      return_staff_id = 2
       WHERE loan_id = v_id;
      SET v_od = fn_overdue_days(v_due, v_ret);
      IF v_od > 0 THEN
        INSERT INTO fine (loan_id, overdue_days, amount, status, imposed_date, paid_date, staff_id)
        VALUES (v_id, v_od, v_od * v_fine_day, v_status, v_ret,
                IF(v_status = '미납', NULL, v_ret), IF(v_status = '미납', NULL, IF(v_status = '면제', 1, 2)));
      END IF;
    END IF;
  END LOOP;
  CLOSE cur;
END $$
DELIMITER ;

CALL sp_seed_loans();
DROP PROCEDURE sp_seed_loans;
DROP FUNCTION fn_seed_open_day;
DROP TEMPORARY TABLE tmp_loan;

-- 복본 상태를 대출 데이터와 일치시킴 (트리거가 분실·폐기일을 기록)
UPDATE book_copy SET status = '대출중' WHERE copy_id IN (SELECT copy_id FROM loan WHERE return_date IS NULL);
UPDATE book_copy SET status = '분실'   WHERE copy_id IN (SELECT copy_id FROM loan WHERE return_type = '분실');
UPDATE book_copy SET status = '폐기'
 WHERE copy_id = (SELECT c FROM (SELECT MAX(copy_id) AS c FROM book_copy
                                  WHERE status = '대출가능' AND copy_id NOT IN (SELECT copy_id FROM loan)) x);

-- 대출정지 (사서 수동 제재) : 진행 중 1건, 조기 해제 1건, 기간 만료 1건
INSERT INTO suspension (member_id, reason, start_date, end_date, memo, staff_id, released_date, released_staff_id) VALUES
  (10011, '자료훼손', CURDATE() - INTERVAL 3 DAY,  CURDATE() + INTERVAL 10 DAY, '대출 도서 낙서·훼손 (동일 도서 변상 완료)', 2, NULL, NULL),
  (10005, '규정위반', CURDATE() - INTERVAL 40 DAY, CURDATE() - INTERVAL 20 DAY, '열람실 좌석 무단 점유', 2, CURDATE() - INTERVAL 30 DAY, 1),
  (10013, '장기연체', CURDATE() - INTERVAL 80 DAY, CURDATE() - INTERVAL 66 DAY, '30일 이상 장기 연체 후 반납', 1, NULL, NULL);
"""
    LOANS_SQL.write_text(sql, encoding="utf-8")


def main():
    books = load_books()
    copy_book = build_books_sql(books)
    planner = plan_loans(copy_book)
    build_loans_sql(planner)
    active = sum(1 for r in planner.rows if r[4] is None)
    print(f"도서 {len(books)}종 · 복본 {len(copy_book)}권 → {BOOKS_SQL.name}")
    print(f"대출 {len(planner.rows)}건 (대출 중 {active}건) → {LOANS_SQL.name}")


if __name__ == "__main__":
    main()

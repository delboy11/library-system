"""DB 메타데이터(information_schema)로 보고서 문서를 생성한다.

  09 용어 사전 · 10 도메인 정의서 · 11 테이블 기술서 · 08 물리 모델의 제약조건/인덱스/프로그램 목록

문서와 실제 DB 가 어긋나지 않도록, 컬럼 주석(COMMENT)·제약조건·인덱스를 DB 에서 직접 읽는다.
또한 모든 컬럼이 도메인에 매핑되어 있는지, 컬럼명의 모든 단어가 용어 사전에 있는지 검사한다.

실행 : .venv/bin/python scripts/gen_docs.py   (DB 가 초기화된 상태여야 함)
"""
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
DB = os.environ.get("DB_NAME", "library_db")

TABLE_ORDER = [
    "member_type", "member", "staff", "category", "publisher", "author", "book", "book_author",
    "book_copy", "loan", "renewal", "fine", "suspension", "closed_day",
]

# ---------------------------------------------------------------------------
# 표준 단어 : 컬럼명은 아래 단어(영문 약어)의 조합으로만 만든다.
#   (영문 약어, 한글 단어, 영문 원어, 정의)
# ---------------------------------------------------------------------------
WORDS = [
    ("member", "회원", "Member", "도서관에 가입해 도서를 대출하는 학생·교직원"),
    ("type", "구분", "Type", "같은 성격의 대상을 나누는 기준"),
    ("code", "코드", "Code", "대상을 짧게 식별하기 위해 정한 부호"),
    ("name", "명", "Name", "대상을 부르는 이름"),
    ("max", "최대", "Maximum", "허용되는 가장 큰 값"),
    ("loan", "대출", "Loan", "회원이 도서복본을 일정 기간 빌려 가는 행위"),
    ("count", "수", "Count", "개수"),
    ("days", "일수", "Days", "날짜의 수"),
    ("renew", "연장", "Renew", "반납예정일을 뒤로 늦추는 행위"),
    ("renewal", "연장", "Renewal", "연장 1회의 기록"),
    ("fine", "연체료", "Fine", "반납예정일을 넘겨 반납했을 때 부과하는 금액"),
    ("per", "당", "Per", "단위 기준"),
    ("day", "일", "Day", "하루"),
    ("id", "번호", "Identifier", "시스템이 부여하는 내부 식별 번호"),
    ("no", "번호", "Number", "업무에서 사용하는 식별 번호 (학번, 등록번호 등)"),
    ("password", "비밀번호", "Password", "로그인 인증용 비밀 문자열"),
    ("hash", "해시", "Hash", "단방향 암호화한 값"),
    ("department", "소속", "Department", "회원이 속한 학과·부서"),
    ("phone", "전화번호", "Phone", "휴대전화 번호"),
    ("email", "이메일", "Email", "전자우편 주소"),
    ("status", "상태", "Status", "대상의 현재 상태값"),
    ("join", "가입", "Join", "회원으로 등록함"),
    ("date", "일자", "Date", "연·월·일"),
    ("withdraw", "탈퇴", "Withdraw", "회원 자격을 해지함"),
    ("staff", "사서", "Staff", "도서관 관리 프로그램을 사용하는 직원"),
    ("login", "로그인", "Login", "시스템 접속 인증"),
    ("role", "역할", "Role", "권한 또는 맡은 역할"),
    ("hire", "입사", "Hire", "직원으로 채용됨"),
    ("category", "분류", "Category", "한국십진분류법(KDC) 주류"),
    ("publisher", "출판사", "Publisher", "도서를 발행한 회사"),
    ("author", "저자", "Author", "도서의 지은이·옮긴이 등"),
    ("order", "순서", "Order", "표기 순서"),
    ("isbn", "ISBN", "International Standard Book Number", "국제표준도서번호 13자리"),
    ("title", "서명", "Title", "도서의 제목"),
    ("kdc", "KDC", "Korean Decimal Classification", "한국십진분류법"),
    ("pub", "발행", "Publication", "출판"),
    ("year", "연도", "Year", "해"),
    ("price", "정가", "Price", "도서에 표시된 가격(원)"),
    ("created", "등록", "Created", "데이터가 처음 등록됨"),
    ("at", "일시", "At", "날짜와 시각"),
    ("book", "도서", "Book", "ISBN 으로 구별되는 서지(책의 종류)"),
    ("copy", "복본", "Copy", "같은 도서의 실물 책 1권"),
    ("reg", "등록", "Registration", "도서관 자산으로 등록함"),
    ("call", "청구", "Call", "서가에서 책을 찾기 위한 청구기호의 '청구'"),
    ("location", "배가위치", "Location", "복본이 꽂혀 있는 자료실·서가"),
    ("acquired", "입수", "Acquired", "도서관에 들어옴"),
    ("removed", "제적", "Removed", "분실·폐기로 장서에서 빠짐"),
    ("due", "반납예정", "Due", "반납해야 하는 날"),
    ("return", "반납", "Return", "대출한 책을 돌려줌"),
    ("active", "진행중", "Active", "아직 끝나지 않은 상태"),
    ("renewed", "연장", "Renewed", "연장 처리됨"),
    ("prev", "이전", "Previous", "변경 전 값"),
    ("new", "신규", "New", "변경 후 값"),
    ("channel", "신청경로", "Channel", "요청이 들어온 경로 (홈페이지/사서)"),
    ("overdue", "연체", "Overdue", "반납예정일이 지났는데 반납하지 않음"),
    ("amount", "금액", "Amount", "원 단위 금액"),
    ("imposed", "부과", "Imposed", "의무를 지움"),
    ("paid", "처리", "Paid", "납부 또는 면제로 종결됨"),
    ("suspension", "대출정지", "Suspension", "일정 기간 대출 자격을 정지함"),
    ("reason", "사유", "Reason", "어떤 일이 일어난 이유"),
    ("start", "시작", "Start", "기간의 처음"),
    ("end", "종료", "End", "기간의 끝"),
    ("memo", "비고", "Memo", "참고 메모"),
    ("released", "해제", "Released", "정지를 풀어 줌"),
    ("closed", "휴관", "Closed", "도서관이 문을 닫음"),
]
WORD_MAP = {w[0]: w for w in WORDS}

# ---------------------------------------------------------------------------
# 도메인 : (도메인명, 데이터 타입, 허용값·형식, 설명)
# ---------------------------------------------------------------------------
DOMAINS = {
    "ID번호": ("INT UNSIGNED", "1 이상 정수, AUTO_INCREMENT", "내부 식별자 (대리키)"),
    "코드": ("VARCHAR(10)", "영문 대문자 코드", "구분 코드"),
    "분류코드": ("CHAR(3)", "'000' ~ '900' (100 단위)", "KDC 주류 코드"),
    "KDC기호": ("VARCHAR(20)", "예: 813.7, 005.133", "KDC 상세 분류기호"),
    "ISBN": ("CHAR(13)", "978 또는 979 로 시작하는 숫자 13자리", "국제표준도서번호"),
    "등록번호": ("VARCHAR(10)", "'EM' + 숫자 6자리", "복본 바코드 번호"),
    "학번": ("VARCHAR(20)", "영문·숫자 4~20자", "학번·교번 (회원 로그인 ID)"),
    "로그인ID": ("VARCHAR(20)", "영문·숫자", "사서 로그인 ID"),
    "비밀번호해시": ("VARCHAR(255)", "scrypt 해시 문자열", "평문 비밀번호는 저장하지 않음"),
    "이름": ("VARCHAR(30)", "1~30자", "사람 이름"),
    "명칭": ("VARCHAR(50)", "1~50자", "출판사·저자·소속 등의 명칭"),
    "짧은명칭": ("VARCHAR(30)", "1~30자", "분류명·배가위치·휴관사유 등"),
    "구분명": ("VARCHAR(20)", "1~20자", "회원구분명"),
    "서명": ("VARCHAR(200)", "1~200자", "도서 제목"),
    "청구기호": ("VARCHAR(40)", "분류기호-저자기호 (예: 813.7-한12ㅅ)", "서가 위치 기호"),
    "전화번호": ("VARCHAR(13)", "010-0000-0000 형식", "휴대전화"),
    "이메일": ("VARCHAR(100)", "이메일 형식", "전자우편"),
    "비고": ("VARCHAR(200)", "자유 입력", "메모"),
    "권수": ("TINYINT UNSIGNED", "1 ~ 100", "대출 가능 권수"),
    "일수": ("TINYINT UNSIGNED", "1 ~ 180", "기간(일)"),
    "횟수": ("TINYINT UNSIGNED", "0 ~ 10", "연장 횟수 등"),
    "연체일수": ("SMALLINT UNSIGNED", "1 이상", "반납예정일 다음 날부터 반납일까지 일수"),
    "금액": ("INT UNSIGNED", "0 이상 (원)", "금액"),
    "연도": ("SMALLINT UNSIGNED", "1450 ~ 2100", "발행연도"),
    "순서": ("TINYINT UNSIGNED", "1 이상", "표기 순서"),
    "일자": ("DATE", "YYYY-MM-DD", "날짜"),
    "일시": ("DATETIME", "YYYY-MM-DD HH:MM:SS", "날짜와 시각"),
    "계정상태": ("VARCHAR(10)", "'정상', '탈퇴'", "회원 계정 상태"),
    "사서권한": ("VARCHAR(10)", "'관리자', '사서'", "사서 권한"),
    "저자역할": ("VARCHAR(10)", "'지은이', '옮긴이', '엮은이', '그림'", "도서에서 저자의 역할"),
    "복본상태": ("VARCHAR(10)", "'대출가능', '대출중', '분실', '폐기'", "도서복본 상태"),
    "반납구분": ("VARCHAR(10)", "'반납', '분실'", "대출 종료 방식"),
    "신청경로": ("VARCHAR(10)", "'홈페이지', '사서'", "연장 신청 경로"),
    "납부상태": ("VARCHAR(10)", "'미납', '납부', '면제'", "연체료 처리 상태"),
    "정지사유": ("VARCHAR(10)", "'장기연체', '자료훼손', '규정위반', '기타'", "대출정지 사유"),
}

# 컬럼 → 도메인 (테이블.컬럼 으로 지정한 것이 우선, 그다음 컬럼명)
COLUMN_DOMAIN = {
    "member_type.type_code": "코드", "member.type_code": "코드",
    "member_type.type_name": "구분명", "max_loan_count": "권수", "loan_days": "일수",
    "max_renew": "횟수", "fine_per_day": "금액",
    "member_id": "ID번호", "staff_id": "ID번호", "publisher_id": "ID번호", "author_id": "ID번호",
    "copy_id": "ID번호", "loan_id": "ID번호", "renewal_id": "ID번호", "fine_id": "ID번호",
    "suspension_id": "ID번호", "return_staff_id": "ID번호", "released_staff_id": "ID번호",
    "active_copy_id": "ID번호",
    "member_no": "학번", "login_id": "로그인ID", "password_hash": "비밀번호해시",
    "member.name": "이름", "staff.name": "이름", "department": "명칭",
    "phone": "전화번호", "email": "이메일",
    "member.status": "계정상태", "staff.role": "사서권한", "book_copy.status": "복본상태", "fine.status": "납부상태",
    "join_date": "일자", "withdraw_date": "일자", "hire_date": "일자", "acquired_date": "일자",
    "removed_date": "일자", "due_date": "일자", "prev_due_date": "일자", "new_due_date": "일자",
    "imposed_date": "일자", "paid_date": "일자", "start_date": "일자", "end_date": "일자",
    "released_date": "일자", "closed_date": "일자",
    "loan_date": "일시", "return_date": "일시", "renewed_at": "일시", "created_at": "일시",
    "category_code": "분류코드", "category_name": "짧은명칭", "publisher_name": "명칭", "author_name": "명칭",
    "isbn": "ISBN", "title": "서명", "kdc_no": "KDC기호", "pub_year": "연도", "price": "금액",
    "author_role": "저자역할", "author_order": "순서",
    "reg_no": "등록번호", "call_no": "청구기호", "location": "짧은명칭",
    "return_type": "반납구분", "channel": "신청경로",
    "overdue_days": "연체일수", "amount": "금액",
    "reason": "정지사유", "closed_day.reason": "짧은명칭", "memo": "비고",
}


def connect():
    return pymysql.connect(
        host=os.environ.get("DB_HOST", "127.0.0.1"), port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "library"), password=os.environ.get("DB_PASSWORD", "library1234"),
        database=DB, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def q(cur, sql, args=None):
    cur.execute(sql, args)
    return cur.fetchall()


def split_comment(comment):
    """'휴대전화 (010-0000-0000)' → ('휴대전화', '010-0000-0000')"""
    m = re.match(r"^(.*?)(?:\s+\((.*)\))?(?:\s+-\s+(.*))?$", comment or "")
    name = (m.group(1) or "").strip()
    note = " / ".join(x for x in (m.group(2), m.group(3)) if x)
    return name, note


def column_domain(table, column):
    return COLUMN_DOMAIN.get(f"{table}.{column}") or COLUMN_DOMAIN.get(column)


def load(cur):
    tables = {t["TABLE_NAME"]: t for t in q(cur, """
        SELECT TABLE_NAME, TABLE_COMMENT FROM information_schema.TABLES
         WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE'""", (DB,))}
    columns = defaultdict(list)
    for c in q(cur, """
        SELECT TABLE_NAME, COLUMN_NAME, ORDINAL_POSITION, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT,
               COLUMN_KEY, EXTRA, COLUMN_COMMENT, GENERATION_EXPRESSION
          FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = %s ORDER BY TABLE_NAME, ORDINAL_POSITION""", (DB,)):
        columns[c["TABLE_NAME"]].append(c)
    constraints = defaultdict(list)
    for c in q(cur, """
        SELECT tc.TABLE_NAME, tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE,
               GROUP_CONCAT(k.COLUMN_NAME ORDER BY k.ORDINAL_POSITION) AS cols,
               MAX(k.REFERENCED_TABLE_NAME) AS ref_table,
               GROUP_CONCAT(k.REFERENCED_COLUMN_NAME ORDER BY k.ORDINAL_POSITION) AS ref_cols,
               MAX(rc.UPDATE_RULE) AS on_update, MAX(rc.DELETE_RULE) AS on_delete,
               MAX(cc.CHECK_CLAUSE) AS check_clause
          FROM information_schema.TABLE_CONSTRAINTS tc
          LEFT JOIN information_schema.KEY_COLUMN_USAGE k
            ON k.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND k.TABLE_NAME = tc.TABLE_NAME
           AND k.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
          LEFT JOIN information_schema.REFERENTIAL_CONSTRAINTS rc
            ON rc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND rc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
          LEFT JOIN information_schema.CHECK_CONSTRAINTS cc
            ON cc.CONSTRAINT_SCHEMA = tc.CONSTRAINT_SCHEMA AND cc.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
         WHERE tc.TABLE_SCHEMA = %s
         GROUP BY tc.TABLE_NAME, tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE
         ORDER BY tc.TABLE_NAME, FIELD(tc.CONSTRAINT_TYPE, 'PRIMARY KEY', 'UNIQUE', 'FOREIGN KEY', 'CHECK'),
                  tc.CONSTRAINT_NAME""", (DB,)):
        constraints[c["TABLE_NAME"]].append(c)
    indexes = defaultdict(list)
    for i in q(cur, """
        SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE,
               GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX) AS cols
          FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = %s
         GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE ORDER BY TABLE_NAME, INDEX_NAME""", (DB,)):
        indexes[i["TABLE_NAME"]].append(i)
    routines = q(cur, """
        SELECT ROUTINE_NAME, ROUTINE_TYPE, ROUTINE_COMMENT FROM information_schema.ROUTINES
         WHERE ROUTINE_SCHEMA = %s ORDER BY ROUTINE_TYPE, ROUTINE_NAME""", (DB,))
    views = q(cur, """SELECT TABLE_NAME FROM information_schema.VIEWS WHERE TABLE_SCHEMA = %s
                      ORDER BY TABLE_NAME""", (DB,))
    triggers = q(cur, """
        SELECT TRIGGER_NAME, EVENT_MANIPULATION, EVENT_OBJECT_TABLE, ACTION_TIMING
          FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = %s ORDER BY TRIGGER_NAME""", (DB,))
    events = q(cur, """SELECT EVENT_NAME, INTERVAL_VALUE, INTERVAL_FIELD, EVENT_COMMENT
                         FROM information_schema.EVENTS WHERE EVENT_SCHEMA = %s""", (DB,))
    return tables, columns, constraints, indexes, routines, views, triggers, events


def key_marks(table, col, constraints):
    marks = []
    for c in constraints[table]:
        cols = (c["cols"] or "").split(",")
        if col not in cols:
            continue
        if c["CONSTRAINT_TYPE"] == "PRIMARY KEY":
            marks.append("PK")
        elif c["CONSTRAINT_TYPE"] == "FOREIGN KEY":
            marks.append("FK")
        elif c["CONSTRAINT_TYPE"] == "UNIQUE":
            marks.append("UK")
    return ", ".join(dict.fromkeys(marks))


def check_constraints_for(table, col, constraints):
    return [c["CONSTRAINT_NAME"] for c in constraints[table]
            if c["CONSTRAINT_TYPE"] == "CHECK" and re.search(rf"`{col}`", c["check_clause"] or "")]


def fix_mojibake(text):
    """information_schema 의 CHECK 절은 한글이 latin-1 로 이중 인코딩되어 나온다 → UTF-8 로 복원"""
    try:
        return text.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


def clean_check(clause):
    s = fix_mojibake(clause or "").replace("`", "")
    s = re.sub(r"_utf8mb4\\?'", "'", s).replace("\\'", "'")
    return s


def md_escape(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def gen_table_spec(tables, columns, constraints, indexes):
    out = ["# 11. 테이블 기술서", "",
           "> 이 문서는 `scripts/gen_docs.py` 가 실제 DB(information_schema)에서 생성했다. "
           "컬럼 설명은 DDL 의 COMMENT, 제약조건·인덱스는 DB 에 정의된 그대로이다.", ""]
    out += ["| No | 테이블명 | 한글명 | 컬럼 수 | 설명 |", "|---|---|---|---|---|"]
    for n, t in enumerate(TABLE_ORDER, 1):
        out.append(f"| {n} | `{t}` | {tables[t]['TABLE_COMMENT']} | {len(columns[t])} | "
                   f"{TABLE_NOTES.get(t, '')} |")
    for n, t in enumerate(TABLE_ORDER, 1):
        out += ["", f"## 11.{n} {tables[t]['TABLE_COMMENT']} (`{t.upper()}`)", ""]
        if TABLE_NOTES.get(t):
            out += [TABLE_NOTES[t], ""]
        out += ["| No | 컬럼명 | 속성명 | 데이터 타입 | NULL | 키 | 기본값 | 도메인 | 설명·제약 |",
                "|---|---|---|---|---|---|---|---|---|"]
        for c in columns[t]:
            name, note = split_comment(c["COLUMN_COMMENT"])
            default = c["COLUMN_DEFAULT"]
            if c["EXTRA"] and "auto_increment" in c["EXTRA"]:
                default = "AUTO_INCREMENT"
            elif c["GENERATION_EXPRESSION"]:
                default = "생성 컬럼"
                note = (note + " / " if note else "") + "식: " + clean_check(c["GENERATION_EXPRESSION"])
            elif default is not None:
                default = re.sub(r"^_utf8mb4\\?'|\\?'$", "", str(default)).replace("curdate()", "CURRENT_DATE")
            checks = check_constraints_for(t, c["COLUMN_NAME"], constraints)
            extra = ", ".join(f"`{x}`" for x in checks)
            desc = " / ".join(x for x in (note, extra) if x)
            out.append(
                f"| {c['ORDINAL_POSITION']} | `{c['COLUMN_NAME']}` | {name} | {c['COLUMN_TYPE'].upper()} | "
                f"{'Y' if c['IS_NULLABLE'] == 'YES' else 'N'} | {key_marks(t, c['COLUMN_NAME'], constraints)} | "
                f"{md_escape(default) if default is not None else ''} | {column_domain(t, c['COLUMN_NAME']) or ''} | "
                f"{md_escape(desc)} |")
        out += ["", "**제약조건**", "", "| 제약조건명 | 유형 | 대상 컬럼 | 내용 |", "|---|---|---|---|"]
        for c in constraints[t]:
            ctype = c["CONSTRAINT_TYPE"]
            if ctype == "FOREIGN KEY":
                body = (f"→ `{c['ref_table']}({c['ref_cols']})` "
                        f"ON UPDATE {c['on_update']} / ON DELETE {c['on_delete']}")
            elif ctype == "CHECK":
                body = f"`{md_escape(clean_check(c['check_clause']))}`"
            else:
                body = ""
            cols = c["cols"] or ", ".join(
                col["COLUMN_NAME"] for col in columns[t] if f"`{col['COLUMN_NAME']}`" in (c["check_clause"] or ""))
            out.append(f"| `{c['CONSTRAINT_NAME']}` | {ctype} | {cols} | {body} |")
        out += ["", "**인덱스**", "", "| 인덱스명 | 컬럼 | 고유 |", "|---|---|---|"]
        for i in indexes[t]:
            out.append(f"| `{i['INDEX_NAME']}` | {i['cols']} | {'N' if i['NON_UNIQUE'] else 'Y'} |")
    return "\n".join(out) + "\n"


def gen_domains(columns):
    used = defaultdict(list)
    for t in TABLE_ORDER:
        for c in columns[t]:
            d = column_domain(t, c["COLUMN_NAME"])
            used[d].append(f"{t}.{c['COLUMN_NAME']}")
    out = ["# 10. 도메인 정의서", "",
           "> 같은 의미의 컬럼은 같은 도메인(데이터 타입·길이·허용값)을 쓴다. "
           "'적용 컬럼'은 `scripts/gen_docs.py` 가 실제 DB 컬럼과 대조해 생성했다.", "",
           "| No | 도메인명 | 데이터 타입 | 허용값·형식 | 설명 | 적용 컬럼 수 | 적용 컬럼 |",
           "|---|---|---|---|---|---|---|"]
    for n, (d, (dtype, allowed, desc)) in enumerate(DOMAINS.items(), 1):
        cols = used.get(d, [])
        out.append(f"| {n} | {d} | {dtype} | {md_escape(allowed)} | {desc} | {len(cols)} | "
                   f"{', '.join(f'`{c}`' for c in cols)} |")
    return "\n".join(out) + "\n"


def gen_terms(columns):
    out = ["# 09. 용어 사전", "",
           "> 표준 단어를 먼저 정하고, 모든 테이블·컬럼명은 표준 단어의 조합으로 만든다. "
           "`scripts/gen_docs.py` 가 실제 DB 의 모든 컬럼명이 표준 단어로만 이루어졌는지 검사한다.", "",
           "## 9.1 표준 단어", "", "| No | 표준 단어 | 영문 약어 | 영문명 | 정의 |", "|---|---|---|---|---|"]
    for n, (abbr, ko, en, desc) in enumerate(sorted(WORDS, key=lambda w: w[1]), 1):
        out.append(f"| {n} | {ko} | `{abbr}` | {en} | {desc} |")
    out += ["", "## 9.2 표준 용어 (속성)", "",
            "| No | 표준 용어 (속성명) | 영문 컬럼명 | 구성 단어 | 도메인 | 사용 테이블 |",
            "|---|---|---|---|---|---|"]
    terms = {}
    for t in TABLE_ORDER:
        for c in columns[t]:
            name, _ = split_comment(c["COLUMN_COMMENT"])
            key = (name, c["COLUMN_NAME"])
            terms.setdefault(key, {"tables": [], "domain": column_domain(t, c["COLUMN_NAME"])})
            terms[key]["tables"].append(t)
    for n, ((name, col), info) in enumerate(sorted(terms.items(), key=lambda kv: kv[0][0]), 1):
        parts = " + ".join(WORD_MAP[w][1] for w in col.split("_") if w in WORD_MAP)
        out.append(f"| {n} | {name} | `{col}` | {parts} | {info['domain']} | "
                   f"{', '.join(f'`{t}`' for t in info['tables'])} |")
    out += ["", "## 9.3 업무 용어", "", "| No | 용어 | 정의 |", "|---|---|---|"]
    for n, (term, desc) in enumerate(BUSINESS_TERMS, 1):
        out.append(f"| {n} | {term} | {desc} |")
    return "\n".join(out) + "\n"


def gen_physical_lists(constraints, indexes, routines, views, triggers, events):
    out = ["<!-- 이 블록은 scripts/gen_docs.py 가 생성한다 -->", "", "### 제약조건 전체 목록", "",
           "| 테이블 | 제약조건명 | 유형 | 컬럼 | 내용 |", "|---|---|---|---|---|"]
    counts = defaultdict(int)
    for t in TABLE_ORDER:
        for c in constraints[t]:
            counts[c["CONSTRAINT_TYPE"]] += 1
            body = (f"→ {c['ref_table']}({c['ref_cols']})" if c["CONSTRAINT_TYPE"] == "FOREIGN KEY"
                    else f"`{md_escape(clean_check(c['check_clause']))}`" if c["CONSTRAINT_TYPE"] == "CHECK" else "")
            out.append(f"| `{t}` | `{c['CONSTRAINT_NAME']}` | {c['CONSTRAINT_TYPE']} | {c['cols'] or ''} | {body} |")
    out += ["", "제약조건 수: " + ", ".join(f"{k} {v}개" for k, v in counts.items()), "",
            "### 인덱스 전체 목록", "", "| 테이블 | 인덱스명 | 컬럼 | 고유 |", "|---|---|---|---|"]
    for t in TABLE_ORDER:
        for i in indexes[t]:
            out.append(f"| `{t}` | `{i['INDEX_NAME']}` | {i['cols']} | {'N' if i['NON_UNIQUE'] else 'Y'} |")
    out += ["", "### 뷰 · 함수 · 프로시저 · 트리거 · 이벤트", "", "| 종류 | 이름 | 설명 |", "|---|---|---|"]
    for v in views:
        out.append(f"| VIEW | `{v['TABLE_NAME']}` | {PROGRAM_NOTES.get(v['TABLE_NAME'], '')} |")
    for r in routines:
        out.append(f"| {r['ROUTINE_TYPE']} | `{r['ROUTINE_NAME']}` | {r['ROUTINE_COMMENT']} |")
    for tr in triggers:
        out.append(f"| TRIGGER | `{tr['TRIGGER_NAME']}` | {tr['ACTION_TIMING']} {tr['EVENT_MANIPULATION']} ON "
                   f"`{tr['EVENT_OBJECT_TABLE']}` — {PROGRAM_NOTES.get(tr['TRIGGER_NAME'], '')} |")
    for e in events:
        out.append(f"| EVENT | `{e['EVENT_NAME']}` | 매 {e['INTERVAL_VALUE']} {e['INTERVAL_FIELD']} — {e['EVENT_COMMENT']} |")
    out.append("<!-- /generated -->")
    return "\n".join(out) + "\n"


TABLE_NOTES = {
    "member_type": "학부생·대학원생·교직원 등 신분별 대출 정책 (숭실대학교 중앙도서관 대출 규정). 정책이 바뀌면 이 테이블만 수정한다.",
    "member": "도서관 회원. 학번·교번으로 회원 포털에 로그인한다. 대출정지 여부는 저장하지 않고 `suspension` 에서 계산한다.",
    "staff": "관리 프로그램을 사용하는 사서 계정.",
    "category": "한국십진분류법(KDC) 주류 10개.",
    "publisher": "출판사. 도서 등록 시 없으면 자동 등록된다.",
    "author": "저자. 동명이인이 있을 수 있어 이름은 UNIQUE 가 아니다.",
    "book": "ISBN 단위 서지정보. 실제 도서 100종(data/books.csv, 출처 검증) — 국립중앙도서관 API 키 발급 후 API 로 갱신.",
    "book_author": "도서와 저자의 M:N 관계를 해소하는 교차 테이블 (공저·번역).",
    "book_copy": "같은 도서의 실물 책 1권. 대출은 복본 단위로 이루어진다.",
    "loan": "대출 1건. 반납·분실 처리 시 return_date 가 기록된다.",
    "renewal": "연장 1회의 이력. 연장 횟수는 이 테이블의 행 수로 계산한다.",
    "fine": "연체 반납 시 부과되는 연체료 (대출 1건당 최대 1건). 연체일수는 휴관일을 뺀다.",
    "suspension": "사서가 기간을 정해 적용하는 대출정지(이용 제재)와 해제 이력. 연체 중 대출 금지는 미반납 연체 대출로 판단한다.",
    "closed_day": "휴관일(일요일·법정공휴일 등). 반납예정일이 휴관일이면 다음 개관일로 미루고, 연체일수에서 뺀다.",
}

PROGRAM_NOTES = {
    "v_book_summary": "도서별 저자 표기, 소장·대출가능 복본 수",
    "v_loan_detail": "대출 상세 + 대출상태(대출중/연체/반납/분실), 연체일수, 연장횟수 계산",
    "v_member_status": "회원별 대출 중 권수, 연체 권수, 미납 연체료, 대출정지 종료일, 대출가능 여부",
    "trg_member_withdraw_check": "탈퇴 시 미반납 도서·미납 연체료가 있으면 거부, 탈퇴일 자동 기록",
    "trg_book_copy_status_guard": "대출 중인 복본은 분실·폐기·대출가능으로 수동 변경 불가, 제적일 자동 기록",
}

BUSINESS_TERMS = [
    ("도서", "ISBN 으로 구별되는 책의 종류(서지). 같은 도서를 여러 권 소장할 수 있다."),
    ("도서복본", "같은 도서의 실물 책 1권. 등록번호(바코드)로 구별한다."),
    ("등록번호", "도서관이 복본마다 붙이는 고유 번호 (예: EM000001)."),
    ("청구기호", "서가에서 책을 찾기 위한 기호. 분류기호 + 저자기호 (+ 복본기호 c.2)."),
    ("대출", "회원이 복본을 정해진 기간 동안 빌려 가는 것."),
    ("반납예정일", "대출일 + 대출기간. 휴관일이면 다음 개관일로 미뤄진다."),
    ("연장", "반납예정일을 '연장한 날 + 대출기간'으로 다시 정하는 것. 회원구분별 최대 횟수까지, 대출 당일·연체·정지·미납 시 불가."),
    ("연체", "반납예정일이 지났는데 반납하지 않은 상태. 연체 도서가 있으면 추가 대출·연장이 막힌다."),
    ("연체일수", "반납예정일 다음 날부터 반납일까지의 일수에서 휴관일을 뺀 값."),
    ("연체료", "연체일수 × 1권 1일 연체료(100원). 반납(또는 분실 처리)할 때 확정되어 부과된다."),
    ("대출정지", "사서가 기간을 정해 적용하는 대출 제재(장기연체·자료훼손·규정위반 등). 연체 중 대출 불가는 이와 별개로 자동 적용된다."),
    ("휴관일", "도서관이 문을 닫는 날 (공휴일·개교기념일 등)."),
    ("분실 처리", "대출 중인 책을 회원이 잃어버린 경우 대출을 종료하고 복본을 '분실'로 바꾸는 것."),
    ("폐기", "훼손·노후 등으로 복본을 장서에서 제외하는 것."),
    ("회원 포털", "회원이 학번으로 로그인해 본인 대출 내역 조회·연장 신청을 하는 화면."),
    ("KDC", "한국십진분류법. 000 총류 ~ 900 역사의 10개 주류로 나눈다."),
]


def check(columns):
    problems = []
    for t in TABLE_ORDER:
        for c in columns[t]:
            col = c["COLUMN_NAME"]
            if not column_domain(t, col):
                problems.append(f"도메인 미지정: {t}.{col}")
            for w in col.split("_"):
                if w not in WORD_MAP:
                    problems.append(f"표준 단어 없음: '{w}' ({t}.{col})")
            if not c["COLUMN_COMMENT"]:
                problems.append(f"COMMENT 없음: {t}.{col}")
    for t in TABLE_ORDER:
        for w in t.split("_"):
            if w not in WORD_MAP:
                problems.append(f"표준 단어 없음: '{w}' (테이블 {t})")
    return problems


def main():
    with connect() as conn, conn.cursor() as cur:
        tables, columns, constraints, indexes, routines, views, triggers, events = load(cur)
    missing = [t for t in TABLE_ORDER if t not in tables]
    if missing:
        sys.exit(f"DB 에 없는 테이블: {missing}")
    problems = check(columns)
    for p in problems:
        print("[검사]", p)
    DOCS.mkdir(exist_ok=True)
    (DOCS / "11_테이블_기술서.md").write_text(gen_table_spec(tables, columns, constraints, indexes), encoding="utf-8", newline="\n")
    (DOCS / "10_도메인_정의서.md").write_text(gen_domains(columns), encoding="utf-8", newline="\n")
    (DOCS / "09_용어_사전.md").write_text(gen_terms(columns), encoding="utf-8", newline="\n")
    (DOCS / "_generated_physical_lists.md").write_text(
        gen_physical_lists(constraints, indexes, routines, views, triggers, events), encoding="utf-8", newline="\n")
    print(f"생성 완료: docs/09, 10, 11, _generated_physical_lists.md  (검사 경고 {len(problems)}건)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()

<!-- 이 블록은 scripts/gen_docs.py 가 생성한다 -->

### 제약조건 전체 목록

| 테이블 | 제약조건명 | 유형 | 컬럼 | 내용 |
|---|---|---|---|---|
| `member_type` | `PRIMARY` | PRIMARY KEY | type_code |  |
| `member_type` | `uq_member_type_name` | UNIQUE | type_name |  |
| `member_type` | `ck_member_type_days` | CHECK |  | `(loan_days between 1 and 180)` |
| `member_type` | `ck_member_type_max_loan` | CHECK |  | `(max_loan_count between 1 and 100)` |
| `member_type` | `ck_member_type_renew` | CHECK |  | `(max_renew <= 10)` |
| `member` | `PRIMARY` | PRIMARY KEY | member_id |  |
| `member` | `uq_member_email` | UNIQUE | email |  |
| `member` | `uq_member_no` | UNIQUE | member_no |  |
| `member` | `uq_member_phone` | UNIQUE | phone |  |
| `member` | `fk_member_type` | FOREIGN KEY | type_code | → member_type(type_code) |
| `member` | `ck_member_no` | CHECK |  | `regexp_like(member_no,'^[0-9A-Za-z]{4,20}$')` |
| `member` | `ck_member_phone` | CHECK |  | `regexp_like(phone,'^01[0-9]-[0-9]{3,4}-[0-9]{4}$')` |
| `member` | `ck_member_status` | CHECK |  | `(status in ('정상','탈퇴'))` |
| `member` | `ck_member_withdraw` | CHECK |  | `((status = '탈퇴') = (withdraw_date is not null))` |
| `staff` | `PRIMARY` | PRIMARY KEY | staff_id |  |
| `staff` | `uq_staff_login` | UNIQUE | login_id |  |
| `staff` | `ck_staff_role` | CHECK |  | `(role in ('관리자','사서'))` |
| `category` | `PRIMARY` | PRIMARY KEY | category_code |  |
| `category` | `uq_category_name` | UNIQUE | category_name |  |
| `category` | `ck_category_code` | CHECK |  | `regexp_like(category_code,'^[0-9]00$')` |
| `publisher` | `PRIMARY` | PRIMARY KEY | publisher_id |  |
| `publisher` | `uq_publisher_name` | UNIQUE | publisher_name |  |
| `author` | `PRIMARY` | PRIMARY KEY | author_id |  |
| `book` | `PRIMARY` | PRIMARY KEY | isbn |  |
| `book` | `fk_book_category` | FOREIGN KEY | category_code | → category(category_code) |
| `book` | `fk_book_publisher` | FOREIGN KEY | publisher_id | → publisher(publisher_id) |
| `book` | `ck_book_isbn` | CHECK |  | `regexp_like(isbn,'^97[89][0-9]{10}$')` |
| `book` | `ck_book_pub_year` | CHECK |  | `(pub_year between 1450 and 2100)` |
| `book_author` | `PRIMARY` | PRIMARY KEY | isbn,author_id |  |
| `book_author` | `fk_book_author_auth` | FOREIGN KEY | author_id | → author(author_id) |
| `book_author` | `fk_book_author_book` | FOREIGN KEY | isbn | → book(isbn) |
| `book_author` | `ck_book_author_role` | CHECK |  | `(author_role in ('지은이','옮긴이','엮은이','그림'))` |
| `book_copy` | `PRIMARY` | PRIMARY KEY | copy_id |  |
| `book_copy` | `uq_book_copy_reg_no` | UNIQUE | reg_no |  |
| `book_copy` | `fk_book_copy_book` | FOREIGN KEY | isbn | → book(isbn) |
| `book_copy` | `ck_book_copy_reg_no` | CHECK |  | `regexp_like(reg_no,'^EM[0-9]{6}$')` |
| `book_copy` | `ck_book_copy_removed` | CHECK |  | `((status in ('분실','폐기')) = (removed_date is not null))` |
| `book_copy` | `ck_book_copy_status` | CHECK |  | `(status in ('대출가능','대출중','분실','폐기'))` |
| `loan` | `PRIMARY` | PRIMARY KEY | loan_id |  |
| `loan` | `uq_loan_active_copy` | UNIQUE | active_copy_id |  |
| `loan` | `fk_loan_copy` | FOREIGN KEY | copy_id | → book_copy(copy_id) |
| `loan` | `fk_loan_member` | FOREIGN KEY | member_id | → member(member_id) |
| `loan` | `fk_loan_return_staff` | FOREIGN KEY | return_staff_id | → staff(staff_id) |
| `loan` | `fk_loan_staff` | FOREIGN KEY | staff_id | → staff(staff_id) |
| `loan` | `ck_loan_due_date` | CHECK |  | `(due_date >= cast(loan_date as date))` |
| `loan` | `ck_loan_return_date` | CHECK |  | `((return_date is null) or (return_date >= loan_date))` |
| `loan` | `ck_loan_return_type` | CHECK |  | `(return_type in ('반납','분실'))` |
| `loan` | `ck_loan_returned` | CHECK |  | `(((return_date is null) = (return_type is null)) and ((return_date is null) = (return_staff_id is null)))` |
| `renewal` | `PRIMARY` | PRIMARY KEY | renewal_id |  |
| `renewal` | `fk_renewal_loan` | FOREIGN KEY | loan_id | → loan(loan_id) |
| `renewal` | `fk_renewal_staff` | FOREIGN KEY | staff_id | → staff(staff_id) |
| `renewal` | `ck_renewal_channel` | CHECK |  | `(channel in ('홈페이지','사서'))` |
| `renewal` | `ck_renewal_due` | CHECK |  | `(new_due_date > prev_due_date)` |
| `renewal` | `ck_renewal_staff` | CHECK |  | `((channel = '사서') = (staff_id is not null))` |
| `fine` | `PRIMARY` | PRIMARY KEY | fine_id |  |
| `fine` | `uq_fine_loan` | UNIQUE | loan_id |  |
| `fine` | `fk_fine_loan` | FOREIGN KEY | loan_id | → loan(loan_id) |
| `fine` | `fk_fine_staff` | FOREIGN KEY | staff_id | → staff(staff_id) |
| `fine` | `ck_fine_days` | CHECK |  | `(overdue_days > 0)` |
| `fine` | `ck_fine_paid` | CHECK |  | `((status = '미납') = (paid_date is null))` |
| `fine` | `ck_fine_status` | CHECK |  | `(status in ('미납','납부','면제'))` |
| `suspension` | `PRIMARY` | PRIMARY KEY | suspension_id |  |
| `suspension` | `fk_suspension_loan` | FOREIGN KEY | loan_id | → loan(loan_id) |
| `suspension` | `fk_suspension_member` | FOREIGN KEY | member_id | → member(member_id) |
| `suspension` | `fk_suspension_released` | FOREIGN KEY | released_staff_id | → staff(staff_id) |
| `suspension` | `fk_suspension_staff` | FOREIGN KEY | staff_id | → staff(staff_id) |
| `suspension` | `ck_suspension_period` | CHECK |  | `(end_date >= start_date)` |
| `suspension` | `ck_suspension_reason` | CHECK |  | `(reason in ('장기연체','자료훼손','규정위반','기타'))` |
| `suspension` | `ck_suspension_release` | CHECK |  | `((released_date is null) = (released_staff_id is null))` |
| `closed_day` | `PRIMARY` | PRIMARY KEY | closed_date |  |

제약조건 수: PRIMARY KEY 14개, UNIQUE 10개, CHECK 28개, FOREIGN KEY 18개

### 인덱스 전체 목록

| 테이블 | 인덱스명 | 컬럼 | 고유 |
|---|---|---|---|
| `member_type` | `PRIMARY` | type_code | Y |
| `member_type` | `uq_member_type_name` | type_name | Y |
| `member` | `fk_member_type` | type_code | N |
| `member` | `idx_member_name` | name | N |
| `member` | `PRIMARY` | member_id | Y |
| `member` | `uq_member_email` | email | Y |
| `member` | `uq_member_no` | member_no | Y |
| `member` | `uq_member_phone` | phone | Y |
| `staff` | `PRIMARY` | staff_id | Y |
| `staff` | `uq_staff_login` | login_id | Y |
| `category` | `PRIMARY` | category_code | Y |
| `category` | `uq_category_name` | category_name | Y |
| `publisher` | `PRIMARY` | publisher_id | Y |
| `publisher` | `uq_publisher_name` | publisher_name | Y |
| `author` | `idx_author_name` | author_name | N |
| `author` | `PRIMARY` | author_id | Y |
| `book` | `fk_book_category` | category_code | N |
| `book` | `fk_book_publisher` | publisher_id | N |
| `book` | `idx_book_title` | title | N |
| `book` | `PRIMARY` | isbn | Y |
| `book_author` | `fk_book_author_auth` | author_id | N |
| `book_author` | `PRIMARY` | isbn,author_id | Y |
| `book_copy` | `idx_book_copy_isbn_status` | isbn,status | N |
| `book_copy` | `PRIMARY` | copy_id | Y |
| `book_copy` | `uq_book_copy_reg_no` | reg_no | Y |
| `loan` | `fk_loan_copy` | copy_id | N |
| `loan` | `fk_loan_return_staff` | return_staff_id | N |
| `loan` | `fk_loan_staff` | staff_id | N |
| `loan` | `idx_loan_due_date` | due_date | N |
| `loan` | `idx_loan_loan_date` | loan_date | N |
| `loan` | `idx_loan_member_return` | member_id,return_date | N |
| `loan` | `PRIMARY` | loan_id | Y |
| `loan` | `uq_loan_active_copy` | active_copy_id | Y |
| `renewal` | `fk_renewal_staff` | staff_id | N |
| `renewal` | `idx_renewal_loan` | loan_id | N |
| `renewal` | `PRIMARY` | renewal_id | Y |
| `fine` | `fk_fine_staff` | staff_id | N |
| `fine` | `idx_fine_status` | status | N |
| `fine` | `PRIMARY` | fine_id | Y |
| `fine` | `uq_fine_loan` | loan_id | Y |
| `suspension` | `fk_suspension_loan` | loan_id | N |
| `suspension` | `fk_suspension_released` | released_staff_id | N |
| `suspension` | `fk_suspension_staff` | staff_id | N |
| `suspension` | `idx_suspension_member_end` | member_id,end_date | N |
| `suspension` | `PRIMARY` | suspension_id | Y |
| `closed_day` | `PRIMARY` | closed_date | Y |

### 뷰 · 함수 · 프로시저 · 트리거 · 이벤트

| 종류 | 이름 | 설명 |
|---|---|---|
| VIEW | `v_book_summary` | 도서별 저자 표기, 소장·대출가능 복본 수 |
| VIEW | `v_loan_detail` | 대출 상세 + 대출상태(대출중/연체/반납/분실), 연체일수, 연장횟수 계산 |
| VIEW | `v_member_status` | 회원별 대출 중 권수, 연체 권수, 미납 연체료, 대출정지 종료일, 대출가능 여부 |
| FUNCTION | `fn_compensation` | 분실·훼손 변상금 기준액 = 정가 × 발행 경과연수별 배율 (규정 제26조). 정가·발행연도를 모르면 NULL (사서가 결정) |
| FUNCTION | `fn_next_open_day` | 주어진 날이 휴관일이면 다음 개관일을 돌려준다 |
| FUNCTION | `fn_overdue_days` | 반납예정일 다음 날부터 기준일까지의 연체일수 (휴관일 제외) |
| PROCEDURE | `sp_add_closed_day` | 휴관일 등록 + 해당일 반납예정 대출의 반납예정일 재계산 |
| PROCEDURE | `sp_borrow` | 대출 처리 (대출 가능 여부 검사 포함) |
| PROCEDURE | `sp_release_suspension` | 대출정지 해제 (사서) |
| PROCEDURE | `sp_renew` | 대출 연장 (홈페이지·사서) |
| PROCEDURE | `sp_report_lost` | 대출 중 분실 처리 (연체료 부과, 변상금 기준액 계산) |
| PROCEDURE | `sp_return` | 반납 처리 (연체일수 계산·연체료 부과 포함) |
| PROCEDURE | `sp_settle_fine` | 연체료 납부·면제 처리 |
| PROCEDURE | `sp_suspend_member` | 대출정지 적용 (사서) |
<!-- /generated -->

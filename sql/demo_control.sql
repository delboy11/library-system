-- =====================================================================
-- 시연용 데이터 제어 스크립트 (DB 관리자 계정으로 DB 서버에 접속해 실행)
--   접속 : MySQL Workbench → Hostname 100.77.2.39 · Port 3306 · Username root
--          또는  mysql -h 100.77.2.39 -u root -p --default-character-set=utf8mb4 library_db
--   사용 : 문장을 하나씩 실행한다 (Workbench: 커서를 문장에 두고 Ctrl+Enter).
--          @변수는 같은 접속(세션) 안에서만 유지되므로 한 창에서 위에서부터 차례로 실행한다.
--          SQL 로 바꾼 상태는 웹 화면을 새로고침하면 바로 보인다 (웹 서버와 같은 DB 서버를 쓰므로).
--   복구 : 각 절의 '되돌리기' 또는 전체 초기화  ssh delboy@100.77.2.39 '~/library-system/deploy/db-server/init.sh'
--   ※ 앱 계정(library)의 권한 검증은 sql/demo_app_account.sql
-- =====================================================================
USE library_db;


-- ---------------------------------------------------------------------
-- 0. 분리 확인 : 여기는 DB 서버(다른 PC)이고, 웹 서버는 네트워크로 접속해 있다
-- ---------------------------------------------------------------------
SELECT @@hostname AS db_server, @@version AS mysql_version, @@bind_address AS listen_on,
       @@time_zone AS time_zone, NOW() AS db_now;

-- 웹 서버(Flask)의 연결 : host 열이 웹 서버 PC 의 IP (예: 100.113.213.25:5xxxx)
SELECT user, host AS client_address, db, command, time
  FROM information_schema.PROCESSLIST
 WHERE user = 'library'
 ORDER BY host;


-- ---------------------------------------------------------------------
-- 1. 시연 회원 상태 (v_member_status 가 조회 시점에 계산)
-- ---------------------------------------------------------------------
SELECT member_no, name, type_name, active_loans, max_loan_count, overdue_loans, unpaid_fine, suspend_until, loan_state
  FROM v_member_status
 WHERE member_no IN ('20231234','20221057','20211388','20241102','20232245','20214410','20193321','20257001')
 ORDER BY member_id;


-- ---------------------------------------------------------------------
-- 2. 데이터 상태 변경 → 웹 화면에 바로 반영
-- ---------------------------------------------------------------------

-- 2-1. 연체 상황 만들기 : 김민준(20231234)의 가장 오래된 대출을 사흘 전 반납예정으로
SET @member_no = '20231234';
SELECT l.loan_id, l.due_date INTO @loan_id, @orig_due
  FROM loan l JOIN member m ON m.member_id = l.member_id
 WHERE m.member_no = @member_no AND l.return_date IS NULL
 ORDER BY l.loan_date LIMIT 1;
SELECT @loan_id AS loan_id, @orig_due AS original_due_date;

UPDATE loan SET due_date = CURDATE() - INTERVAL 3 DAY WHERE loan_id = @loan_id;

SELECT member_no, name, overdue_loans, loan_state FROM v_member_status WHERE member_no = @member_no;
SELECT loan_id, title, due_date, loan_state, overdue_days FROM v_loan_detail WHERE loan_id = @loan_id;
-- (웹) 대출 화면에서 20231234 조회 → '대출 불가: 연체 도서 1권 반납 필요', 회원 포털 연장 → 연체라 거부

-- 되돌리기
UPDATE loan SET due_date = @orig_due WHERE loan_id = @loan_id;


-- 2-2. 대출 정책 바꾸기 : 학부생 대출 한도 10권 → 2권 (정책은 코드가 아니라 member_type 데이터)
UPDATE member_type SET max_loan_count = 2 WHERE type_code = 'UG';
SELECT member_no, name, active_loans, max_loan_count FROM v_member_status WHERE member_no = '20231234';
-- (웹) 20231234 대출 시도 → '대출 한도(2권)를 초과합니다. 현재 2권 대출 중입니다.'

-- 되돌리기
UPDATE member_type SET max_loan_count = 10 WHERE type_code = 'UG';


-- 2-3. 대출정지 적용·해제 : 웹과 같은 저장 프로시저를 SQL 로 호출 (staff_id 1 = admin)
SET @member_id = (SELECT member_id FROM member WHERE member_no = '20221057');
CALL sp_suspend_member(@member_id, '규정위반', 7, '시연용 정지', 1);
SELECT member_no, name, suspend_until, loan_state FROM v_member_status WHERE member_id = @member_id;

-- 되돌리기 (조기 해제 이력이 남는다)
SET @suspension_id = (SELECT MAX(suspension_id) FROM suspension WHERE member_id = @member_id);
CALL sp_release_suspension(@suspension_id, 1);


-- ---------------------------------------------------------------------
-- 3. 예외 상황 : 잘못된 데이터는 DB 가 거부한다 (모두 오류가 나는 것이 정상, 데이터는 바뀌지 않음)
-- ---------------------------------------------------------------------

-- 3-1. 같은 복본 이중 대출 → ERROR 1062 Duplicate entry … for key 'loan.uq_loan_active_copy'
--      (생성 컬럼 active_copy_id = 미반납이면 copy_id, 반납되면 NULL → UNIQUE)
SELECT copy_id INTO @busy_copy FROM loan WHERE return_date IS NULL ORDER BY loan_id LIMIT 1;
INSERT INTO loan (copy_id, member_id, staff_id, due_date)
VALUES (@busy_copy, 10001, 1, CURDATE() + INTERVAL 14 DAY);

-- 3-2. CHECK : ISBN 형식 → ERROR 3819 Check constraint 'ck_book_isbn' is violated
INSERT INTO book (isbn, title, publisher_id, category_code) VALUES ('1234567890123', '잘못된 ISBN', 1, '000');

-- 3-3. CHECK : 전화번호 형식 → ERROR 3819 'ck_member_phone'
UPDATE member SET phone = '01012345678' WHERE member_no = '20231234';

-- 3-4. CHECK : 반납일시 없이 반납구분만 → ERROR 3819 'ck_loan_returned'
UPDATE loan SET return_type = '반납' WHERE copy_id = @busy_copy AND return_date IS NULL;

-- 3-5. FOREIGN KEY : 없는 회원구분 → ERROR 1452 … fk_member_type
UPDATE member SET type_code = 'XX' WHERE member_no = '20231234';

-- 3-6. 트리거 : 대출 중인 복본 폐기 → ERROR 1644 '대출 중인 복본은 반납(또는 분실 처리) 후 상태를 변경할 수 있습니다.'
UPDATE book_copy SET status = '폐기' WHERE copy_id = @busy_copy;

-- 3-7. 트리거 : 미반납 도서가 있는 회원 탈퇴 → ERROR 1644 '반납하지 않은 도서가 있어 탈퇴 처리할 수 없습니다.'
UPDATE member SET status = '탈퇴' WHERE member_no = '20257001';

-- 3-8. 프로시저 : 연체 회원 대출 → ERROR 1644 '연체 중인 도서가 있어 대출할 수 없습니다. …'
CALL sp_borrow('20241102', 'EM000005', 1);

-- 3-9. 프로시저 : 연장 2회 다 쓴 대출 → ERROR 1644 '연장 가능 횟수(2회)를 모두 사용했습니다.'
SELECT loan_id INTO @used_up FROM v_loan_detail
 WHERE member_no = '20232245' AND return_date IS NULL AND renew_count = 2 LIMIT 1;
CALL sp_renew(@used_up, '사서', 1, NULL);

-- 3-10. 프로시저 : 회원 포털에서 남의 대출 연장 → ERROR 1644 '연장할 수 있는 대출이 아닙니다.'
CALL sp_renew(@used_up, '홈페이지', NULL, 10001);


-- ---------------------------------------------------------------------
-- 4. 권한 검증
-- ---------------------------------------------------------------------

-- 4-1. 앱 전용 계정의 권한 : library_db 의 DML + EXECUTE 뿐 (DDL·계정 관리 없음)
SHOW GRANTS FOR 'library'@'%';

-- 4-2. 앱 계정에서 프로시저 실행 권한을 빼면 → 웹의 대출·반납·연장이 바로 막힌다
REVOKE EXECUTE ON library_db.* FROM 'library'@'%';
-- (웹) 대출 시도 → '앱 DB 계정(library)에 프로시저 실행(EXECUTE) 권한이 없습니다.'
--      조회 화면(대출현황·회원·통계)은 그대로 열린다 (SELECT 권한은 있으므로)
--      → 업무 규칙은 DB 의 프로시저에 있고, 앱은 호출만 한다

-- 되돌리기
GRANT EXECUTE ON library_db.* TO 'library'@'%';

-- 4-3. 사서 역할(앱 수준 권한)도 데이터 : lib01 을 관리자로 → 다시 로그인하면 연체료 면제·휴관일 메뉴 사용 가능
SELECT login_id, name, role FROM staff;
UPDATE staff SET role = '관리자' WHERE login_id = 'lib01';

-- 되돌리기
UPDATE staff SET role = '사서' WHERE login_id = 'lib01';


-- ---------------------------------------------------------------------
-- 5. 끝난 뒤 확인 : 1장과 같은 결과면 원래 상태
-- ---------------------------------------------------------------------
SELECT member_no, name, active_loans, max_loan_count, overdue_loans, unpaid_fine, suspend_until, loan_state
  FROM v_member_status
 WHERE member_no IN ('20231234','20221057','20211388','20241102','20232245','20214410','20193321','20257001')
 ORDER BY member_id;

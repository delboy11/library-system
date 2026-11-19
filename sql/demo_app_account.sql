-- =====================================================================
-- 앱 전용 계정(library) 권한 검증 : 웹 서버가 쓰는 것과 같은 계정으로 DB 서버에 접속한다
--   한 번에 실행 : mysql -h 100.77.2.39 -u library -p --force -t --default-character-set=utf8mb4 library_db < sql/demo_app_account.sql
--                  (비밀번호 library1234, --force : 오류가 나도 다음 문장을 계속 실행)
--   Workbench   : Username library 로 접속해 문장을 하나씩 실행
--   기대 결과 : 조회·데이터 변경·프로시저 실행은 되고, 구조 변경·규칙 삭제·계정 관리는 모두 거부된다
-- =====================================================================

-- 누구로, 어디서 접속했나 (USER() 의 호스트 = 이 PC 의 IP)
SELECT CURRENT_USER() AS account, USER() AS connected_from, @@hostname AS db_server;
SHOW GRANTS;

-- 되는 것 ---------------------------------------------------------------
SELECT COUNT(*) AS loans, SUM(return_date IS NULL) AS on_loan FROM loan;      -- SELECT
SELECT member_no, loan_state FROM v_member_status WHERE member_no = '20241102'; -- 뷰
CALL sp_borrow('20241102', 'EM000005', 1);   -- EXECUTE 는 있지만 업무 규칙이 거부 → ERROR 1644 '연체 중인 도서가 …'

-- 안 되는 것 (모두 오류가 정상) ---------------------------------------------
DROP TABLE closed_day;                          -- ERROR 1142 DROP command denied
CREATE TABLE hack (id INT);                     -- ERROR 1142 CREATE command denied
ALTER TABLE member DROP COLUMN phone;           -- ERROR 1142 ALTER command denied
DROP TRIGGER trg_member_withdraw_check;         -- ERROR 1142 TRIGGER command denied : 앱이 뚫려도 규칙(트리거)은 못 지운다
DROP PROCEDURE sp_borrow;                       -- ERROR 1370 alter routine command denied
CREATE USER 'hacker'@'%' IDENTIFIED BY 'x';     -- ERROR 1227 Access denied; CREATE USER 권한 필요
GRANT SELECT ON library_db.* TO 'hacker'@'%';   -- ERROR 1044/1410 권한을 남에게 줄 수 없음
SELECT user, host FROM mysql.user;              -- ERROR 1142 SELECT command denied … table 'user'
DROP DATABASE library_db;                       -- ERROR 1044 Access denied

-- 트리거는 앱 계정의 직접 UPDATE 도 막는다 → ERROR 1644 '반납하지 않은 도서가 있어 탈퇴 처리할 수 없습니다.'
UPDATE member SET status = '탈퇴' WHERE member_no = '20257001';

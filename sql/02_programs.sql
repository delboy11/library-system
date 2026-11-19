-- =====================================================================
-- 함수 · 뷰 · 트리거 · 저장 프로시저  v2
-- 업무 규칙은 숭실대학교 중앙도서관 대출 규정을 따르며, DB 프로시저에서 일관되게 처리한다.
--   · 연체 중인 회원은 추가 대출·연장 불가 (규정 제24조)
--   · 연장은 "연장한 날부터 대출기간만큼", 대출 당일 연장 불가, 연체·제재 시 연장 불가
--   · 연체료 = 1권 1일 100원, 휴관일 제외
--   · 반납예정일이 휴관일이면 다음 개관일 (우리 팀 정책)
--   · 미납 연체료가 있으면 대출·연장 불가 (우리 팀 정책)
-- 실행 : mysql -u root --default-character-set=utf8mb4 < sql/02_programs.sql
-- =====================================================================
USE library_db;

DELIMITER $$

-- =====================================================================
-- 1. 함수
-- =====================================================================

DROP FUNCTION IF EXISTS fn_next_open_day $$
CREATE FUNCTION fn_next_open_day(p_date DATE) RETURNS DATE
READS SQL DATA
COMMENT '주어진 날이 휴관일이면 다음 개관일을 돌려준다'
BEGIN
  DECLARE v_date DATE DEFAULT p_date;
  WHILE EXISTS (SELECT 1 FROM closed_day WHERE closed_date = v_date) DO
    SET v_date = v_date + INTERVAL 1 DAY;
  END WHILE;
  RETURN v_date;
END $$


DROP FUNCTION IF EXISTS fn_overdue_days $$
CREATE FUNCTION fn_overdue_days(p_due_date DATE, p_until DATE) RETURNS INT
READS SQL DATA
COMMENT '반납예정일 다음 날부터 기준일까지의 연체일수 (휴관일 제외)'
BEGIN
  IF p_until IS NULL OR p_until <= p_due_date THEN
    RETURN 0;
  END IF;
  RETURN DATEDIFF(p_until, p_due_date)
       - (SELECT COUNT(*) FROM closed_day WHERE closed_date > p_due_date AND closed_date <= p_until);
END $$


DROP FUNCTION IF EXISTS fn_compensation $$
CREATE FUNCTION fn_compensation(p_isbn CHAR(13)) RETURNS INT
READS SQL DATA
COMMENT '분실·훼손 변상금 기준액 = 정가 × 발행 경과연수별 배율 (규정 제26조). 정가·발행연도를 모르면 NULL (사서가 결정)'
BEGIN
  DECLARE v_price INT;
  DECLARE v_age INT;
  -- pub_year 가 UNSIGNED 라 그대로 빼면 미래 연도에서 범위 오류가 나므로 SIGNED 로 변환
  SELECT price, GREATEST(0, YEAR(CURDATE()) - CAST(pub_year AS SIGNED)) INTO v_price, v_age FROM book WHERE isbn = p_isbn;
  IF v_price IS NULL OR v_age IS NULL THEN
    RETURN NULL;
  END IF;
  RETURN ROUND(v_price * CASE WHEN v_age < 4 THEN 1.2
                              WHEN v_age < 10 THEN 1.5
                              WHEN v_age < 20 THEN 2.0
                              ELSE 3.0 END);
END $$

DELIMITER ;


-- =====================================================================
-- 2. 뷰
-- =====================================================================

-- 도서 목록 : 저자 표기 + 이용 가능 복본 / 대출가능 복본 수
CREATE OR REPLACE VIEW v_book_summary AS
SELECT b.isbn, b.title, b.pub_year, b.price, b.kdc_no,
       b.category_code, c.category_name,
       b.publisher_id, p.publisher_name,
       (SELECT GROUP_CONCAT(CONCAT(a.author_name,
                                   IF(ba.author_role = '지은이', '', CONCAT(' (', ba.author_role, ')')))
                            ORDER BY ba.author_order SEPARATOR ', ')
          FROM book_author ba JOIN author a ON a.author_id = ba.author_id
         WHERE ba.isbn = b.isbn) AS authors,
       (SELECT COUNT(*) FROM book_copy bc
         WHERE bc.isbn = b.isbn AND bc.status IN ('대출가능', '대출중')) AS total_copies,
       (SELECT COUNT(*) FROM book_copy bc
         WHERE bc.isbn = b.isbn AND bc.status = '대출가능') AS available_copies
  FROM book b
  JOIN publisher p ON p.publisher_id = b.publisher_id
  JOIN category  c ON c.category_code = b.category_code;


-- 대출 상세 : 대출상태(대출중/연체/반납/분실), 연체일수(휴관일 제외), 연장횟수
CREATE OR REPLACE VIEW v_loan_detail AS
SELECT l.loan_id, l.member_id, m.member_no, m.name AS member_name, m.phone,
       l.copy_id, bc.reg_no, bc.call_no, b.isbn, b.title,
       l.loan_date, l.due_date, l.return_date, l.return_type,
       (SELECT COUNT(*) FROM renewal r WHERE r.loan_id = l.loan_id) AS renew_count,
       CASE WHEN l.return_type = '분실'      THEN '분실'
            WHEN l.return_date IS NOT NULL   THEN '반납'
            WHEN l.due_date < CURDATE()      THEN '연체'
            ELSE '대출중' END AS loan_state,
       fn_overdue_days(l.due_date, COALESCE(DATE(l.return_date), CURDATE())) AS overdue_days,
       s.name AS staff_name, rs.name AS return_staff_name
  FROM loan l
  JOIN member    m  ON m.member_id = l.member_id
  JOIN book_copy bc ON bc.copy_id  = l.copy_id
  JOIN book      b  ON b.isbn      = bc.isbn
  JOIN staff     s  ON s.staff_id  = l.staff_id
  LEFT JOIN staff rs ON rs.staff_id = l.return_staff_id;


-- 회원 현황 : 대출 중·연체 권수, 미납 연체료, 대출정지 종료일, 대출상태
--   대출상태 = 탈퇴 / 대출정지(대출정지 기간 중 · 연체 도서 보유 · 미납 연체료) / 대출가능
--   대출정지의 세 조건은 sp_borrow · sp_renew 가 대출·연장을 거부하는 조건과 같다
CREATE OR REPLACE VIEW v_member_status AS
SELECT x.member_id, x.member_no, x.name, x.type_code, t.type_name, x.department, x.phone, x.email,
       x.status, x.join_date, x.withdraw_date,
       t.max_loan_count, t.loan_days, t.max_renew, t.fine_per_day,
       x.active_loans, x.overdue_loans, x.unpaid_fine, x.suspend_until,
       CASE WHEN x.status = '탈퇴' THEN '탈퇴'
            WHEN x.suspend_until IS NOT NULL OR x.overdue_loans > 0 OR x.unpaid_fine > 0 THEN '대출정지'
            ELSE '대출가능' END AS loan_state
  FROM (SELECT m.*,
               (SELECT COUNT(*) FROM loan l
                 WHERE l.member_id = m.member_id AND l.return_date IS NULL) AS active_loans,
               (SELECT COUNT(*) FROM loan l
                 WHERE l.member_id = m.member_id AND l.return_date IS NULL
                   AND l.due_date < CURDATE()) AS overdue_loans,
               (SELECT COALESCE(SUM(f.amount), 0) FROM fine f JOIN loan l ON l.loan_id = f.loan_id
                 WHERE l.member_id = m.member_id AND f.status = '미납') AS unpaid_fine,
               (SELECT MAX(s.end_date) FROM suspension s
                 WHERE s.member_id = m.member_id AND s.released_date IS NULL
                   AND CURDATE() BETWEEN s.start_date AND s.end_date) AS suspend_until
          FROM member m) x
  JOIN member_type t ON t.type_code = x.type_code;


DELIMITER $$

-- =====================================================================
-- 3. 트리거
-- =====================================================================

-- 회원 탈퇴 : 미반납 도서나 미납 연체료가 있으면 거부하고, 탈퇴일을 자동 기록
DROP TRIGGER IF EXISTS trg_member_withdraw_check $$
CREATE TRIGGER trg_member_withdraw_check
BEFORE UPDATE ON member
FOR EACH ROW
BEGIN
  IF NEW.status = '탈퇴' AND OLD.status <> '탈퇴' THEN
    IF EXISTS (SELECT 1 FROM loan WHERE member_id = OLD.member_id AND return_date IS NULL) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '반납하지 않은 도서가 있어 탈퇴 처리할 수 없습니다.';
    END IF;
    IF EXISTS (SELECT 1 FROM fine f JOIN loan l ON l.loan_id = f.loan_id
                WHERE l.member_id = OLD.member_id AND f.status = '미납') THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '미납 연체료가 있어 탈퇴 처리할 수 없습니다.';
    END IF;
    SET NEW.withdraw_date = CURDATE();
  ELSEIF NEW.status = '정상' AND OLD.status = '탈퇴' THEN
    SET NEW.withdraw_date = NULL;
  END IF;
END $$


-- 복본 상태 보호 : 대출 중인 복본은 분실·폐기·대출가능으로 바꿀 수 없음. 분실·폐기일 자동 기록
DROP TRIGGER IF EXISTS trg_book_copy_status_guard $$
CREATE TRIGGER trg_book_copy_status_guard
BEFORE UPDATE ON book_copy
FOR EACH ROW
BEGIN
  IF NEW.status <> OLD.status THEN
    IF NEW.status IN ('대출가능', '분실', '폐기')
       AND EXISTS (SELECT 1 FROM loan WHERE copy_id = OLD.copy_id AND return_date IS NULL) THEN
      SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '대출 중인 복본은 반납(또는 분실 처리) 후 상태를 변경할 수 있습니다.';
    END IF;
    IF NEW.status IN ('분실', '폐기') THEN
      SET NEW.removed_date = CURDATE();
    ELSE
      SET NEW.removed_date = NULL;
    END IF;
  END IF;
END $$


-- =====================================================================
-- 4. 저장 프로시저
-- =====================================================================

-- 대출 : 대출 가능 여부 검사 → 대출 등록 → 복본 상태 '대출중'
DROP PROCEDURE IF EXISTS sp_borrow $$
CREATE PROCEDURE sp_borrow(IN p_member_no VARCHAR(20), IN p_reg_no VARCHAR(10), IN p_staff_id INT UNSIGNED)
COMMENT '대출 처리 (대출 가능 여부 검사 포함)'
BEGIN
  DECLARE v_member_id   INT UNSIGNED;
  DECLARE v_status      VARCHAR(10);
  DECLARE v_max_loan    TINYINT UNSIGNED;
  DECLARE v_loan_days   TINYINT UNSIGNED;
  DECLARE v_active      INT;
  DECLARE v_susp_end    DATE;
  DECLARE v_copy_id     INT UNSIGNED;
  DECLARE v_copy_status VARCHAR(10);
  DECLARE v_loan_id     INT UNSIGNED;
  DECLARE v_msg         VARCHAR(128);

  -- 같은 회원·같은 복본에 대한 동시 처리를 막기 위해 행 잠금
  SELECT m.member_id, m.status, t.max_loan_count, t.loan_days
    INTO v_member_id, v_status, v_max_loan, v_loan_days
    FROM member m JOIN member_type t ON t.type_code = m.type_code
   WHERE m.member_no = p_member_no
     FOR UPDATE OF m;

  IF v_member_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '존재하지 않는 학번(교번)입니다.';
  END IF;
  IF v_status = '탈퇴' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '탈퇴한 회원은 대출할 수 없습니다.';
  END IF;

  SELECT MAX(end_date) INTO v_susp_end FROM suspension
   WHERE member_id = v_member_id AND released_date IS NULL AND CURDATE() BETWEEN start_date AND end_date;
  IF v_susp_end IS NOT NULL THEN
    SET v_msg = CONCAT('대출정지 기간입니다. (', DATE_FORMAT(v_susp_end, '%Y-%m-%d'), '까지)');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;
  IF EXISTS (SELECT 1 FROM loan WHERE member_id = v_member_id AND return_date IS NULL AND due_date < CURDATE()) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '연체 중인 도서가 있어 대출할 수 없습니다. 연체 도서를 먼저 반납하세요.';
  END IF;
  IF EXISTS (SELECT 1 FROM fine f JOIN loan l ON l.loan_id = f.loan_id
              WHERE l.member_id = v_member_id AND f.status = '미납') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '미납 연체료가 있어 대출할 수 없습니다.';
  END IF;

  SELECT COUNT(*) INTO v_active FROM loan WHERE member_id = v_member_id AND return_date IS NULL;
  IF v_active >= v_max_loan THEN
    SET v_msg = CONCAT('대출 한도(', v_max_loan, '권)를 초과합니다. 현재 ', v_active, '권 대출 중입니다.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  SELECT copy_id, status INTO v_copy_id, v_copy_status FROM book_copy WHERE reg_no = p_reg_no FOR UPDATE;
  IF v_copy_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '존재하지 않는 등록번호입니다.';
  END IF;
  IF v_copy_status <> '대출가능' THEN
    SET v_msg = CONCAT('대출할 수 없는 복본입니다. (현재 상태: ', v_copy_status, ')');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  INSERT INTO loan (copy_id, member_id, staff_id, loan_date, due_date)
  VALUES (v_copy_id, v_member_id, p_staff_id, NOW(), fn_next_open_day(CURDATE() + INTERVAL v_loan_days DAY));
  SET v_loan_id = LAST_INSERT_ID();

  UPDATE book_copy SET status = '대출중' WHERE copy_id = v_copy_id;

  SELECT l.loan_id, l.due_date, b.title, m.name AS member_name
    FROM loan l
    JOIN book_copy bc ON bc.copy_id = l.copy_id
    JOIN book b       ON b.isbn = bc.isbn
    JOIN member m     ON m.member_id = l.member_id
   WHERE l.loan_id = v_loan_id;
END $$


-- 반납 : 반납 기록 → 연체일수 자동 계산(휴관일 제외) → 연체료 부과 → 복본 '대출가능'
DROP PROCEDURE IF EXISTS sp_return $$
CREATE PROCEDURE sp_return(IN p_reg_no VARCHAR(10), IN p_staff_id INT UNSIGNED)
COMMENT '반납 처리 (연체일수 계산·연체료 부과 포함)'
BEGIN
  DECLARE v_copy_id      INT UNSIGNED;
  DECLARE v_loan_id      INT UNSIGNED;
  DECLARE v_member_id    INT UNSIGNED;
  DECLARE v_due          DATE;
  DECLARE v_fine_per_day INT UNSIGNED;
  DECLARE v_overdue      INT DEFAULT 0;
  DECLARE v_fine         INT DEFAULT 0;

  SELECT copy_id INTO v_copy_id FROM book_copy WHERE reg_no = p_reg_no FOR UPDATE;
  IF v_copy_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '존재하지 않는 등록번호입니다.';
  END IF;

  SELECT l.loan_id, l.member_id, l.due_date, t.fine_per_day
    INTO v_loan_id, v_member_id, v_due, v_fine_per_day
    FROM loan l
    JOIN member m      ON m.member_id = l.member_id
    JOIN member_type t ON t.type_code = m.type_code
   WHERE l.copy_id = v_copy_id AND l.return_date IS NULL
     FOR UPDATE OF l;
  IF v_loan_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '대출 중인 복본이 아닙니다.';
  END IF;

  UPDATE loan SET return_date = NOW(), return_type = '반납', return_staff_id = p_staff_id
   WHERE loan_id = v_loan_id;

  SET v_overdue = fn_overdue_days(v_due, CURDATE());
  IF v_overdue > 0 THEN
    SET v_fine = v_overdue * v_fine_per_day;
    INSERT INTO fine (loan_id, overdue_days, amount) VALUES (v_loan_id, v_overdue, v_fine);
  END IF;

  UPDATE book_copy SET status = '대출가능' WHERE copy_id = v_copy_id;

  SELECT b.title, m.name AS member_name, v_overdue AS overdue_days, v_fine AS fine_amount
    FROM book_copy bc
    JOIN book b   ON b.isbn = bc.isbn
    JOIN member m ON m.member_id = v_member_id
   WHERE bc.copy_id = v_copy_id;
END $$


-- 연장 : 연장한 날부터 대출기간만큼 (휴관일이면 다음 개관일). 연장 이력 기록
--   p_channel = '홈페이지'(회원 포털, p_member_id 로 본인 확인) 또는 '사서'(p_staff_id 필수)
DROP PROCEDURE IF EXISTS sp_renew $$
CREATE PROCEDURE sp_renew(IN p_loan_id INT UNSIGNED, IN p_channel VARCHAR(10),
                          IN p_staff_id INT UNSIGNED, IN p_member_id INT UNSIGNED)
COMMENT '대출 연장 (홈페이지·사서)'
BEGIN
  DECLARE v_loan_id     INT UNSIGNED;
  DECLARE v_member_id   INT UNSIGNED;
  DECLARE v_loan_date   DATETIME;
  DECLARE v_due         DATE;
  DECLARE v_return_date DATETIME;
  DECLARE v_loan_days   TINYINT UNSIGNED;
  DECLARE v_max_renew   TINYINT UNSIGNED;
  DECLARE v_count       INT;
  DECLARE v_new_due     DATE;
  DECLARE v_msg         VARCHAR(128);

  SELECT l.loan_id, l.member_id, l.loan_date, l.due_date, l.return_date, t.loan_days, t.max_renew
    INTO v_loan_id, v_member_id, v_loan_date, v_due, v_return_date, v_loan_days, v_max_renew
    FROM loan l
    JOIN member m      ON m.member_id = l.member_id
    JOIN member_type t ON t.type_code = m.type_code
   WHERE l.loan_id = p_loan_id
     FOR UPDATE OF l;

  IF v_loan_id IS NULL OR (p_channel = '홈페이지' AND v_member_id <> p_member_id) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '연장할 수 있는 대출이 아닙니다.';
  END IF;
  IF v_return_date IS NOT NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '이미 반납된 대출입니다.';
  END IF;
  IF DATE(v_loan_date) = CURDATE() THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '대출 당일에는 연장할 수 없습니다.';
  END IF;
  IF EXISTS (SELECT 1 FROM loan WHERE member_id = v_member_id AND return_date IS NULL AND due_date < CURDATE()) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '연체 중인 도서가 있어 연장할 수 없습니다.';
  END IF;
  IF EXISTS (SELECT 1 FROM suspension WHERE member_id = v_member_id AND released_date IS NULL
                AND CURDATE() BETWEEN start_date AND end_date) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '대출정지 기간에는 연장할 수 없습니다.';
  END IF;
  IF EXISTS (SELECT 1 FROM fine f JOIN loan l ON l.loan_id = f.loan_id
              WHERE l.member_id = v_member_id AND f.status = '미납') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '미납 연체료가 있어 연장할 수 없습니다.';
  END IF;

  SELECT COUNT(*) INTO v_count FROM renewal WHERE loan_id = p_loan_id;
  IF v_count >= v_max_renew THEN
    SET v_msg = CONCAT('연장 가능 횟수(', v_max_renew, '회)를 모두 사용했습니다.');
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = v_msg;
  END IF;

  SET v_new_due = fn_next_open_day(CURDATE() + INTERVAL v_loan_days DAY);
  IF v_new_due <= v_due THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '지금 연장해도 반납예정일이 늦어지지 않습니다.';
  END IF;

  INSERT INTO renewal (loan_id, prev_due_date, new_due_date, channel, staff_id)
  VALUES (p_loan_id, v_due, v_new_due, p_channel, IF(p_channel = '사서', p_staff_id, NULL));
  UPDATE loan SET due_date = v_new_due WHERE loan_id = p_loan_id;

  SELECT l.loan_id, l.due_date, b.title, v_count + 1 AS renew_count
    FROM loan l
    JOIN book_copy bc ON bc.copy_id = l.copy_id
    JOIN book b       ON b.isbn = bc.isbn
   WHERE l.loan_id = p_loan_id;
END $$


-- 분실 처리 : 대출 종료(반납구분 '분실') → 연체분 연체료 부과 → 복본 '분실'. 변상금 기준액 안내
DROP PROCEDURE IF EXISTS sp_report_lost $$
CREATE PROCEDURE sp_report_lost(IN p_loan_id INT UNSIGNED, IN p_staff_id INT UNSIGNED)
COMMENT '대출 중 분실 처리 (연체료 부과, 변상금 기준액 계산)'
BEGIN
  DECLARE v_loan_id      INT UNSIGNED;
  DECLARE v_copy_id      INT UNSIGNED;
  DECLARE v_member_id    INT UNSIGNED;
  DECLARE v_due          DATE;
  DECLARE v_return_date  DATETIME;
  DECLARE v_fine_per_day INT UNSIGNED;
  DECLARE v_overdue      INT DEFAULT 0;
  DECLARE v_fine         INT DEFAULT 0;

  SELECT l.loan_id, l.copy_id, l.member_id, l.due_date, l.return_date, t.fine_per_day
    INTO v_loan_id, v_copy_id, v_member_id, v_due, v_return_date, v_fine_per_day
    FROM loan l
    JOIN member m      ON m.member_id = l.member_id
    JOIN member_type t ON t.type_code = m.type_code
   WHERE l.loan_id = p_loan_id
     FOR UPDATE OF l;

  IF v_loan_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '존재하지 않는 대출입니다.';
  END IF;
  IF v_return_date IS NOT NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '이미 반납된 대출입니다.';
  END IF;

  UPDATE loan SET return_date = NOW(), return_type = '분실', return_staff_id = p_staff_id
   WHERE loan_id = v_loan_id;

  SET v_overdue = fn_overdue_days(v_due, CURDATE());
  IF v_overdue > 0 THEN
    SET v_fine = v_overdue * v_fine_per_day;
    INSERT INTO fine (loan_id, overdue_days, amount) VALUES (v_loan_id, v_overdue, v_fine);
  END IF;

  UPDATE book_copy SET status = '분실' WHERE copy_id = v_copy_id;

  SELECT b.title, m.name AS member_name, v_overdue AS overdue_days, v_fine AS fine_amount,
         fn_compensation(b.isbn) AS compensation
    FROM book_copy bc
    JOIN book b   ON b.isbn = bc.isbn
    JOIN member m ON m.member_id = v_member_id
   WHERE bc.copy_id = v_copy_id;
END $$


-- 대출정지 적용 : 오늘부터 p_days 일간 (사서 수동 제재)
DROP PROCEDURE IF EXISTS sp_suspend_member $$
CREATE PROCEDURE sp_suspend_member(IN p_member_id INT UNSIGNED, IN p_reason VARCHAR(10), IN p_days INT,
                                   IN p_memo VARCHAR(200), IN p_staff_id INT UNSIGNED)
COMMENT '대출정지 적용 (사서)'
BEGIN
  DECLARE v_status VARCHAR(10);

  SELECT status INTO v_status FROM member WHERE member_id = p_member_id FOR UPDATE;
  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '존재하지 않는 회원입니다.';
  END IF;
  IF v_status = '탈퇴' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '탈퇴한 회원입니다.';
  END IF;
  IF p_days IS NULL OR p_days NOT BETWEEN 1 AND 365 THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '정지 일수는 1~365일이어야 합니다.';
  END IF;

  INSERT INTO suspension (member_id, reason, start_date, end_date, memo, staff_id)
  VALUES (p_member_id, p_reason, CURDATE(), CURDATE() + INTERVAL (p_days - 1) DAY, p_memo, p_staff_id);

  SELECT suspension_id, start_date, end_date FROM suspension WHERE suspension_id = LAST_INSERT_ID();
END $$


-- 대출정지 해제 : 진행 중이거나 예정된 정지를 조기 해제
DROP PROCEDURE IF EXISTS sp_release_suspension $$
CREATE PROCEDURE sp_release_suspension(IN p_suspension_id INT UNSIGNED, IN p_staff_id INT UNSIGNED)
COMMENT '대출정지 해제 (사서)'
BEGIN
  DECLARE v_id       INT UNSIGNED;
  DECLARE v_end      DATE;
  DECLARE v_released DATE;

  SELECT suspension_id, end_date, released_date INTO v_id, v_end, v_released
    FROM suspension WHERE suspension_id = p_suspension_id FOR UPDATE;
  IF v_id IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '존재하지 않는 대출정지입니다.';
  END IF;
  IF v_released IS NOT NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '이미 해제된 대출정지입니다.';
  END IF;
  IF v_end < CURDATE() THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '이미 기간이 끝난 대출정지입니다.';
  END IF;

  UPDATE suspension SET released_date = CURDATE(), released_staff_id = p_staff_id
   WHERE suspension_id = p_suspension_id;
END $$


-- 휴관일 등록 : 그날이 반납예정일인 미반납 대출을 다음 개관일로 다시 계산
DROP PROCEDURE IF EXISTS sp_add_closed_day $$
CREATE PROCEDURE sp_add_closed_day(IN p_date DATE, IN p_reason VARCHAR(30))
COMMENT '휴관일 등록 + 해당일 반납예정 대출의 반납예정일 재계산'
BEGIN
  IF p_date < CURDATE() THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '지난 날짜는 휴관일로 등록할 수 없습니다.';
  END IF;
  IF EXISTS (SELECT 1 FROM closed_day WHERE closed_date = p_date) THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '이미 등록된 휴관일입니다.';
  END IF;

  INSERT INTO closed_day (closed_date, reason) VALUES (p_date, p_reason);
  UPDATE loan SET due_date = fn_next_open_day(due_date)
   WHERE return_date IS NULL AND due_date = p_date;

  SELECT ROW_COUNT() AS moved_loans;
END $$


-- 연체료 처리 : 미납 → 납부 또는 면제
DROP PROCEDURE IF EXISTS sp_settle_fine $$
CREATE PROCEDURE sp_settle_fine(IN p_fine_id INT UNSIGNED, IN p_status VARCHAR(10), IN p_staff_id INT UNSIGNED)
COMMENT '연체료 납부·면제 처리'
BEGIN
  DECLARE v_status VARCHAR(10);

  IF p_status NOT IN ('납부', '면제') THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '처리 구분은 납부 또는 면제여야 합니다.';
  END IF;
  SELECT status INTO v_status FROM fine WHERE fine_id = p_fine_id FOR UPDATE;
  IF v_status IS NULL THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '존재하지 않는 연체료입니다.';
  END IF;
  IF v_status <> '미납' THEN
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = '이미 처리된 연체료입니다.';
  END IF;

  UPDATE fine SET status = p_status, paid_date = CURDATE(), staff_id = p_staff_id WHERE fine_id = p_fine_id;
END $$

DELIMITER ;

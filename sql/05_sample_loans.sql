-- =====================================================================
-- 대출 이력 샘플 (scripts/build_seed.py 가 생성 — 직접 수정하지 말 것)
-- 값은 모두 '오늘로부터 며칠 전'. 날짜 계산은 DB 함수가 한다.
--   · 대출일·연장일·반납일이 휴관일이면 그 전 개관일로 앞당김
--   · 반납예정일 = fn_next_open_day(대출일 + 대출기간), 연장 = fn_next_open_day(연장일 + 대출기간)
--   · 연체 반납이면 fn_overdue_days(휴관일 제외)로 연체료 생성
-- 대출 230건 (현재 대출 중 24건)
-- =====================================================================
SET NAMES utf8mb4;   -- 클라이언트 문자셋 고정 : 어떤 mysql 클라이언트로 실행해도 한글이 깨지지 않게
USE library_db;

CREATE TEMPORARY TABLE tmp_loan (
  loan_id INT PRIMARY KEY, copy_id INT, member_id INT, loan_ago INT, return_ago INT NULL,
  renew1_ago INT NULL, renew2_ago INT NULL, fine_status VARCHAR(10), lost TINYINT
);
INSERT INTO tmp_loan VALUES
  (1, 126, 10017, 197, 189, NULL, NULL, '납부', 0),
  (2, 101, 10007, 197, 192, NULL, NULL, '납부', 0),
  (3, 120, 10011, 196, 185, NULL, NULL, '납부', 0),
  (4, 114, 10007, 194, 191, NULL, NULL, '납부', 0),
  (5, 95, 10008, 193, 190, NULL, NULL, '납부', 0),
  (6, 125, 10026, 191, 173, NULL, NULL, '납부', 0),
  (7, 155, 10021, 191, 188, NULL, NULL, '면제', 0),
  (8, 51, 10003, 188, 179, NULL, NULL, '납부', 0),
  (9, 14, 10017, 187, 184, NULL, NULL, '납부', 0),
  (10, 31, 10002, 187, 178, NULL, NULL, '납부', 0),
  (11, 76, 10022, 187, 159, NULL, NULL, '납부', 0),
  (12, 119, 10011, 186, 177, NULL, NULL, '납부', 0),
  (13, 121, 10009, 186, 174, NULL, NULL, '납부', 0),
  (14, 6, 10018, 181, 177, NULL, NULL, '납부', 0),
  (15, 82, 10026, 181, 168, NULL, NULL, '납부', 0),
  (16, 62, 10014, 181, 157, NULL, NULL, '납부', 0),
  (17, 90, 10001, 180, 158, NULL, NULL, '납부', 0),
  (18, 49, 10010, 177, 171, NULL, NULL, '납부', 0),
  (19, 146, 10027, 175, 156, NULL, NULL, '납부', 0),
  (20, 55, 10010, 175, 164, NULL, NULL, '납부', 0),
  (21, 65, 10026, 175, 157, NULL, NULL, '면제', 0),
  (22, 114, 10009, 174, 166, NULL, NULL, '납부', 0),
  (23, 63, 10009, 173, 170, NULL, NULL, '납부', 0),
  (24, 37, 10008, 171, 162, NULL, NULL, '납부', 0),
  (25, 107, 10005, 171, 165, NULL, NULL, '납부', 0),
  (26, 124, 10024, 170, NULL, 150, NULL, '납부', 0),
  (27, 127, 10018, 167, 162, NULL, NULL, '면제', 0),
  (28, 32, 10003, 167, 148, NULL, NULL, '납부', 0),
  (29, 151, 10009, 167, 159, NULL, NULL, '납부', 0),
  (30, 58, 10002, 165, 157, NULL, NULL, '납부', 0),
  (31, 14, 10005, 165, 148, 160, NULL, '납부', 0),
  (32, 69, 10011, 165, 156, NULL, NULL, '납부', 0),
  (33, 138, 10003, 164, 157, NULL, NULL, '납부', 0),
  (34, 144, 10005, 162, 154, NULL, NULL, '면제', 0),
  (35, 13, 10022, 162, 140, NULL, NULL, '납부', 0),
  (36, 38, 10005, 161, 141, 159, NULL, '납부', 0),
  (37, 8, 10026, 160, 122, NULL, NULL, '납부', 0),
  (38, 121, 10004, 160, 152, NULL, NULL, '납부', 0),
  (39, 89, 10003, 159, 154, NULL, NULL, '납부', 0),
  (40, 44, 10009, 158, 147, NULL, NULL, '납부', 0),
  (41, 119, 10004, 154, 147, NULL, NULL, '납부', 0),
  (42, 11, 10001, 152, 143, NULL, NULL, '납부', 0),
  (43, 95, 10009, 151, 148, NULL, NULL, '납부', 0),
  (44, 150, 10022, 151, 137, NULL, NULL, '납부', 0),
  (45, 70, 10020, 150, 140, NULL, NULL, '납부', 0),
  (46, 114, 10004, 149, 135, 144, NULL, '면제', 0),
  (47, 77, 10012, 148, 144, NULL, NULL, '납부', 0),
  (48, 6, 10019, 146, 142, NULL, NULL, '납부', 0),
  (49, 106, 10010, 146, 142, NULL, NULL, '납부', 0),
  (50, 58, 10007, 146, 137, NULL, NULL, '납부', 0),
  (51, 123, 10006, 144, 141, NULL, NULL, '납부', 0),
  (52, 127, 10022, 143, 114, NULL, NULL, '납부', 0),
  (53, 39, 10016, 143, 138, NULL, NULL, '납부', 0),
  (54, 80, 10014, 143, 132, NULL, NULL, '납부', 0),
  (55, 79, 10021, 143, 137, NULL, NULL, '납부', 0),
  (56, 156, 10023, 142, 116, 139, NULL, '납부', 0),
  (57, 1, 10007, 141, 133, NULL, NULL, '납부', 0),
  (58, 66, 10017, 141, 133, NULL, NULL, '납부', 0),
  (59, 75, 10018, 140, 135, NULL, NULL, '납부', 0),
  (60, 21, 10004, 140, 133, NULL, NULL, '납부', 0),
  (61, 77, 10019, 137, 128, NULL, NULL, '납부', 0),
  (62, 133, 10012, 137, 119, NULL, NULL, '납부', 0),
  (63, 23, 10018, 136, 127, NULL, NULL, '납부', 0),
  (64, 61, 10013, 135, 82, NULL, NULL, '납부', 0),
  (65, 38, 10022, 135, 101, 130, NULL, '납부', 0),
  (66, 18, 10016, 135, 125, NULL, NULL, '납부', 0),
  (67, 101, 10004, 135, 123, NULL, NULL, '납부', 0),
  (68, 86, 10015, 132, 129, NULL, NULL, '납부', 0),
  (69, 148, 10024, 130, NULL, NULL, NULL, '납부', 0),
  (70, 63, 10010, 130, 124, NULL, NULL, '납부', 0),
  (71, 69, 10021, 130, 117, NULL, NULL, '납부', 0),
  (72, 138, 10012, 130, 123, NULL, NULL, '납부', 0),
  (73, 128, 10009, 130, 127, NULL, NULL, '납부', 0),
  (74, 151, 10001, 129, 120, NULL, NULL, '납부', 0),
  (75, 14, 10015, 129, 116, NULL, NULL, '납부', 0),
  (76, 145, 10003, 129, 117, NULL, NULL, '납부', 0),
  (77, 96, 10005, 129, 126, NULL, NULL, '납부', 0),
  (78, 52, 10014, 128, 124, NULL, NULL, '납부', 0),
  (79, 59, 10018, 128, 112, 126, NULL, '납부', 0),
  (80, 135, 10023, 128, 107, NULL, NULL, '면제', 0),
  (81, 150, 10005, 126, 113, NULL, NULL, '납부', 0),
  (82, 36, 10020, 125, 115, NULL, NULL, '납부', 0),
  (83, 106, 10022, 125, 83, 123, NULL, '납부', 0),
  (84, 13, 10016, 125, 114, NULL, NULL, '납부', 0),
  (85, 107, 10021, 123, 119, NULL, NULL, '면제', 0),
  (86, 75, 10016, 122, 113, NULL, NULL, '납부', 0),
  (87, 51, 10014, 122, 115, NULL, NULL, '납부', 0),
  (88, 114, 10022, 119, 115, NULL, NULL, '납부', 0),
  (89, 30, 10016, 118, 114, NULL, NULL, '납부', 0),
  (90, 120, 10005, 118, 106, NULL, NULL, '납부', 0),
  (91, 45, 10015, 117, 107, NULL, NULL, '납부', 0),
  (92, 77, 10005, 114, 101, NULL, NULL, '납부', 0),
  (93, 19, 10002, 113, 108, NULL, NULL, '납부', 0),
  (94, 126, 10002, 113, 101, NULL, NULL, '면제', 0),
  (95, 6, 10008, 112, 99, NULL, NULL, '납부', 0),
  (96, 5, 10007, 112, 101, NULL, NULL, '납부', 0),
  (97, 21, 10014, 112, 99, NULL, NULL, '납부', 0),
  (98, 33, 10022, 111, 86, NULL, NULL, '납부', 0),
  (99, 32, 10017, 111, 101, NULL, NULL, '납부', 0),
  (100, 138, 10005, 111, 102, NULL, NULL, '납부', 0),
  (101, 99, 10021, 111, 108, NULL, NULL, '납부', 0),
  (102, 83, 10015, 110, 91, NULL, NULL, '납부', 0),
  (103, 101, 10016, 109, 106, NULL, NULL, '납부', 0),
  (104, 63, 10006, 108, 97, NULL, NULL, '면제', 0),
  (105, 111, 10006, 108, 102, NULL, NULL, '납부', 0),
  (106, 94, 10006, 108, 96, NULL, NULL, '납부', 0),
  (107, 53, 10009, 107, 103, NULL, NULL, '납부', 0),
  (108, 59, 10005, 106, 100, NULL, NULL, '납부', 0),
  (109, 92, 10022, 106, 88, NULL, NULL, '납부', 0),
  (110, 90, 10027, 105, 71, NULL, NULL, '납부', 0),
  (111, 4, 10003, 104, 93, NULL, NULL, '납부', 0),
  (112, 103, 10018, 104, 91, NULL, NULL, '납부', 0),
  (113, 69, 10009, 103, 98, NULL, NULL, '납부', 0),
  (114, 41, 10016, 103, 78, NULL, NULL, '납부', 0),
  (115, 42, 10024, 100, NULL, NULL, NULL, '납부', 0),
  (116, 95, 10020, 100, 90, NULL, NULL, '납부', 0),
  (117, 142, 10011, 99, 94, NULL, NULL, '납부', 0),
  (118, 140, 10011, 99, 95, NULL, NULL, '납부', 0),
  (119, 108, 10011, 99, 95, NULL, NULL, '납부', 0),
  (120, 70, 10010, 99, 89, NULL, NULL, '납부', 0),
  (121, 127, 10017, 97, 87, NULL, NULL, '면제', 0),
  (122, 14, 10018, 96, 87, NULL, NULL, '납부', 0),
  (123, 76, 10027, 95, 88, NULL, NULL, '납부', 0),
  (124, 15, 10008, 94, 90, NULL, NULL, '납부', 0),
  (125, 126, 10021, 94, 78, 92, NULL, '납부', 0),
  (126, 107, 10004, 94, 85, NULL, NULL, '납부', 0),
  (127, 47, 10026, 94, 69, NULL, NULL, '납부', 0),
  (128, 75, 10011, 93, 82, NULL, NULL, '납부', 0),
  (129, 36, 10026, 93, 79, NULL, NULL, '납부', 0),
  (130, 58, 10023, 93, 81, NULL, NULL, '납부', 0),
  (131, 32, 10018, 91, 81, NULL, NULL, '납부', 0),
  (132, 110, 10004, 88, 79, NULL, NULL, '면제', 0),
  (133, 40, 10026, 86, 67, NULL, NULL, '납부', 0),
  (134, 51, 10003, 86, 75, NULL, NULL, '면제', 0),
  (135, 155, 10003, 85, 80, NULL, NULL, '면제', 0),
  (136, 4, 10008, 85, 76, NULL, NULL, '면제', 0),
  (137, 46, 10012, 85, 67, 83, NULL, '납부', 0),
  (138, 134, 10001, 84, 62, NULL, NULL, '납부', 0),
  (139, 31, 10006, 84, 78, NULL, NULL, '납부', 0),
  (140, 95, 10021, 83, 75, NULL, NULL, '납부', 0),
  (141, 67, 10015, 83, 77, NULL, NULL, '납부', 0),
  (142, 135, 10006, 80, 68, NULL, NULL, '면제', 0),
  (143, 119, 10019, 80, 54, NULL, NULL, '면제', 0),
  (144, 8, 10021, 80, 76, NULL, NULL, '납부', 0),
  (145, 99, 10023, 78, 69, NULL, NULL, '납부', 0),
  (146, 53, 10017, 77, 70, NULL, NULL, '납부', 0),
  (147, 82, 10022, 77, 65, NULL, NULL, '납부', 0),
  (148, 151, 10005, 76, 71, NULL, NULL, '면제', 0),
  (149, 87, 10019, 76, 65, NULL, NULL, '납부', 0),
  (150, 23, 10024, 75, NULL, NULL, NULL, '납부', 0),
  (151, 6, 10011, 74, 61, NULL, NULL, '납부', 0),
  (152, 120, 10018, 74, 68, NULL, NULL, '납부', 0),
  (153, 84, 10009, 72, 62, NULL, NULL, '납부', 0),
  (154, 28, 10026, 71, 55, NULL, NULL, '면제', 0),
  (155, 85, 10015, 70, 50, NULL, NULL, '납부', 1),
  (156, 95, 10011, 69, 59, NULL, NULL, '납부', 0),
  (157, 63, 10016, 67, 56, NULL, NULL, '납부', 0),
  (158, 127, 10002, 67, 62, NULL, NULL, '납부', 0),
  (159, 138, 10023, 65, 61, NULL, NULL, '납부', 0),
  (160, 21, 10009, 64, 60, NULL, NULL, '면제', 0),
  (161, 98, 10023, 64, 38, NULL, NULL, '면제', 0),
  (162, 30, 10026, 64, 48, NULL, NULL, '납부', 0),
  (163, 70, 10006, 63, 55, NULL, NULL, '납부', 0),
  (164, 112, 10022, 62, 37, NULL, NULL, '납부', 0),
  (165, 135, 10025, 61, NULL, NULL, NULL, '납부', 0),
  (166, 32, 10023, 61, 23, 56, NULL, '납부', 0),
  (167, 93, 10012, 60, NULL, NULL, NULL, '납부', 0),
  (168, 69, 10005, 60, 51, NULL, NULL, '납부', 0),
  (169, 72, 10013, 60, 54, NULL, NULL, '납부', 0),
  (170, 71, 10013, 59, 52, NULL, NULL, '납부', 0),
  (171, 1, 10009, 59, 47, NULL, NULL, '납부', 0),
  (172, 151, 10006, 58, 55, NULL, NULL, '납부', 0),
  (173, 107, 10021, 58, 49, NULL, NULL, '납부', 0),
  (174, 133, 10005, 58, 35, NULL, NULL, '납부', 0),
  (175, 89, 10026, 57, 34, NULL, NULL, '납부', 0),
  (176, 121, 10010, 55, 47, NULL, NULL, '면제', 0),
  (177, 59, 10026, 54, 30, NULL, NULL, '면제', 0),
  (178, 14, 10011, 54, 30, NULL, NULL, '면제', 0),
  (179, 19, 10014, 54, 46, NULL, NULL, '납부', 0),
  (180, 75, 10009, 53, 45, NULL, NULL, '납부', 0),
  (181, 114, 10014, 53, 44, NULL, NULL, '면제', 0),
  (182, 26, 10011, 52, 49, NULL, NULL, '납부', 0),
  (183, 96, 10005, 51, 31, NULL, NULL, '납부', 0),
  (184, 37, 10006, 48, 36, NULL, NULL, '납부', 0),
  (185, 149, 10026, 47, 35, NULL, NULL, '납부', 0),
  (186, 50, 10009, 47, 41, NULL, NULL, '납부', 0),
  (187, 101, 10023, 47, 4, 42, NULL, '면제', 0),
  (188, 77, 10008, 47, 36, NULL, NULL, '납부', 0),
  (189, 91, 10004, 46, 41, NULL, NULL, '납부', 0),
  (190, 90, 10014, 46, 37, NULL, NULL, '납부', 0),
  (191, 110, 10004, 45, 33, NULL, NULL, '납부', 0),
  (192, 26, 10019, 43, 39, NULL, NULL, '납부', 0),
  (193, 144, 10014, 42, 38, NULL, NULL, '납부', 0),
  (194, 38, 10010, 41, 35, NULL, NULL, '면제', 0),
  (195, 76, 10009, 40, 20, NULL, NULL, '미납', 0),
  (196, 132, 10024, 40, NULL, NULL, NULL, '납부', 0),
  (197, 6, 10009, 39, 26, NULL, NULL, '면제', 0),
  (198, 13, 10019, 39, 28, NULL, NULL, '납부', 0),
  (199, 147, 10023, 38, NULL, NULL, NULL, '납부', 0),
  (200, 138, 10018, 38, 35, NULL, NULL, '납부', 0),
  (201, 92, 10015, 38, 35, NULL, NULL, '납부', 0),
  (202, 153, 10013, 37, 25, NULL, NULL, '납부', 0),
  (203, 108, 10025, 33, NULL, NULL, NULL, '납부', 0),
  (204, 130, 10018, 33, 27, NULL, NULL, '납부', 0),
  (205, 75, 10003, 33, 22, NULL, NULL, '납부', 0),
  (206, 82, 10010, 31, 22, NULL, NULL, '면제', 0),
  (207, 45, 10019, 31, 24, NULL, NULL, '납부', 0),
  (208, 19, 10010, 31, 22, NULL, NULL, '납부', 0),
  (209, 90, 10016, 30, 20, NULL, NULL, '면제', 0),
  (210, 16, 10010, 29, 23, NULL, NULL, '납부', 0),
  (211, 136, 10007, 28, 22, NULL, NULL, '납부', 0),
  (212, 138, 10018, 27, 24, NULL, NULL, '납부', 0),
  (213, 117, 10027, 26, NULL, NULL, NULL, '납부', 0),
  (214, 155, 10010, 26, 23, NULL, NULL, '납부', 0),
  (215, 111, 10004, 25, NULL, NULL, NULL, '납부', 0),
  (216, 70, 10010, 25, 21, NULL, NULL, '납부', 0),
  (217, 128, 10003, 24, NULL, NULL, NULL, '납부', 0),
  (218, 131, 10006, 23, 13, NULL, NULL, '면제', 0),
  (219, 15, 10022, 22, NULL, NULL, NULL, '납부', 0),
  (220, 7, 10003, 20, NULL, NULL, NULL, '납부', 0),
  (221, 154, 10024, 15, NULL, NULL, NULL, '납부', 0),
  (222, 133, 10006, 13, NULL, 9, 3, '납부', 0),
  (223, 125, 10008, 12, NULL, NULL, NULL, '납부', 0),
  (224, 138, 10026, 12, NULL, NULL, NULL, '납부', 0),
  (225, 115, 10022, 11, NULL, NULL, NULL, '납부', 0),
  (226, 109, 10001, 9, NULL, 4, NULL, '납부', 0),
  (227, 103, 10025, 8, NULL, NULL, NULL, '납부', 0),
  (228, 6, 10001, 5, NULL, NULL, NULL, '납부', 0),
  (229, 153, 10022, 3, NULL, NULL, NULL, '납부', 0),
  (230, 134, 10002, 0, NULL, NULL, NULL, '납부', 0);

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

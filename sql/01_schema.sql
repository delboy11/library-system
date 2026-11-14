-- =====================================================================
-- 도서관 대출·반납·연체 관리 시스템 : 물리적 데이터 모델 (DDL)  v2
-- DBMS : MySQL 8.0.19 이상 (CHECK 제약, 생성 컬럼, FOR UPDATE OF, INSERT 행 별칭 사용)
-- 실행 : mysql -u root --default-character-set=utf8mb4 < sql/01_schema.sql
-- 테이블 14개
--   회원구분 member_type · 회원 member · 사서 staff
--   분류 category · 출판사 publisher · 저자 author · 도서 book · 도서저자 book_author · 도서복본 book_copy
--   대출 loan · 연장이력 renewal · 연체료 fine · 대출정지 suspension · 휴관일 closed_day
-- =====================================================================

DROP DATABASE IF EXISTS library_db;
CREATE DATABASE library_db
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE library_db;

-- 응용프로그램 전용 계정 (DML + 프로시저 실행 권한만 부여)
DROP USER IF EXISTS 'library'@'localhost', 'library'@'127.0.0.1';
CREATE USER 'library'@'localhost' IDENTIFIED BY 'library1234';
CREATE USER 'library'@'127.0.0.1' IDENTIFIED BY 'library1234';
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON library_db.* TO 'library'@'localhost';
GRANT SELECT, INSERT, UPDATE, DELETE, EXECUTE ON library_db.* TO 'library'@'127.0.0.1';


-- ---------------------------------------------------------------------
-- 1. 회원구분 : 신분별 대출 정책 (숭실대학교 중앙도서관 대출 규정 기준)
--    연장 시 "연장한 날부터 대출기간만큼" 늘어나므로 연장 일수는 loan_days 를 그대로 쓴다.
-- ---------------------------------------------------------------------
CREATE TABLE member_type (
  type_code       VARCHAR(10)      NOT NULL COMMENT '회원구분코드',
  type_name       VARCHAR(20)      NOT NULL COMMENT '회원구분명',
  max_loan_count  TINYINT UNSIGNED NOT NULL COMMENT '최대 대출 권수',
  loan_days       TINYINT UNSIGNED NOT NULL COMMENT '대출 기간(일) - 연장 1회 기간과 같음',
  max_renew       TINYINT UNSIGNED NOT NULL COMMENT '최대 연장 횟수',
  fine_per_day    INT UNSIGNED     NOT NULL COMMENT '1권 1일 연체료(원)',
  CONSTRAINT pk_member_type          PRIMARY KEY (type_code),
  CONSTRAINT uq_member_type_name     UNIQUE (type_name),
  CONSTRAINT ck_member_type_max_loan CHECK (max_loan_count BETWEEN 1 AND 100),
  CONSTRAINT ck_member_type_days     CHECK (loan_days BETWEEN 1 AND 180),
  CONSTRAINT ck_member_type_renew    CHECK (max_renew <= 10)
) COMMENT = '회원구분';


-- ---------------------------------------------------------------------
-- 2. 회원 : 학번/교번(member_no)으로 회원 포털에 로그인
--    status 는 계정 상태(정상/탈퇴)만 저장. 대출정지 여부는 suspension 에서 계산한다.
-- ---------------------------------------------------------------------
CREATE TABLE member (
  member_id      INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '회원번호 (내부 식별자)',
  member_no      VARCHAR(20)  NOT NULL COMMENT '학번·교번 (로그인 ID)',
  password_hash  VARCHAR(255) NOT NULL COMMENT '비밀번호 해시',
  name           VARCHAR(30)  NOT NULL COMMENT '이름',
  type_code      VARCHAR(10)  NOT NULL COMMENT '회원구분코드',
  department     VARCHAR(50)      NULL COMMENT '소속 (학과·부서)',
  phone          VARCHAR(13)  NOT NULL COMMENT '휴대전화 (010-0000-0000)',
  email          VARCHAR(100)     NULL COMMENT '이메일',
  status         VARCHAR(10)  NOT NULL DEFAULT '정상' COMMENT '계정상태',
  join_date      DATE         NOT NULL DEFAULT (CURRENT_DATE) COMMENT '가입일',
  withdraw_date  DATE             NULL COMMENT '탈퇴일',
  CONSTRAINT pk_member           PRIMARY KEY (member_id),
  CONSTRAINT uq_member_no        UNIQUE (member_no),
  CONSTRAINT uq_member_phone     UNIQUE (phone),
  CONSTRAINT uq_member_email     UNIQUE (email),
  CONSTRAINT fk_member_type      FOREIGN KEY (type_code)
    REFERENCES member_type (type_code) ON UPDATE CASCADE,
  CONSTRAINT ck_member_status    CHECK (status IN ('정상', '탈퇴')),
  CONSTRAINT ck_member_withdraw  CHECK ((status = '탈퇴') = (withdraw_date IS NOT NULL)),
  CONSTRAINT ck_member_no        CHECK (member_no REGEXP '^[0-9A-Za-z]{4,20}$'),
  CONSTRAINT ck_member_phone     CHECK (phone REGEXP '^01[0-9]-[0-9]{3,4}-[0-9]{4}$'),
  INDEX idx_member_name (name)
) AUTO_INCREMENT = 10001 COMMENT = '회원';


-- ---------------------------------------------------------------------
-- 3. 사서 : 관리 프로그램 로그인 계정, 대출·반납 처리자
-- ---------------------------------------------------------------------
CREATE TABLE staff (
  staff_id       INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '사서번호',
  login_id       VARCHAR(20)  NOT NULL COMMENT '로그인 ID',
  password_hash  VARCHAR(255) NOT NULL COMMENT '비밀번호 해시',
  name           VARCHAR(30)  NOT NULL COMMENT '이름',
  role           VARCHAR(10)  NOT NULL DEFAULT '사서' COMMENT '권한',
  hire_date      DATE         NOT NULL DEFAULT (CURRENT_DATE) COMMENT '입사일',
  CONSTRAINT pk_staff       PRIMARY KEY (staff_id),
  CONSTRAINT uq_staff_login UNIQUE (login_id),
  CONSTRAINT ck_staff_role  CHECK (role IN ('관리자', '사서'))
) COMMENT = '사서';


-- ---------------------------------------------------------------------
-- 4. 분류 (한국십진분류법 KDC 주류 10개)
-- ---------------------------------------------------------------------
CREATE TABLE category (
  category_code  CHAR(3)     NOT NULL COMMENT '분류코드 (KDC 주류)',
  category_name  VARCHAR(30) NOT NULL COMMENT '분류명',
  CONSTRAINT pk_category      PRIMARY KEY (category_code),
  CONSTRAINT uq_category_name UNIQUE (category_name),
  CONSTRAINT ck_category_code CHECK (category_code REGEXP '^[0-9]00$')
) COMMENT = '분류';


-- ---------------------------------------------------------------------
-- 5. 출판사
-- ---------------------------------------------------------------------
CREATE TABLE publisher (
  publisher_id    INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '출판사번호',
  publisher_name  VARCHAR(50)  NOT NULL COMMENT '출판사명',
  CONSTRAINT pk_publisher      PRIMARY KEY (publisher_id),
  CONSTRAINT uq_publisher_name UNIQUE (publisher_name)
) COMMENT = '출판사';


-- ---------------------------------------------------------------------
-- 6. 저자
-- ---------------------------------------------------------------------
CREATE TABLE author (
  author_id    INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '저자번호',
  author_name  VARCHAR(50)  NOT NULL COMMENT '저자명',
  CONSTRAINT pk_author PRIMARY KEY (author_id),
  INDEX idx_author_name (author_name)
) COMMENT = '저자';


-- ---------------------------------------------------------------------
-- 7. 도서 (서지정보 : ISBN 단위, 국립중앙도서관 API 에서 수집)
-- ---------------------------------------------------------------------
CREATE TABLE book (
  isbn           CHAR(13)          NOT NULL COMMENT 'ISBN-13',
  title          VARCHAR(200)      NOT NULL COMMENT '서명',
  publisher_id   INT UNSIGNED      NOT NULL COMMENT '출판사번호',
  category_code  CHAR(3)           NOT NULL COMMENT '분류코드 (KDC 주류)',
  kdc_no         VARCHAR(20)           NULL COMMENT 'KDC 분류기호 (예: 813.7)',
  pub_year       SMALLINT UNSIGNED     NULL COMMENT '발행연도',
  price          INT UNSIGNED          NULL COMMENT '정가(원)',
  created_at     DATETIME          NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '등록일시',
  CONSTRAINT pk_book           PRIMARY KEY (isbn),
  CONSTRAINT fk_book_publisher FOREIGN KEY (publisher_id)
    REFERENCES publisher (publisher_id) ON UPDATE CASCADE,
  CONSTRAINT fk_book_category  FOREIGN KEY (category_code)
    REFERENCES category (category_code) ON UPDATE CASCADE,
  CONSTRAINT ck_book_isbn      CHECK (isbn REGEXP '^97[89][0-9]{10}$'),
  CONSTRAINT ck_book_pub_year  CHECK (pub_year BETWEEN 1450 AND 2100),
  INDEX idx_book_title (title)
) COMMENT = '도서';


-- ---------------------------------------------------------------------
-- 8. 도서저자 : 도서-저자 M:N 관계 해소 (공저·번역)
-- ---------------------------------------------------------------------
CREATE TABLE book_author (
  isbn          CHAR(13)         NOT NULL COMMENT 'ISBN',
  author_id     INT UNSIGNED     NOT NULL COMMENT '저자번호',
  author_role   VARCHAR(10)      NOT NULL DEFAULT '지은이' COMMENT '저자역할',
  author_order  TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '표기순서',
  CONSTRAINT pk_book_author      PRIMARY KEY (isbn, author_id),
  CONSTRAINT fk_book_author_book FOREIGN KEY (isbn)
    REFERENCES book (isbn) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_book_author_auth FOREIGN KEY (author_id)
    REFERENCES author (author_id),
  CONSTRAINT ck_book_author_role CHECK (author_role IN ('지은이', '옮긴이', '엮은이', '그림'))
) COMMENT = '도서저자';


-- ---------------------------------------------------------------------
-- 9. 도서복본 : 서가에 있는 실물 책 1권 (등록번호 단위)
-- ---------------------------------------------------------------------
CREATE TABLE book_copy (
  copy_id        INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '복본번호',
  reg_no         VARCHAR(10)  NOT NULL COMMENT '등록번호 (바코드)',
  isbn           CHAR(13)     NOT NULL COMMENT 'ISBN',
  call_no        VARCHAR(40)  NOT NULL COMMENT '청구기호',
  location       VARCHAR(30)  NOT NULL DEFAULT '종합자료실' COMMENT '배가위치',
  status         VARCHAR(10)  NOT NULL DEFAULT '대출가능' COMMENT '복본상태',
  acquired_date  DATE         NOT NULL DEFAULT (CURRENT_DATE) COMMENT '입수일',
  removed_date   DATE             NULL COMMENT '분실·폐기 처리일',
  CONSTRAINT pk_book_copy         PRIMARY KEY (copy_id),
  CONSTRAINT uq_book_copy_reg_no  UNIQUE (reg_no),
  CONSTRAINT fk_book_copy_book    FOREIGN KEY (isbn)
    REFERENCES book (isbn) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_book_copy_status  CHECK (status IN ('대출가능', '대출중', '분실', '폐기')),
  CONSTRAINT ck_book_copy_removed CHECK ((status IN ('분실', '폐기')) = (removed_date IS NOT NULL)),
  CONSTRAINT ck_book_copy_reg_no  CHECK (reg_no REGEXP '^EM[0-9]{6}$'),
  INDEX idx_book_copy_isbn_status (isbn, status)
) COMMENT = '도서복본';


-- ---------------------------------------------------------------------
-- 10. 대출 : 대출 1건 = 복본 1권. 반납(또는 분실 처리) 시 return_date 기록
-- ---------------------------------------------------------------------
CREATE TABLE loan (
  loan_id          INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '대출번호',
  copy_id          INT UNSIGNED NOT NULL COMMENT '복본번호',
  member_id        INT UNSIGNED NOT NULL COMMENT '회원번호',
  staff_id         INT UNSIGNED NOT NULL COMMENT '대출 처리 사서',
  loan_date        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '대출일시',
  due_date         DATE         NOT NULL COMMENT '반납예정일 (연장 시 갱신)',
  return_date      DATETIME         NULL COMMENT '반납일시',
  return_type      VARCHAR(10)      NULL COMMENT '반납구분 (반납/분실)',
  return_staff_id  INT UNSIGNED     NULL COMMENT '반납 처리 사서',
  -- 반납 전이면 copy_id, 반납 후면 NULL → UNIQUE 로 "복본당 미반납 대출 1건" 보장
  active_copy_id   INT UNSIGNED GENERATED ALWAYS AS (IF(return_date IS NULL, copy_id, NULL)) STORED
                   COMMENT '미반납 복본 (생성 컬럼)',
  CONSTRAINT pk_loan              PRIMARY KEY (loan_id),
  CONSTRAINT uq_loan_active_copy  UNIQUE (active_copy_id),
  CONSTRAINT fk_loan_copy         FOREIGN KEY (copy_id)   REFERENCES book_copy (copy_id),
  CONSTRAINT fk_loan_member       FOREIGN KEY (member_id) REFERENCES member (member_id),
  CONSTRAINT fk_loan_staff        FOREIGN KEY (staff_id)  REFERENCES staff (staff_id),
  CONSTRAINT fk_loan_return_staff FOREIGN KEY (return_staff_id) REFERENCES staff (staff_id),
  CONSTRAINT ck_loan_due_date     CHECK (due_date >= DATE(loan_date)),
  CONSTRAINT ck_loan_return_date  CHECK (return_date IS NULL OR return_date >= loan_date),
  CONSTRAINT ck_loan_return_type  CHECK (return_type IN ('반납', '분실')),
  CONSTRAINT ck_loan_returned     CHECK ((return_date IS NULL) = (return_type IS NULL)
                                     AND (return_date IS NULL) = (return_staff_id IS NULL)),
  INDEX idx_loan_member_return (member_id, return_date),
  INDEX idx_loan_due_date (due_date),
  INDEX idx_loan_loan_date (loan_date)
) COMMENT = '대출';


-- ---------------------------------------------------------------------
-- 11. 연장이력 : 연장 1회 = 1행. 연장 횟수는 COUNT 로 계산 (중복 저장 안 함)
-- ---------------------------------------------------------------------
CREATE TABLE renewal (
  renewal_id     INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '연장번호',
  loan_id        INT UNSIGNED NOT NULL COMMENT '대출번호',
  renewed_at     DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '연장일시',
  prev_due_date  DATE         NOT NULL COMMENT '연장 전 반납예정일',
  new_due_date   DATE         NOT NULL COMMENT '연장 후 반납예정일',
  channel        VARCHAR(10)  NOT NULL COMMENT '신청경로',
  staff_id       INT UNSIGNED     NULL COMMENT '처리 사서 (홈페이지 신청은 NULL)',
  CONSTRAINT pk_renewal         PRIMARY KEY (renewal_id),
  CONSTRAINT fk_renewal_loan    FOREIGN KEY (loan_id)  REFERENCES loan (loan_id),
  CONSTRAINT fk_renewal_staff   FOREIGN KEY (staff_id) REFERENCES staff (staff_id),
  CONSTRAINT ck_renewal_due     CHECK (new_due_date > prev_due_date),
  CONSTRAINT ck_renewal_channel CHECK (channel IN ('홈페이지', '사서')),
  CONSTRAINT ck_renewal_staff   CHECK ((channel = '사서') = (staff_id IS NOT NULL)),
  INDEX idx_renewal_loan (loan_id)
) COMMENT = '연장이력';


-- ---------------------------------------------------------------------
-- 12. 연체료 : 연체 반납 시 대출 1건당 최대 1건 (1:0..1)
--     금액 = 연체일수(휴관일 제외) × 1권 1일 연체료
-- ---------------------------------------------------------------------
CREATE TABLE fine (
  fine_id       INT UNSIGNED      NOT NULL AUTO_INCREMENT COMMENT '연체료번호',
  loan_id       INT UNSIGNED      NOT NULL COMMENT '대출번호',
  overdue_days  SMALLINT UNSIGNED NOT NULL COMMENT '연체일수 (휴관일 제외)',
  amount        INT UNSIGNED      NOT NULL COMMENT '연체료(원) - 부과 시점 정책으로 확정',
  status        VARCHAR(10)       NOT NULL DEFAULT '미납' COMMENT '납부상태',
  imposed_date  DATE              NOT NULL DEFAULT (CURRENT_DATE) COMMENT '부과일',
  paid_date     DATE                  NULL COMMENT '처리일 (납부/면제)',
  staff_id      INT UNSIGNED          NULL COMMENT '납부·면제 처리 사서',
  CONSTRAINT pk_fine        PRIMARY KEY (fine_id),
  CONSTRAINT uq_fine_loan   UNIQUE (loan_id),
  CONSTRAINT fk_fine_loan   FOREIGN KEY (loan_id)  REFERENCES loan (loan_id),
  CONSTRAINT fk_fine_staff  FOREIGN KEY (staff_id) REFERENCES staff (staff_id),
  CONSTRAINT ck_fine_status CHECK (status IN ('미납', '납부', '면제')),
  CONSTRAINT ck_fine_days   CHECK (overdue_days > 0),
  CONSTRAINT ck_fine_paid   CHECK ((status = '미납') = (paid_date IS NULL)),
  INDEX idx_fine_status (status)
) COMMENT = '연체료';


-- ---------------------------------------------------------------------
-- 13. 대출정지 : 사서가 기간을 정해 적용하는 이용 제재 (규정 제27조) 와 해제 이력
--     ※ 연체 중인 회원의 대출·연장 금지(규정 제24조)는 이 테이블이 아니라 미반납 연체 대출로 판단한다.
--     유효 정지 = released_date IS NULL AND CURDATE() BETWEEN start_date AND end_date
-- ---------------------------------------------------------------------
CREATE TABLE suspension (
  suspension_id      INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '정지번호',
  member_id          INT UNSIGNED NOT NULL COMMENT '회원번호',
  loan_id            INT UNSIGNED     NULL COMMENT '관련 대출 (선택)',
  reason             VARCHAR(10)  NOT NULL COMMENT '정지사유',
  start_date         DATE         NOT NULL COMMENT '정지 시작일',
  end_date           DATE         NOT NULL COMMENT '정지 종료일 (이 날까지 대출 불가)',
  memo               VARCHAR(200)     NULL COMMENT '비고',
  staff_id           INT UNSIGNED NOT NULL COMMENT '적용 사서',
  released_date      DATE             NULL COMMENT '조기 해제일',
  released_staff_id  INT UNSIGNED     NULL COMMENT '해제 사서',
  CONSTRAINT pk_suspension          PRIMARY KEY (suspension_id),
  CONSTRAINT fk_suspension_member   FOREIGN KEY (member_id) REFERENCES member (member_id),
  CONSTRAINT fk_suspension_loan     FOREIGN KEY (loan_id)   REFERENCES loan (loan_id),
  CONSTRAINT fk_suspension_staff    FOREIGN KEY (staff_id)  REFERENCES staff (staff_id),
  CONSTRAINT fk_suspension_released FOREIGN KEY (released_staff_id) REFERENCES staff (staff_id),
  CONSTRAINT ck_suspension_reason   CHECK (reason IN ('장기연체', '자료훼손', '규정위반', '기타')),
  CONSTRAINT ck_suspension_period   CHECK (end_date >= start_date),
  CONSTRAINT ck_suspension_release  CHECK ((released_date IS NULL) = (released_staff_id IS NULL)),
  INDEX idx_suspension_member_end (member_id, end_date)
) COMMENT = '대출정지';


-- ---------------------------------------------------------------------
-- 14. 휴관일 : 일요일·법정공휴일·개교기념일 등 (규정 제18조)
--     반납예정일이 휴관일이면 다음 개관일로 미루고, 연체일수에서 휴관일을 뺀다.
-- ---------------------------------------------------------------------
CREATE TABLE closed_day (
  closed_date  DATE        NOT NULL COMMENT '휴관일자',
  reason       VARCHAR(30) NOT NULL COMMENT '휴관사유',
  CONSTRAINT pk_closed_day PRIMARY KEY (closed_date)
) COMMENT = '휴관일';

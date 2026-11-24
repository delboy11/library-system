# 도서관 대출·반납·연체 관리 시스템

숭실대학교 데이터베이스응용 팀 프로젝트. 숭실대학교 중앙도서관의 대출 규정을 기준으로 사서용 관리 프로그램과 회원 포털을 만들었다.
대출 규칙을 응용프로그램이 아니라 데이터베이스(제약조건·뷰·저장 프로시저·트리거)가 지키도록 설계한 것이 핵심이다.

설계 문서(업무 기능도, 단위 업무 기술서, 업무 흐름도, ERD, 용어 사전, 도메인 정의서, 테이블 기술서)는 따로 제출한 최종 보고서에 있다.

## 개발 환경

| 구분 | 사용한 것 |
|---|---|
| 개발 언어 | Python 3 (웹 프레임워크 Flask, DB 연결 PyMySQL) |
| DBMS | MySQL 8.4 |
| DB 서버 | 발표 노트북과 다른 PC에 Docker 컨테이너로 설치 |
| 네트워크 | Tailscale(VPN)로 발표 노트북과 DB 서버를 연결 |
| 모델링 도구 | ERDCloud |
| 협업 도구 | GitHub, Notion |

## 시스템 구성

```
[발표 노트북]                                         [DB 서버 PC]
 브라우저 ──HTTP──▶ 웹 서버 Flask ──Tailscale VPN──▶ MySQL 8.4 (Docker)
                    계정 library                      library_db
```

- 브라우저(클라이언트), 웹 서버, DB 서버의 세 층으로 나누었고 DB 서버는 다른 PC에 있다.
- 웹 서버는 전용 계정 `library`로 접속한다. 이 계정은 조회·입력·수정·삭제와 프로시저 실행만 할 수 있고, 테이블을 만들거나 지울 수 없다.

## 기능 (6개 영역, 단위 업무 25개)

| 영역 | 단위 업무 |
|---|---|
| 회원 관리 | 회원 등록, 회원 정보 수정, 탈퇴 처리, 회원 조회 |
| 도서 관리 | 도서 등록, 도서 정보 수정, 복본 추가, 폐기 처리, 도서 검색, 함께 대출한 책 추천 |
| 대출 관리 | 대출 가능 여부 검사, 대출 처리, 대출 내역 조회, 대출 연장 |
| 반납 관리 | 반납 처리, 연체일수 자동 계산, 분실 처리 |
| 연체 관리 | 연체자 조회, 대출정지 적용, 대출정지 해제, 연체료 부과·납부·면제 |
| 공통 | 사서 로그인·권한, 회원 로그인·비밀번호 변경, 휴관일 관리, 대시보드·통계 |

- 사서용 화면: `http://127.0.0.1:5000`
- 회원 포털: `http://127.0.0.1:5000/my` (도서 검색, 내 대출 현황, 연장 신청)

## 설계에서 고민한 점

- **같은 책이 여러 권 있을 때**: 책의 정보(`book`)와 실물 한 권(`book_copy`)을 다른 테이블로 나누고, 대출은 실물 단위로 기록한다.
- **한 권이 동시에 두 번 대출되는 것 막기**: 대출 테이블에 "반납 전이면 복본번호, 반납되면 NULL"인 생성 컬럼을 두고 UNIQUE 제약을 걸었다. 프로그램을 거치지 않고 SQL로 직접 넣어도 DB가 거부한다.
- **대출정지 상태**: 저장하지 않고 뷰 `v_member_status`가 정지 기간·연체 도서·미납 연체료를 보고 조회할 때마다 계산한다.
- **대출 규칙의 위치**: 대출·반납·연장 검사를 저장 프로시저에 모았다. 대출 권수와 기간은 `member_type` 테이블의 데이터다.
- **함께 대출한 책 추천**: 뷰 `v_also_borrowed`가 대출 기록을 회원 기준으로 자기 자신과 조인해 계산한다. 2명 이상이 함께 빌린 책만 보여 주어 한 사람의 대출 기록이 드러나지 않게 했다.

## 데이터베이스

| 종류 | 개수 | 이름 |
|---|---|---|
| 테이블 | 14 | member_type, member, staff, category, publisher, author, book, book_author, book_copy, loan, renewal, fine, suspension, closed_day |
| 뷰 | 4 | v_book_summary, v_loan_detail, v_member_status, v_also_borrowed |
| 함수 | 3 | fn_next_open_day, fn_overdue_days, fn_compensation |
| 트리거 | 2 | trg_member_withdraw_check, trg_book_copy_status_guard |
| 프로시저 | 8 | sp_borrow, sp_return, sp_renew, sp_report_lost, sp_suspend_member, sp_release_suspension, sp_settle_fine, sp_add_closed_day |

대출 규정(숭실대학교 중앙도서관 기준):

| 회원구분 | 대출 권수 | 대출 기간 | 연장 |
|---|---|---|---|
| 학부생 | 10권 | 14일 | 2회 |
| 휴학생 | 5권 | 14일 | 2회 |
| 대학원생 | 15권 | 30일 | 2회 |
| 전임교원 | 50권 | 180일 | 1회 |
| 직원·비전임교원 | 15권 | 30일 | 2회 |

연체 도서가 있으면 반납할 때까지 대출과 연장을 할 수 없고, 연체료는 1권 1일 100원이며 휴관일은 세지 않는다.

## 폴더 구조

```
library-system/
├── sql/
│   ├── 01_schema.sql        # 테이블 14개, 제약조건, 인덱스, 앱 전용 계정
│   ├── 02_programs.sql      # 함수 3, 뷰 4, 트리거 2, 프로시저 8
│   ├── 03_base_data.sql     # 회원구분(대출 정책), 사서, 분류, 휴관일, 회원
│   ├── 04_books.sql         # 도서·복본
│   ├── 05_sample_loans.sql  # 대출·연장·연체료·대출정지 이력
│   ├── demo_control.sql     # 시연용: 상태 변경, 예외 상황, 권한 검증
│   └── demo_app_account.sql # 시연용: 앱 계정(library) 권한 검증
├── data/books.csv           # 실제 도서 100종의 서지정보
├── scripts/                 # DB 초기화(init_db), 도서·대출 데이터 생성, 국립중앙도서관 API 가져오기
├── app/                     # Flask 응용프로그램 (회원, 도서, 대출, 연체, 휴관일, 통계, 회원 포털)
├── tests/test_scenarios.py  # 업무 규칙 통합 테스트 29개
├── dump/library_db_dump.sql # DB 구축 dump
├── deploy/db-server/        # DB 서버 PC 설치 스크립트
├── docker-compose.yml       # 한 PC에서 재현할 때 쓰는 구성
└── Dockerfile
```

## 실행 방법

### 한 PC에서 재현 (Docker)

Docker Desktop만 있으면 된다. MySQL과 Python을 따로 설치할 필요가 없다.

```bash
git clone https://github.com/delboy11/library-system.git
cd library-system
docker compose up -d --build
```

40초쯤 뒤 `http://127.0.0.1:5000` 으로 접속한다. 데이터를 처음 상태로 되돌리려면 `docker compose down -v` 후 `docker compose up -d`.

대출 날짜는 DB를 초기화한 날을 기준으로 만들어지므로, 초기화한 직후에 연체·반납 예정 상황이 그대로 재현된다.

### 발표 구성 (DB 서버 PC + 발표 노트북)

DB 서버 PC에서 MySQL 컨테이너를 띄우고 데이터를 넣는다.

```bash
BIND_IP=<DB 서버의 Tailscale 주소> deploy/db-server/start.sh
deploy/db-server/init.sh
```

발표 노트북에서는 Tailscale에 로그인한 상태로 웹 서버를 실행한다.

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set DB_HOST=<DB 서버의 Tailscale 주소>
.venv\Scripts\python run.py
```

사서 화면 맨 아래에 "브라우저 → 웹 서버 → DB 서버"와 DB 서버의 호스트 이름이 표시된다.

### 환경변수

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `DB_HOST` · `DB_PORT` | 127.0.0.1 · 3306 | DB 서버 주소 |
| `DB_USER` · `DB_PASSWORD` · `DB_NAME` | library · library1234 · library_db | 앱 전용 계정 |
| `APP_HOST` · `APP_PORT` | 127.0.0.1 · 5000 | 웹 서버가 받을 주소 (0.0.0.0 이면 다른 기기에서 접속 가능) |

## 시연 계정

| 용도 | 아이디 | 비밀번호 |
|---|---|---|
| 사서 (관리자) | admin | admin1234 |
| 사서 | lib01 | lib1234 |
| 회원 포털 | 학번·교번 (예: 20231234) | member1234 |
| 앱 → DB | library | library1234 |
| DB 관리자 (Docker 한 PC 구성) | root | root1234 |

## 시연용 SQL

| 파일 | 접속 계정 | 내용 |
|---|---|---|
| `sql/demo_control.sql` | root | 분리 구성 확인, 상태 변경(연체 만들기, 대출 한도 변경, 대출정지), 예외 상황(UNIQUE·CHECK·FK·트리거·프로시저), 권한 검증, 함께 대출한 책 |
| `sql/demo_app_account.sql` | library | 앱 계정은 조회·변경·프로시저 실행만 되고 테이블 생성·삭제는 거부됨 |

## 테스트

```bash
.venv/bin/python -m unittest -v tests.test_scenarios   # DB를 초기화하고 업무 규칙 29개를 검증
```

Docker 구성에서 돌릴 때는 초기화 명령을 `MYSQL_BIN`으로 지정한다.

```bash
MYSQL_BIN="docker compose exec -T -e MYSQL_PWD=root1234 db mysql" \
  .venv/bin/python -m unittest tests.test_scenarios
```

## 국립중앙도서관 API

`NL_CERT_KEY` 환경변수에 발급받은 키를 넣고 실행하면 도서 등록 화면의 ISBN 조회 버튼으로 서지정보를 채울 수 있다.

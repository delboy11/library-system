# 도서관 대출·반납·연체 관리 시스템

데이터베이스 팀 프로젝트. 숭실대학교 중앙도서관 대출 규정을 기준으로 사서용 관리 프로그램과 회원 포털을 만들었다.

| 구분 | 선정 |
|---|---|
| 언어 / 프레임워크 | Python 3 · Flask 3 · PyMySQL |
| DBMS | MySQL 8.4 (8.0.19 이상이면 동작: CHECK 제약·생성 컬럼·행 별칭 구문 사용) |
| DB 서버 | 별도 PC `delboy-metal` (Ubuntu 24.04) 의 **Docker** 컨테이너 (`mysql:8.4`) |
| 네트워크 | **Tailscale** (WireGuard VPN) — 발표 노트북 ↔ DB 서버, DB 포트는 Tailscale 주소에서만 열림 |
| 모델링 도구 | ERDCloud (`sql/01_schema.sql` Import), 문서 내 ERD 는 Mermaid |
| 도서 데이터 | 실제 도서 100종 (`data/books.csv`) · 국립중앙도서관 API 가져오기 스크립트 포함 |

## 시스템 구성 (DB 서버와 클라이언트 분리)

```
[발표 노트북]                                              [DB 서버 PC : delboy-metal]
 브라우저 ──HTTP──▶ 웹 서버 Flask (run.py :5000) ──Tailscale──▶ MySQL 8.4 (Docker) 100.77.2.39:3306
                    계정 library (DML·EXECUTE 만)                  library_db : 테이블·뷰·함수·트리거·프로시저
```

- **논리적 분리**: 화면(템플릿) · 응용(Flask) · 데이터(MySQL). 업무 규칙은 DB 의 프로시저·트리거에 있고, 웹 서버는 권한이 제한된 앱 계정으로 호출만 한다.
- **물리적 분리**: DB 는 다른 PC 에 있다. 사서 화면 맨 아래 줄에 `브라우저 → 웹 서버 → DB 서버(호스트 delboy-metal)` 와 DB 가 본 접속 IP 가 표시된다.
- 결정 이유: [`docs/00_설계_결정사항.md`](docs/00_설계_결정사항.md) 7장, 설치 상세: [`docs/08_물리적_데이터_모델.md`](docs/08_물리적_데이터_모델.md) 13장.

## 화면

- **사서용** `http://127.0.0.1:5000` — 대시보드, 대출, 반납, 대출현황, 도서, 회원, 연체·정지, 연체료, 휴관일, 통계
- **회원 포털** `http://127.0.0.1:5000/my` — 도서 검색, 내 대출 현황, 연장 신청, 연체료·정지 조회, 비밀번호 변경
  (`APP_HOST=0.0.0.0` 으로 실행하면 폰에서 `http://<노트북 IP>:5000/my` 로 접속 가능)

## 폴더 구조

```
library-system/
├── sql/
│   ├── 01_schema.sql        # 테이블 14개, PK/FK/UNIQUE/CHECK, 인덱스, 앱 전용 계정
│   ├── 02_programs.sql      # 함수 3, 뷰 3, 트리거 2, 프로시저 8
│   ├── 03_base_data.sql     # 회원구분(대출 정책), 사서, 분류, 휴관일, 회원
│   ├── 04_books.sql         # 도서·복본 (build_seed.py 생성)
│   ├── 05_sample_loans.sql  # 대출·연장·연체료·정지 이력 (build_seed.py 생성)
│   ├── demo_control.sql     # 시연용: 상태 변경 · 예외 상황 · 권한 검증 (관리자 계정)
│   └── demo_app_account.sql # 시연용: 앱 계정(library) 권한 검증
├── data/books.csv           # 실제 도서 100종 서지정보 (출처 URL 포함)
├── scripts/
│   ├── init_db.sh / .bat    # DB 초기화 (01 → 05 순서 실행, MYSQL_HOST 로 원격 DB 서버 지정 가능)
│   ├── build_seed.py        # books.csv → 04, 대출 이력 → 05
│   ├── import_books.py      # 국립중앙도서관 API → books.csv
│   └── gen_docs.py          # DB 메타데이터 → 용어 사전·도메인 정의서·테이블 기술서
├── app/                     # Flask (blueprint 별 기능 영역)
│   ├── members.py  books.py  loans.py  overdue.py  closed_days.py  stats.py
│   ├── portal.py            # 회원 포털 (/my)
│   ├── nl_api.py            # 국립중앙도서관 API 클라이언트
│   └── db.py                # 연결 풀·트랜잭션·프로시저 호출·오류 메시지 변환
├── docker-compose.yml       # 한 PC 재현: db(MySQL 8.4) + web(Flask) 컨테이너
├── Dockerfile               # web 컨테이너 이미지
├── deploy/db-server/        # DB 서버 PC 용: start.sh(Docker MySQL) · init.sh(초기화) · systemd 단위
├── tests/test_scenarios.py  # 업무 규칙 통합 테스트 28개
└── docs/                    # 보고서 (00 설계 결정 ~ 13 시연 시나리오)
```

## 실행 방법

같은 코드를 두 가지 구성으로 실행한다. 차이는 웹 서버가 접속할 DB 주소(`DB_HOST`) 하나뿐이다.

| 구성 | DB 위치 | 용도 |
|---|---|---|
| 1. 한 PC | 이 PC (Docker 컨테이너 또는 직접 설치한 MySQL) | 누구나 재현 · 발표 비상용 |
| 2. 두 PC (발표) | DB 서버 PC `delboy-metal` (Tailscale) | DB 서버와 클라이언트의 물리적 분리 시연 |

### 1. 한 PC 에서 실행 (재현용)

#### 방법 A. Docker — 명령 한 줄 (권장)

필요한 것: Docker Desktop (Windows · macOS) 또는 Docker Engine + Compose (Linux). MySQL · Python 설치는 필요 없다.

```bash
git clone https://github.com/delboy11/library-system.git
cd library-system
docker compose up -d --build
```

40초 정도 뒤 (처음에는 이미지 내려받는 시간이 더 든다) http://127.0.0.1:5000 사서 `admin` / `admin1234`, http://127.0.0.1:5000/my 회원 `20231234` / `member1234`.

- `db` 컨테이너: MySQL 8.4. 처음 뜰 때 `sql/01 ~ 05` 를 순서대로 실행해 `library_db` 를 만든다. 시간대는 `+09:00` 으로 고정.
- `web` 컨테이너: Flask 웹 서버. 앱 계정 `library` 로 `db` 에 접속한다. 사서 화면 맨 아래에 `웹 서버 library-web → DB 서버 db:3306 · 호스트 library-db` 가 표시된다.
- 설정은 [`docker-compose.yml`](docker-compose.yml) · [`Dockerfile`](Dockerfile) 에 있다.

| 하고 싶은 것 | 명령 |
|---|---|
| 상태 확인 | `docker compose ps` (db · web 둘 다 `healthy` 면 준비 완료. `docker compose up -d --wait` 는 여기까지 기다린다) |
| 웹 서버 로그 | `docker compose logs -f web` |
| 끄기 / 다시 켜기 (데이터 유지) | `docker compose stop` / `docker compose start` |
| **데이터 다시 초기화** | `docker compose down -v` 후 `docker compose up -d` |
| SQL 창 (root) | `docker compose exec db mysql -uroot -proot1234 --default-character-set=utf8mb4 library_db` 또는 Workbench 로 127.0.0.1:3306 · root / root1234 |
| 시연용 SQL (명령 프롬프트 · bash) | `docker compose exec -T db mysql -ulibrary -plibrary1234 --force -t --default-character-set=utf8mb4 library_db < sql/demo_app_account.sql` |
| 3306 · 5000 포트가 이미 쓰이고 있을 때 | bash: `DB_PORT=3307 APP_PORT=5001 docker compose up -d` · 명령 프롬프트: `set DB_PORT=3307` · `set APP_PORT=5001` 후 `docker compose up -d` |
| 모두 지우기 | `docker compose down -v --rmi local` |

#### 방법 B. MySQL 직접 설치

Windows:

1. MySQL 8.4 LTS 설치: dev.mysql.com 의 Windows MSI 설치 파일 → 설치 끝의 MySQL Configurator 에서 root 비밀번호 설정 (MySQL Installer 는 8.0 전용이고, 8.0 은 2026-04 에 지원이 끝났다)
2. Python 3 설치 (설치 화면에서 "Add python.exe to PATH" 체크)
3. 명령 프롬프트에서 프로젝트 폴더로 이동 후 (`DB_HOST` 를 지정하지 않으면 이 PC 의 MySQL)
   ```bat
   scripts\init_db.bat
   python -m venv .venv
   .venv\Scripts\pip install -r requirements.txt
   .venv\Scripts\python run.py
   ```
   `init_db.bat` 은 PATH 에 mysql 이 없으면 `C:\Program Files\MySQL\MySQL Server *\bin` 에서 찾는다.
   (MySQL Workbench 에서 `sql/` 의 다섯 파일을 01 → 05 순서로 열어 실행해도 된다.)

macOS:

```bash
brew install mysql && brew services start mysql
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
./scripts/init_db.sh                      # DB 생성 + 데이터
.venv/bin/python run.py                   # http://127.0.0.1:5000
```

#### 한 PC 구성에서 주의할 점

- 대출 날짜는 **DB 를 초기화한 날 기준**으로 만들어진다. 재현하거나 발표하기 직전에 다시 초기화하면 연체·반납 예정 상황이 그대로 나온다.
- 연체·대출정지 판단은 DB 의 `CURDATE()` 기준이라 DB 시간대가 한국이어야 한다. 직접 설치한 MySQL 은 PC 시계를 따르고, Docker 구성은 `+09:00` 으로 고정해 두었다. (컨테이너 기본값인 UTC 로 두면 오전 9시 전에 날짜가 하루 어긋난다)
- 테스트(`tests/`)를 돌리면 DB 가 초기화된다.

### 2. 발표 구성 : DB 서버(delboy-metal) + 발표 노트북

**DB 서버** — 이미 설치되어 있고 재부팅 시 자동으로 켜진다 (systemd `library-mysql`). 처음 설치할 때만:

```bash
BIND_IP=100.77.2.39 deploy/db-server/start.sh      # MySQL 8.4 컨테이너 (Tailscale 주소에서만 수신)
deploy/db-server/init.sh                           # library_db 생성 + 데이터
```

**발표 직전 데이터 초기화** (노트북에서): `ssh delboy@100.77.2.39 '~/library-system/deploy/db-server/init.sh'`

**발표 노트북 (Windows)** — Tailscale 로그인 상태에서, 프로젝트 폴더의 명령 프롬프트:

```bat
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
set DB_HOST=100.77.2.39
.venv\Scripts\python run.py
```

시작할 때 ` * DB 서버 연결 OK : 100.77.2.39:3306 (호스트 delboy-metal, MySQL 8.4.13, …)` 가 나오면 준비 완료. 폰으로 회원 포털을 보여 주려면 `set APP_HOST=0.0.0.0` 도 지정한다.

네트워크가 안 되면 1 의 한 PC 구성으로 바꾼다 (`DB_HOST` 를 지정하지 않고 실행).

### 환경변수

| 환경변수 | 기본값 | 설명 |
|---|---|---|
| `DB_HOST` · `DB_PORT` | 127.0.0.1 · 3306 | DB 서버 주소 (발표 구성 100.77.2.39) |
| `DB_USER` · `DB_PASSWORD` · `DB_NAME` | library · library1234 · library_db | 앱 전용 계정 |
| `APP_HOST` · `APP_PORT` | 127.0.0.1 · 5000 | 웹 서버가 받을 주소 (0.0.0.0 이면 다른 기기 접속 허용, debug 꺼짐) |

Docker 구성에서 `DB_PORT` · `APP_PORT` 는 이 PC 에 여는 포트 번호로 쓰인다 (컨테이너 안은 3306 · 5000 고정).

## 시연용 SQL (데이터 제어)

| 파일 | 접속 계정 | 내용 |
|---|---|---|
| `sql/demo_control.sql` | root (Workbench: Hostname 100.77.2.39) | 0 분리 확인(`PROCESSLIST` 에 웹 서버 IP) · 2 상태 변경(연체 만들기, 대출 한도 변경, 대출정지) · 3 예외 상황 10가지(UNIQUE·CHECK·FK·트리거·프로시저) · 4 권한(`REVOKE EXECUTE` → 웹 대출 즉시 차단, 사서 역할 변경). 각 절에 되돌리기 포함 |
| `sql/demo_app_account.sql` | library | 앱 계정은 조회·변경·프로시저 실행만 되고 DROP·CREATE·ALTER·트리거 삭제·계정 관리는 거부됨 |

```bash
mysql -h 100.77.2.39 -u library -p --force -t --default-character-set=utf8mb4 library_db < sql/demo_app_account.sql
```

### 계정

| 용도 | 아이디 | 비밀번호 |
|---|---|---|
| 사서 (관리자) | admin | admin1234 |
| 사서 | lib01 | lib1234 |
| 회원 포털 | 학번·교번 (예: 20231234) | member1234 |
| 앱 → DB | library | library1234 (DML·EXECUTE 권한만) |
| DB 관리자 (발표 DB 서버) | root | DB 서버의 `~/.library-db/root_password` (Tailscale 안에서만 접속 가능) |
| DB 관리자 (Docker 한 PC) | root | root1234 (이 PC 의 127.0.0.1 에서만 접속 가능. 바꾸려면 처음 띄울 때 `MYSQL_ROOT_PASSWORD`) |

## 대출 규정 (숭실대학교 중앙도서관 기준)

| 회원구분 | 권수 | 기간 | 연장 |
|---|---|---|---|
| 학부생 | 10 | 14일 | 2회 |
| 휴학생 | 5 | 14일 | 2회 |
| 대학원생 | 15 | 30일 | 2회 |
| 전임교원 | 50 | 180일 | 1회 |
| 직원·비전임교원 | 15 | 30일 | 2회 |

- 연장: **연장한 날부터 대출기간만큼**, 대출 당일 불가, 연체·대출정지·미납 연체료가 있으면 불가
- 연체: 연체 도서가 있으면 추가 대출·연장 불가 (반납하면 해제), 연체료 **1권 1일 100원 (휴관일 제외)**
- 반납예정일이 휴관일(일요일·공휴일·개교기념일)이면 다음 개관일
- 분실: 동일 도서 변상 원칙, 불가 시 정가 × 경과연수 배율 (1.2 / 1.5 / 2 / 3배)
- 회의록의 "대출 기간 15일"은 공식 규정(14일)과 달라 14일을 적용했다 → `member_type.loan_days` 만 바꾸면 변경 가능

자세한 근거와 결정 이유는 [`docs/00_설계_결정사항.md`](docs/00_설계_결정사항.md).

## 국립중앙도서관 API

```bash
export NL_CERT_KEY=발급받은키
.venv/bin/python scripts/import_books.py --refresh      # books.csv 의 ISBN 을 국립중앙도서관 데이터로 갱신
.venv/bin/python scripts/build_seed.py && ./scripts/init_db.sh
```

키를 설정하고 앱을 실행하면 도서 등록 화면의 **ISBN 조회** 버튼으로 서지정보를 자동으로 채울 수 있다.

## 테스트 · 문서 생성

```bash
.venv/bin/python -m unittest -v tests.test_scenarios   # DB 를 초기화하고 업무 규칙 28개 검증
.venv/bin/python scripts/gen_docs.py                   # 09 용어 사전 · 10 도메인 정의서 · 11 테이블 기술서 재생성
```

테스트는 `DB_HOST` 의 DB 를 초기화한다. Docker 구성이나 원격 DB 서버로 돌릴 때는 초기화 명령을 `MYSQL_BIN` 으로 지정한다:

```bash
MYSQL_BIN="docker compose exec -T -e MYSQL_PWD=root1234 db mysql" \
  .venv/bin/python -m unittest tests.test_scenarios          # Docker 구성 (한 PC)
```

```bash
DB_HOST=100.77.2.39 MYSQL_BIN="ssh delboy@100.77.2.39 MYSQL_PWD=\$(cat ~/.library-db/root_password) docker exec -i -e MYSQL_PWD library-mysql mysql" \
  .venv/bin/python -m unittest tests.test_scenarios
```

#!/usr/bin/env bash
# DB 초기화 : 스키마 → 함수·뷰·트리거·프로시저 → 기초 데이터 → 도서 → 대출 이력
# 사용법 : ./scripts/init_db.sh                                  (이 PC 의 MySQL, root 비밀번호 없음)
#          MYSQL_PWD=비밀번호 ./scripts/init_db.sh
#          MYSQL_HOST=100.77.2.39 MYSQL_PWD=비밀번호 ./scripts/init_db.sh   (다른 PC 의 DB 서버)
#          deploy/db-server/init.sh                                (DB 서버 PC 에서, Docker 의 MySQL)
# MYSQL_HOST · MYSQL_TCP_PORT · MYSQL_PWD 는 mysql 클라이언트가 직접 읽는 환경변수다.
# MYSQL_BIN : mysql 클라이언트 명령 (기본 mysql. 예: "docker exec -i -e MYSQL_PWD library-mysql mysql")
set -euo pipefail
cd "$(dirname "$0")/.."

MYSQL_BIN=${MYSQL_BIN:-mysql}
echo "대상 DB 서버: ${MYSQL_HOST:-localhost}:${MYSQL_TCP_PORT:-3306} (library_db 를 지우고 다시 만든다)"
for f in sql/01_schema.sql sql/02_programs.sql sql/03_base_data.sql sql/04_books.sql sql/05_sample_loans.sql; do
  echo ">> $f"
  $MYSQL_BIN -u "${MYSQL_USER:-root}" --default-character-set=utf8mb4 < "$f"
done
echo "완료: library_db 초기화"

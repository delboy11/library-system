#!/usr/bin/env bash
# DB 초기화 : 스키마 → 함수·뷰·트리거·프로시저 → 기초 데이터 → 도서 → 대출 이력
# 사용법 : ./scripts/init_db.sh            (root 비밀번호 없음)
#          MYSQL_PWD=비밀번호 ./scripts/init_db.sh
set -euo pipefail
cd "$(dirname "$0")/.."

for f in sql/01_schema.sql sql/02_programs.sql sql/03_base_data.sql sql/04_books.sql sql/05_sample_loans.sql; do
  echo ">> $f"
  mysql -u "${MYSQL_USER:-root}" --default-character-set=utf8mb4 < "$f"
done
echo "완료: library_db 초기화"

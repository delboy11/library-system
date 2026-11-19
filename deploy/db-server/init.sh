#!/usr/bin/env bash
# DB 서버 PC 에서 library_db 를 초기화한다 (컨테이너 안의 mysql 클라이언트로 sql/01~05 실행).
# 사용법 : deploy/db-server/init.sh
#   다른 PC 에서 : ssh <DB 서버> '~/library-system/deploy/db-server/init.sh'
set -euo pipefail

NAME=${CONTAINER_NAME:-library-mysql}
PW_FILE=${PW_FILE:-$HOME/.library-db/root_password}

MYSQL_PWD=$(cat "$PW_FILE")
export MYSQL_PWD
export MYSQL_BIN="docker exec -i -e MYSQL_PWD $NAME mysql"
exec "$(dirname "$0")/../../scripts/init_db.sh"

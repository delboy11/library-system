#!/usr/bin/env bash
# DB 서버 PC 에서 MySQL 8.4 컨테이너를 만들거나 켠다 (Docker).
# 사용법 : BIND_IP=100.77.2.39 deploy/db-server/start.sh
#   BIND_IP : MySQL 포트(3306)를 열 주소. Tailscale 주소를 주면 같은 tailnet 의 기기만 접속할 수 있다 (기본 127.0.0.1)
#   root 비밀번호는 처음 실행할 때 무작위로 만들어 ~/.library-db/root_password (권한 600) 에 저장한다.
# 시간대 : DB 서버 PC 가 UTC 여도 CURDATE()·NOW() 가 한국 날짜가 되도록 --default-time-zone=+09:00
set -euo pipefail

NAME=${CONTAINER_NAME:-library-mysql}
BIND_IP=${BIND_IP:-127.0.0.1}
PW_FILE=${PW_FILE:-$HOME/.library-db/root_password}

if [ ! -s "$PW_FILE" ]; then
  mkdir -p "$(dirname "$PW_FILE")"
  (umask 077 && openssl rand -base64 24 | tr -d '/+=\n' | cut -c1-24 > "$PW_FILE")
  echo "root 비밀번호를 만들었습니다: $PW_FILE"
fi

# 부팅 직후에는 Tailscale 주소가 아직 없을 수 있으므로 생길 때까지 기다린다 (최대 2분)
if [ "$BIND_IP" != "127.0.0.1" ] && [ "$BIND_IP" != "0.0.0.0" ] && command -v ip >/dev/null; then
  for _ in $(seq 1 60); do
    ip -4 addr | grep -q "inet $BIND_IP/" && break
    sleep 2
  done
fi

if [ "$(docker container inspect -f '{{.State.Running}}' "$NAME" 2>/dev/null)" = "true" ]; then
  echo "이미 실행 중: $NAME"
  exit 0
fi

since=$(date +%s)
if docker container inspect "$NAME" >/dev/null 2>&1; then
  docker start "$NAME" >/dev/null
else
  # --network host : 포트 포워딩(docker-proxy)을 거치지 않아 MySQL 이 접속한 PC 의 실제 IP 를 본다
  #                   (USER() = library@웹서버IP). @@hostname 도 DB 서버 PC 이름이 된다
  # --bind-address  : MySQL 이 BIND_IP 에서만 접속을 받는다 (Tailscale 주소면 tailnet 기기만)
  # 부팅 직후 BIND_IP 가 아직 없으면 mysqld 가 멈추고, --restart 정책이 다시 띄운다
  docker run -d --name "$NAME" --restart unless-stopped \
    --network host \
    -v library-mysql-data:/var/lib/mysql \
    -v "$PW_FILE:/run/secrets/root_password:ro" \
    -e MYSQL_ROOT_PASSWORD_FILE=/run/secrets/root_password \
    -e MYSQL_ROOT_HOST=% \
    -e TZ=Asia/Seoul \
    mysql:8.4 \
    --bind-address="$BIND_IP" --port=3306 --mysqlx=OFF --skip-name-resolve \
    --default-time-zone=+09:00 \
    --character-set-server=utf8mb4 --collation-server=utf8mb4_0900_ai_ci >/dev/null
fi

# 접속을 받을 준비가 될 때까지 기다린다 (처음 만들 때는 초기화로 30초쯤 걸린다)
for _ in $(seq 1 90); do
  if docker logs --since "$since" "$NAME" 2>&1 | grep -q "ready for connections.*port: 3306"; then
    echo "MySQL 준비 완료: $NAME → $BIND_IP:3306"
    exit 0
  fi
  sleep 2
done
echo "MySQL 이 3분 안에 준비되지 않았습니다. docker logs $NAME 으로 확인하세요." >&2
exit 1

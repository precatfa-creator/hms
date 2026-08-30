#!/usr/bin/env bash
# Control the isolated studbook cluster. Runs as the current user, no root:
# the system PostgreSQL on 5432 is never touched.
#
#   ./pg.sh start | stop | status | psql | reset
set -euo pipefail

PGROOT=/home/omix/pgstudbook
BIN=/usr/lib/postgresql/16/bin
HERE="$(cd "$(dirname "$0")" && pwd)"

case "${1:-status}" in
	start)  "$BIN/pg_ctl" -D "$PGROOT/data" -l "$PGROOT/server.log" start ;;
	stop)   "$BIN/pg_ctl" -D "$PGROOT/data" stop ;;
	status) "$BIN/pg_isready" -h 127.0.0.1 -p 5433 ;;
	psql)   PGPASSWORD=studbook_dev_pw "$BIN/psql" -h 127.0.0.1 -p 5433 \
	                -U studbook_app -d studbook_legacy ;;
	reset)  PGPASSWORD=studbook_dev_pw "$BIN/psql" -h 127.0.0.1 -p 5433 \
	                -U studbook_app -d studbook_legacy -v ON_ERROR_STOP=1 -f "$HERE/schema.sql" ;;
	*)      echo "usage: $0 {start|stop|status|psql|reset}" >&2; exit 1 ;;
esac

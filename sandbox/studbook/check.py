#!/usr/bin/env python3
"""Sanity-check the sandbox Postgres before the bridge is pointed at it.

	/home/omix/frappe-bench/env/bin/python check.py

Checks the schema is complete and that the role the bridge will use cannot
write. Says nothing about row counts: the data is filled in by hand.
"""

import psycopg2

RO = dict(host="127.0.0.1", port=5433, dbname="studbook_legacy",
          user="studbook_ro", password="studbook_ro_pw")

TABLES = {"horse", "horse_owner", "ownership_log", "name_log",
          "revinfo", "horse_aud", "ownership_log_aud", "name_log_aud"}


def main():
	connection = psycopg2.connect(**RO)
	cursor = connection.cursor()

	cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
	found = {row[0] for row in cursor.fetchall()}
	assert TABLES <= found, f"missing tables: {TABLES - found}"

	# audit rows must always join to a revision, however the data got in
	for table in ("horse_aud", "ownership_log_aud", "name_log_aud"):
		cursor.execute(f"SELECT count(*) FROM {table} a "
		               f"LEFT JOIN revinfo r USING (rev) WHERE r.rev IS NULL")
		assert cursor.fetchone()[0] == 0, f"{table} has rows with no revision"

	try:
		cursor.execute("UPDATE horse SET name_en = 'nope'")
	except psycopg2.errors.InsufficientPrivilege:
		connection.rollback()
	else:
		raise AssertionError("studbook_ro can write, the grant is wrong")

	cursor.execute("SELECT count(*) FROM horse")
	print(f"OK  {len(TABLES)} tables present, role is read-only, {cursor.fetchone()[0]} horses")
	connection.close()


if __name__ == "__main__":
	main()

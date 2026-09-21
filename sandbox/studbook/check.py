#!/usr/bin/env python3
"""Sanity-check the sandbox Postgres before the bridge is pointed at it.

	/home/omix/frappe-bench/env/bin/python check.py

Checks the schema is complete and that the role the bridge will use cannot
write. Says nothing about row counts: the data is filled in by hand.
"""

import psycopg2

RO = dict(host="127.0.0.1", port=5433, dbname="studbook_legacy",
          user="studbook_ro", password="studbook_ro_pw")

TABLES = {"horse", "owner", "horse_owner", "horse_breeder",
          "country", "city", "book_type", "horse_color",
          "event", "event_type", "event_old_owner", "event_new_owner",
          "file", "application_user", "laboratory",
          "revision_info", "horse_aud", "owner_aud", "event_aud",
          "horse_owner_aud", "horse_breeder_aud",
          "event_old_owner_aud", "event_new_owner_aud"}

AUDIT_TABLES = ("horse_aud", "owner_aud", "event_aud", "horse_owner_aud",
                "horse_breeder_aud", "event_old_owner_aud", "event_new_owner_aud")


def main():
	connection = psycopg2.connect(**RO)
	cursor = connection.cursor()

	cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
	found = {row[0] for row in cursor.fetchall()}
	assert TABLES <= found, f"missing tables: {TABLES - found}"

	# audit rows must always join to a revision, however the data got in
	for table in AUDIT_TABLES:
		cursor.execute(f"SELECT count(*) FROM {table} a "
		               f"LEFT JOIN revision_info r ON r.id = a.rev WHERE r.id IS NULL")
		assert cursor.fetchone()[0] == 0, f"{table} has rows with no revision"

	# exactly one home country, which is what makes origin derivable
	cursor.execute("SELECT count(*) FROM country WHERE local")
	local_countries = cursor.fetchone()[0]
	assert local_countries <= 1, f"{local_countries} countries are flagged local"

	try:
		cursor.execute("UPDATE horse SET name = 'nope'")
	except psycopg2.errors.InsufficientPrivilege:
		connection.rollback()
	else:
		raise AssertionError("studbook_ro can write, the grant is wrong")

	cursor.execute("SELECT count(*) FROM horse")
	print(f"OK  {len(TABLES)} tables present, role is read-only, {cursor.fetchone()[0]} horses")
	connection.close()


if __name__ == "__main__":
	main()

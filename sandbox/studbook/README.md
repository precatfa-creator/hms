# Legacy studbook sandbox

A throwaway PostgreSQL standing in for the legacy studbook, so the Frappe
bridge can be developed against something real before the actual system exists.

It is a user-owned cluster created with `initdb` — no root, no Docker, and the
system PostgreSQL on 5432 is never touched. Deleting `/home/omix/pgstudbook`
removes every trace of it.

|             |                                        |
| ----------- | -------------------------------------- |
| host / port | `127.0.0.1:5433`                       |
| database    | `studbook_legacy`                      |
| data dir    | `/home/omix/pgstudbook/data`           |
| log         | `/home/omix/pgstudbook/server.log`     |
| owner role  | `studbook_app` / `studbook_dev_pw`     |
| bridge role | `studbook_ro` / `studbook_ro_pw` (SELECT only) |

Sandbox credentials, committed on purpose. The real connection details belong
in `site_config.json` and never in the repo.

## Use

```bash
./pg.sh start | stop | status   # the cluster does not survive a reboot
./pg.sh psql                    # a shell as the owner, for filling tables
./pg.sh reset                   # drop and recreate every table, empty
python3 check.py                # schema is complete and studbook_ro cannot write
```

`check.py` wants the bench interpreter, which already has psycopg2:
`/home/omix/frappe-bench/env/bin/python check.py`

## Schema

`schema.sql` is the whole definition. Tables are empty by design — fill them by
hand.

`horse` carries the identity, pedigree, owner and breeder columns, named to
match the Frappe `Horse` fieldnames so the bridge can select them without
aliasing. `horse_owner` is the owner directory; `ownership_log` and `name_log`
are the child-table equivalents.

The audit side follows Hibernate Envers defaults: every audited table has a
`_aud` twin holding `rev` and `revtype` beside the mirrored columns, and one
`revinfo` table holds the revision clock.

```
revtype   0 = ADD   1 = MOD   2 = DEL
revtstmp  epoch milliseconds
```

Filling `_aud` rows by hand is only worth it for horses whose history you want
to test against; current-state reads never look at them.

## Caveat

The column names here are a guess at what the real system will use. When its
DDL turns up, the aliases needed to absorb the difference belong in the
bridge's SELECT statements — one place, nothing downstream of it moves.

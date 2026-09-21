# StudLib sandbox

A throwaway PostgreSQL carrying the StudLib schema, so the Frappe sync can be
developed against something real before the actual system is reachable.

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

Fill it with the sample data — four horses, three owners, four events:

```bash
PGPASSWORD=studbook_dev_pw /usr/lib/postgresql/16/bin/psql \
	-h 127.0.0.1 -p 5433 -U studbook_app -d studbook_legacy \
	-f sample_data.sql
```

It truncates first, so a second run replaces its rows rather than doubling
them.

## Schema

`schema.sql` is the whole definition. Column names, types and enum values come
straight from `docs/Database_Specification_1.01.pdf`, including the CHECK
constraints on the breed, sex and status enums and the partial unique index
that allows exactly one `local` country.

It is a **subset** — the tables HMS actually reads, plus enough audit
scaffolding to prove the shape:

| Group | Tables |
| ----- | ------ |
| Core | `horse`, `country`, `city`, `book_type`, `horse_color` |
| Ownership | `owner`, `horse_owner`, `horse_breeder` |
| Events | `event`, `event_type`, `event_old_owner`, `event_new_owner` |
| Files | `file` |
| Supporting | `application_user`, `laboratory` |
| Views | `vhorse`, `vhorse_event` |

Left out because nothing here reads them: `covering_agreement`,
`covering_certificate`, `covering_result`, `season`, `laboratory_test*`, the
~24 horse marking collection tables, `refresh_token`, `token_blacklist`,
`email_log`, `forbidden_name`, `studbook_generation_task`.

A horse is identified by `uuid`, not `registry_id` — an unregistered foal has
no registry id yet, which is why `sample_data.sql` ships one.

The audit side follows Hibernate Envers defaults: every audited table has a
`_aud` twin holding `rev` and `revtype` beside the mirrored columns, and one
`revision_info` table holds the revision clock.

```
revtype            0 = ADD   1 = MOD   2 = DEL
revision_timestamp epoch milliseconds
custom_timestamp   the readable one
```

Filling `_aud` rows by hand is only worth it for horses whose history you want
to test against; neither the sync nor the event poll reads them.

## Grants

`./pg.sh reset` drops and recreates the tables, which takes their privileges
with them. `schema.sql` re-grants `SELECT` to `studbook_ro` at the end, so a
reset cannot lock the sync out. Adding a table by hand means granting it
yourself, or just running `reset` again.

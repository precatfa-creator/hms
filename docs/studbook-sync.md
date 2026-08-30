# Studbook Sync

How horses get from the legacy studbook database into this Frappe site, how to
run and schedule it, and how to keep the development sandbox alive.

---

## What this is

The studbook is the system of record for horses: identity, pedigree, ownership.
It is a PostgreSQL database with Hibernate Envers audit tables. Frappe holds the
same horses plus the things the studbook knows nothing about — scanned
documents, completion status, the registration and change forms.

The sync reads the studbook and writes Horses. It never writes back. Roughly:

```
PostgreSQL                 hms/api/legacy_sync.py                 Frappe
  horse            ──▶  read-only SELECT, upsert by  ──▶  Horse
  ownership_log         registration number                Horse Ownership Log
  name_log                                                 Horse Name Log
```

The real studbook does not exist yet, so a sandbox Postgres stands in for it.
Everything below applies unchanged when the real one arrives: point HMS Settings
at it and, if its column names differ, adjust the `COLUMNS` map in
`hms/api/legacy_sync.py`.

### Who owns what

This is the rule that makes the sync safe to run repeatedly.

| The studbook owns                           | Frappe owns                              |
| ------------------------------------------- | ---------------------------------------- |
| names, UELN, microchip, origin, sex, colour  | every `doc_*` attachment and its dates   |
| breed, dates and places of birth, location   | `status` (derived from the documents)    |
| life status, sire and dam blocks             | `registration_form` link                 |
| owner and breeder blocks                     |                                          |
| ownership and name history tables            |                                          |

The sync only writes the left column. A re-sync cannot cost anyone an upload.

---

## Running a sync

**HMS Settings** → `Test Connection`, then `Sync Horses Now`.

`Test Connection` reads a row count and nothing else. Use it after changing any
connection detail — it fails in a second, where a sync would make you wait.

`Sync Horses Now` reads every horse and reports what it did:

| Count       | Meaning                                                     |
| ----------- | ----------------------------------------------------------- |
| Created     | new to this site, inserted                                   |
| Updated     | already here, and something the studbook owns had changed    |
| Unchanged   | already here, nothing to do                                  |
| Failed      | that horse errored; the rest still synced                    |

**Running it twice is safe.** The legacy registration number is the Horse's
docname, so the second run finds every horse and updates rather than duplicating.
A run that changes nothing reports everything as Unchanged.

An `Outcome` of `Partial` means some horses failed and some succeeded. The first
five failures are named in the message; the rest are in **Error Log**.

### Sync History

The last twenty runs, newest first: time, user, counts, duration, outcome. The
summary of the most recent one also appears as a headline at the top of the
form, coloured by outcome.

---

## Scheduling

**HMS Settings** → **Scheduled Sync**.

| Frequency | Asks for      | Runs                          |
| --------- | ------------- | ----------------------------- |
| Never     | —             | not at all                    |
| Hourly    | —             | on the hour                   |
| Daily     | a time        | every day at that time        |
| Weekly    | a day, a time | that weekday, at that time    |
| Monthly   | a day, a time | that day of the month         |

Times are server time. **Next Sync** shows when it will next fire; save before
believing it.

Day of the month is capped at 28 so a monthly sync can never skip February.

### How it works underneath

`hooks.py` registers one scheduled job, `hms.api.legacy_sync.scheduled_sync`.
Saving HMS Settings rewrites that job's cron expression, or stops the job when
the frequency is Never. Frappe's own scheduler decides when to run it, refuses
to queue it twice, and logs every run — none of that is reimplemented here.

Two consequences worth knowing:

- The schedule is stored on the **Scheduled Job Type**, not only in Settings.
  `/app/scheduled-job-type` shows the live cron; the run history is at
  `/app/scheduled-job-log`. Both are linked from the form.
- A scheduled run belongs to Administrator, and appears in Sync History as such.

If nothing fires, check the scheduler is enabled for the site:

```bash
bench --site losand.local doctor            # scheduler status
bench --site losand.local enable-scheduler  # if it is off
```

---

## The development sandbox

A throwaway PostgreSQL standing in for the legacy studbook. It is a user-owned
cluster made with `initdb` — no root, no Docker — so the system PostgreSQL on
port 5432 is never touched.

|             |                                                |
| ----------- | ---------------------------------------------- |
| host / port | `127.0.0.1:5433`                               |
| database    | `studbook_legacy`                              |
| data        | `/home/omix/pgstudbook/data`                   |
| log         | `/home/omix/pgstudbook/server.log`             |
| owner       | `studbook_app` / `studbook_dev_pw`             |
| read-only   | `studbook_ro` / `studbook_ro_pw`               |
| scripts     | `apps/hms/sandbox/studbook/`                   |

Sandbox credentials, in the repo on purpose. Real ones belong in HMS Settings,
where the password field is encrypted, and nowhere else.

### After a reboot

The cluster does not start on its own. WSL or the machine going down leaves the
data intact and the server stopped:

```bash
/home/omix/frappe-bench/apps/hms/sandbox/studbook/pg.sh start
```

That is the whole recovery. Confirm with `./pg.sh status`, which should say
`accepting connections`.

A scheduled sync that fires while the cluster is down fails and records a
`Failed` row. Nothing is lost, but the failure is real — start the cluster
before relying on the schedule.

To have it start by itself, add to `~/.bashrc`:

```bash
pgrep -f 'postgres.*pgstudbook' >/dev/null || \
	/home/omix/frappe-bench/apps/hms/sandbox/studbook/pg.sh start >/dev/null
```

### Everyday commands

```bash
cd /home/omix/frappe-bench/apps/hms/sandbox/studbook

./pg.sh start | stop | status
./pg.sh psql                  # a shell as the owner
./pg.sh reset                 # drop and recreate every table, empty

/home/omix/frappe-bench/env/bin/python check.py
```

`check.py` asserts the schema is complete, that no audit row is missing its
revision, and that the read-only role genuinely cannot write.

### Filling it with data

`sample_data.sql` has two horses, two owners, both child tables and a two
revision audit trail. It is re-runnable — a second run replaces its rows rather
than doubling them.

```bash
PGPASSWORD=studbook_dev_pw /usr/lib/postgresql/16/bin/psql \
	-h 127.0.0.1 -p 5433 -U studbook_app -d studbook_legacy \
	-f sample_data.sql
```

Or open it in a GUI. **DBeaver** on the Windows side is the easiest: WSL2
forwards localhost, so `localhost:5433` connects with no further setup. Install
it on Windows rather than in WSL — no X server needed.

One DBeaver trap: a file opened through `File → Open` is not attached to a
connection and fails with *No active connection*. Either pick the database from
the toolbar dropdown first, or open scripts by right-clicking the connection →
`SQL Editor` → `New SQL script`.

Only the required columns need filling: `registration_no`, `name_ar`, `name_en`,
`origin`, `gender`. Everything else is optional.

### Browsing it

In DBeaver, double-click a table and use the **Data** tab — Properties shows the
schema, not the rows. `horse` has 47 columns, so press **Tab** to switch the grid
to record view.

From a terminal:

```bash
./pg.sh psql
```
```
\dt                list tables
\d horse           columns
\x on              vertical output, worth it for horse
SELECT registration_no, name_en, current_location FROM horse;
```

---

## The audit tables

The studbook keeps history the way Hibernate Envers does: every audited table
has a `_aud` twin, and one `revinfo` table holds the revision clock.

```
revtype   0 = ADD   1 = MOD   2 = DEL
revtstmp  epoch milliseconds
```

Reading one horse's history:

```sql
SELECT a.rev, a.revtype, a.current_location, a.owner_name_en,
       to_timestamp(r.revtstmp / 1000)::date AS changed_on
FROM horse_aud a
JOIN revinfo r USING (rev)
JOIN horse h ON h.id = a.id
WHERE h.registration_no = 'LY-2026-00001'
ORDER BY a.rev;
```

**The sync does not read these tables.** It takes current state from `horse`,
and the ownership and name history from `ownership_log` and `name_log`, which
are ordinary tables. The `_aud` tables are there because the real studbook will
have them.

Nothing fills `_aud` automatically in the sandbox — no triggers. Inserting into
`horse` by hand leaves `horse_aud` empty, which is fine unless you are testing
history. `sample_data.sql` shows the pattern: a `revinfo` row first, because
`horse_aud.rev` is a foreign key to it.

---

## Where things live

| Path                                             | What                                  |
| ------------------------------------------------ | ------------------------------------- |
| `hms/api/legacy_sync.py`                         | the sync, the cron logic, `COLUMNS`   |
| `hms/hms/doctype/hms_settings/`                  | the settings single doctype           |
| `hms/hms/doctype/studbook_sync_log/`             | one row of sync history               |
| `hms/hooks.py`                                   | registers the scheduled job           |
| `sandbox/studbook/`                              | the sandbox: schema, scripts, samples |
| `hms/api/studbook.py`                            | the older type-ahead bridge, separate |

### Two whitelisted methods

Both are System Manager only.

```python
hms.api.legacy_sync.test_connection()  # {"horses": 2}
hms.api.legacy_sync.sync_horses()      # counts and outcome
```

---

## When the real studbook arrives

1. Fill its host, database and read-only user into HMS Settings.
2. If its column names differ from the sandbox, edit `COLUMNS` in
   `hms/api/legacy_sync.py`. That map is the only place the names appear.
3. `Test Connection`, then `Sync Horses Now` on a copy of the site first.

Ask for a **read-only** database user. The sync never writes, and a role that
cannot write is a guarantee rather than a promise.

---

## Troubleshooting

| Symptom                                    | Cause and fix                                                                 |
| ------------------------------------------ | ----------------------------------------------------------------------------- |
| *The studbook connection is turned off*    | `Enabled` is unchecked in HMS Settings.                                        |
| Connection refused on 5433                 | Sandbox cluster is down. `./pg.sh start`.                                       |
| *No active connection* in DBeaver          | The SQL editor has no database selected. Pick one in the toolbar.               |
| Sync reports everything Unchanged          | Correct, if nothing changed in the studbook. Edit a row there and re-run.       |
| Outcome `Partial`                          | Some horses errored — see the message, then **Error Log** for the rest.         |
| Scheduled sync never fires                 | Scheduler off (`bench doctor`), frequency is Never, or the job is stopped.      |
| Workspace edits do not appear after migrate | Bump `modified` in the workspace JSON; migrate skips files older than the DB.   |

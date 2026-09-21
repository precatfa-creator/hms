# Studbook Sync

How horses get from the StudLib studbook database into this Frappe site, how to
run and schedule it, and how to keep the development sandbox alive.

Documents and events are in [documents-and-events.md](documents-and-events.md).

---

## What this is

StudLib is the system of record for horses: identity, pedigree, ownership.
It is a PostgreSQL database with Hibernate Envers audit tables, described in
`docs/Database_Specification_1.01.pdf`. Frappe holds the same horses plus the
things StudLib knows nothing about — scanned documents, completion status, the
registration and change forms.

The sync reads StudLib and writes Horses. It never writes back.

```
PostgreSQL                    hms/api/legacy_sync.py               Frappe
  country, horse_color   ──▶  mirrored first, so the        ──▶  Studbook Country
  book_type, owner            Horse has something to Link        Horse Color
                              at                                 Book Type
                                                                 Horse Owner

  horse + its joins      ──▶  read-only SELECT, upsert      ──▶  Horse
  horse_owner                 keyed on the studbook uuid         Horse Party
  horse_breeder                                                  (owners, breeders)
```

**The key is `uuid`, not the registry number.** A foal exists in StudLib as
`NEW_FOAL` long before it is given a `registry_id`, so the registry number
cannot identify a horse. `Horse.studbook_uuid` carries StudLib's `uuid` and is
what a second run matches on; the docname stays a naming series.

The real studbook is not reachable yet, so a sandbox Postgres carrying the same
schema stands in for it. Everything below applies unchanged when the real one
arrives: point HMS Settings at it.

### Who owns what

This is the rule that makes the sync safe to run repeatedly.

| StudLib owns                                      | Frappe owns                          |
| ------------------------------------------------- | ------------------------------------ |
| names, UELN, registry ids, microchip, sex, colour  | every Horse Document                 |
| breed, strain, classification, `status`            | `documents_status`                   |
| all seven dates, studbook volume and page          | the paper forms                      |
| sire and dam, owners and breeders                  | Horse Events after they are created  |
| birthplace, import and export country              |                                      |

The sync only writes the left column; `FRAPPE_OWNED` in `legacy_sync.py` names
the exceptions. A re-sync cannot cost anyone an upload.

### Two fields that are not what they look like

| Field | What it is |
| ----- | ---------- |
| `status` | StudLib's **registration workflow** — New Foal, Waiting for Laboratory, Register in Studbook, Rejected, External. It used to hold our document tally; that moved to `documents_status`. |
| `origin` | Derived, not stored. StudLib has no origin column: a horse whose birthplace country is flagged `Local` is Local, anything else is Imported. Read-only on the form. |

Likewise `life_status` is derived from `date_of_death`.

### The two deliberate aliases

StudLib's `name` is the official registered name and `local_name` is the local
spelling. Frappe uses `name` for the docname, and the whole app — print formats,
paper forms, the type-ahead — is built on `name_en` / `name_ar`. So:

| StudLib      | Horse     |
| ------------ | --------- |
| `name`       | `name_en` |
| `local_name` | `name_ar` |

Every other column carries its StudLib name. `COLUMNS` in
`hms/api/legacy_sync.py` is the whole map.

---

## Running a sync

**HMS Settings** → `Test Connection`, then `Sync Horses Now`.

`Test Connection` reads a row count and nothing else. Use it after changing any
connection detail — it fails in a second, where a sync would make you wait.

`Sync Horses Now` mirrors the reference tables, then reads every horse and
reports what it did:

| Count       | Meaning                                                     |
| ----------- | ----------------------------------------------------------- |
| Created     | new to this site, inserted                                   |
| Updated     | already here, and something the studbook owns had changed    |
| Unchanged   | already here, nothing to do                                  |
| Failed      | that horse errored; the rest still synced                    |

**Running it twice is safe.** The second run finds every horse by its
`studbook_uuid` and updates rather than duplicating. A run that changes nothing
reports everything as Unchanged.

Sire and dam are resolved in a second pass, because a foal can be read before
its parents are in the site. A parent StudLib does not hold — a foreign sire,
say — stays in the flat `sire_*` / `dam_*` block with no Link, which is what
those fields are still there for.

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

A horse's NOT NULL columns are `name`, `breed`, `sex`, `status` and `uuid`;
everything else is optional. `breed`, `sex` and `status` carry CHECK
constraints, so a typo is rejected rather than synced.

### Browsing it

In DBeaver, double-click a table and use the **Data** tab — Properties shows the
schema, not the rows. `horse` is wide, so press **Tab** to switch the grid to
record view.

From a terminal:

```bash
./pg.sh psql
```
```
\dt                list tables
\d horse           columns
\x on              vertical output, worth it for horse
SELECT registry_id, name, sex, status FROM horse;
SELECT * FROM vhorse;          -- origin LOCAL/IMPORTED, colour name, offspring
```

---

## The audit tables

StudLib keeps history the way Hibernate Envers does: every audited table has a
`_aud` twin, and one `revision_info` table holds the revision clock.

```
revtype            0 = ADD   1 = MOD   2 = DEL
revision_timestamp epoch milliseconds
custom_timestamp   the readable one, indexed DESC
```

Reading one horse's history:

```sql
SELECT a.rev, a.revtype, a.status, a.registry_id, r.custom_timestamp, r.username
FROM horse_aud a
JOIN revision_info r ON r.id = a.rev
JOIN horse h ON h.id = a.id
WHERE h.registry_id = 'AH-2001'
ORDER BY a.rev;
```

**Neither the sync nor the event poll reads these tables.** Current state comes
from `horse`, ownership from `horse_owner` and `horse_breeder`, and new events
from `event`. The `_aud` tables are mirrored here because the real studbook has
them, and because they are the only place an *edited* or *deleted* event would
show up — see the limitation noted in
[documents-and-events.md](documents-and-events.md).

Nothing fills `_aud` automatically in the sandbox — no triggers. Inserting into
`horse` by hand leaves `horse_aud` empty, which is fine unless you are testing
history. `sample_data.sql` shows the pattern: a `revision_info` row first,
because `horse_aud.rev` is a foreign key to it.

---

## Where things live

| Path                                             | What                                  |
| ------------------------------------------------ | ------------------------------------- |
| `hms/api/legacy_sync.py`                         | the sync, the cron logic, `COLUMNS`   |
| `hms/api/events.py`                              | the event poll and its watermark      |
| `scripts/gen_doctypes.py`                        | every doctype JSON is generated here  |
| `hms/hms/doctype/hms_settings/`                  | the settings single doctype           |
| `hms/hms/doctype/studbook_sync_log/`             | one row of sync history               |
| `hms/hooks.py`                                   | registers the scheduled job           |
| `sandbox/studbook/`                              | the sandbox: schema, scripts, samples |
| `hms/api/studbook.py`                            | the older type-ahead bridge, separate |

### Two whitelisted methods

Both are System Manager only.

```python
hms.api.legacy_sync.test_connection()  # {"horses": 4}
hms.api.legacy_sync.sync_horses()      # counts and outcome
hms.api.events.poll_events()           # new events, and the watermark reached
```

---

## When the real studbook arrives

1. Fill its host, database and read-only user into HMS Settings.
2. `Test Connection`, then `Sync Horses Now` on a copy of the site first.
3. Then turn on **Poll Studbook Events**, leaving *Backfill Past Events* off
   unless you want a notification for every event in the system's history.

The sandbox schema is taken from the specification, so `COLUMNS`, `HORSE_SQL`
and `PARTIES_SQL` should need no edits. If the real database differs, those
three are the only places the column names appear.

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

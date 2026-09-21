# Documents and Events

Two things that used to be fields on the Horse and are now records of their own:
the scanned documents a horse carries, and the lifecycle events the studbook
records against it.

For how horses themselves get here, see [studbook-sync.md](studbook-sync.md).

---

## Documents

### What changed

A document used to be an `Attach` field on the Horse — `doc_passport`,
`doc_owner_id` and eleven more — with its date or certificate number in the
field beside it. One upload per category, forever, and the list of categories
was compiled into `documents.py`.

It is now a **Horse Document**: one record per uploaded document, hanging off
the Horse on the Connections tab. A horse can hold as many as the category
allows — several Owner IDs, one per co-owner; a covering certificate per season.

The Documents tab is gone from the Horse form. The rollup it produced is still
there as `documents_status`.

### Three doctypes

```
Horse Document Category  ── the rules: who needs it, how many, what details
        │
        └── Horse Document  ── one uploaded file, against one horse
                    │
                    └── Horse  ── documents_status rolls up from these
```

### The category is the control panel

Everything the old code decided is now a field on **Horse Document Category**:

| Section | Controls |
| ------- | -------- |
| **Applies To** | Local and/or Imported, and whether it is *required* for each. Sex (All / Males / Females), breed, country of origin. |
| **Limits** | `Maximum Uploads` — how many a horse may carry. **0 means no limit.** Whether the document expires. |
| **Required Details** | Which of the five detail fields the document must carry, and what to call two of them. |

"Males" covers Male, Stallion, Gelding, Cryptorchid and Monorchid; "Females"
covers Female and Broodmare. That split is there because the documents mapping
asks for a Covering **Certificate** from a female/broodmare and a Covering
**Agreement** from a male/stallion.

A category set to **Disabled** applies to nobody — including for the purpose of
being required.

### The five detail fields

Every category in the mapping needs one of five shapes, so Horse Document
carries all five and the category decides which are shown and required:

| Field | Used by |
| ----- | ------- |
| `document_date` | Date of Registration, Marking Date, Date of Export, Date of the Event |
| `reference_no` | Certificate Number, Passport Number, Marked By (Doctor) |
| `doc_status` | DNA Result — Approved / Declined |
| `season` | Covering Certificate, Covering Agreement |
| `notes` | Others |

`document_date` and `reference_no` take their labels from the category, so
"Date" reads as "Marking Date" on a Marking and "Date of Export" on an Export
Certificate.

This is deliberately not a form builder. If a category ever needs a sixth
shape, add the field here rather than building one.

### Complete, and the status rollup

A document is **complete** when it has its attachment *and* every detail its
category asks for. An attachment on its own is not a document.

`Horse.documents_status` is then:

| | |
| --- | --- |
| **Not Yet** | none of the required categories has a complete document |
| **Partially Completed** | some do |
| **Completed** | all of them do |

Only *required* categories count. Uploading five optional documents leaves a
horse at Not Yet.

An **incomplete document is allowed to exist** — the form marks the missing
detail as required, but the server lets it save. That is what makes it possible
to raise a document from an event before the paper has arrived.

### What is shipped

`hms/fixtures/horse_document_category.json` holds the thirteen categories from
the documents mapping, with the starred ones marked required per origin. They
are ordinary records: edit them in the Desk, and the change takes effect on the
next save of any horse.

### Adding a category

1. **Horse Document Category → New.**
2. Name it, tick which origins it applies to and which of those require it.
3. Set `Maximum Uploads` (0 for no limit).
4. Tick the details it must carry.

No deploy, no code change. The rules are read through a cache that clears
itself whenever a category is saved.

---

## Events

### An event is a notice, not a state

StudLib records a DEATH event *and* writes `horse.date_of_death`. An EXPORT
event *and* `date_of_exporting`. A CHANGE_OWNER event *and* a rewritten
`horse_owner`. The horse sync already carries all of that.

So nothing in the event pipeline writes to the Horse. An event exists to **raise
a notification** and to **start the paperwork**. The two pipelines stay
independent — an event handled wrongly cannot corrupt a horse record.

### How events get here

StudLib is a Java application we hold read-only Postgres on: no webhook, no
LISTEN/NOTIFY. So `hms/api/events.py` polls, on Frappe's hourly slot.

**The poll looks back, on purpose.** Postgres hands out sequence values before
a transaction commits, so a transaction holding event 500 can commit *after*
one holding 505. A plain `WHERE id > watermark` reads 505, moves the watermark
past 500, and 500 is never seen again. The query therefore re-reads a window of
200 ids below the watermark and drops anything already here. Re-reading is
cheap; a lost change of owner is not.

### First run

Turning **Poll Studbook Events** on and polling sets the watermark to the newest
event and imports nothing — otherwise a system with years of history would fire
a notification per row.

To take the history instead, tick **Backfill Past Events** before the first
poll. Every past event is imported, each with its own notification.

### Notifications

A new Horse Event writes a Frappe **Notification Log** entry for everyone
holding the role on the event's action row, falling back to **Notify Role** in
HMS Settings. It is Frappe's own bell — there is no second notification system
to maintain.

Administrator is never notified, so on a site whose only System Manager is
Administrator no notification appears. That is the cause, not a bug in the poll.

### Turning an event into paperwork

Open the event and press **Create Transaction**. What that makes comes from the
**Event Actions** table in HMS Settings — one row per event type, naming a form
to create, a document category to raise, or both:

| Event | Creates, by default |
| ----- | ------------------- |
| CHANGE_OWNER | an Owner Change Form, prefilled with the new owner, plus an Owner Change Form document |
| DEATH | a Death Form document |
| EXPORT | an Export Certificate document |
| NEW_FOAL | a Registration Form for Local Horses |
| IMPORT | a Passport document |
| GELDING, COVERED, FOAL_ABORTION | nothing; the event is recorded and that is all |

Change any row and the next event follows the new rule. No deploy.

The event is then marked **Processed** and links to what it produced;
`Acknowledge` and `Ignore` are there for the events that need no paperwork.

### An event that arrives before its horse

A foal can be registered in StudLib and its NEW_FOAL event read here before the
next horse sync has brought the foal over. The event is stored with no horse
link and its studbook uuid in `unresolved_horse`, and the form says so. The next
horse sync calls `resolve_unlinked()` and fills the link in.

### What the poll does not see

Only **new** events. An event edited or deleted in StudLib afterwards is not
picked up — that would mean reading `event_aud` and `revision_info` instead, and
create-only is enough for the paperwork this drives. If edits start mattering,
that is where to look.

---

## Two traps worth knowing

Both cost a debugging session here.

**A DocType name is global.** Two apps shipping a DocType of the same name does
not error — the later migrate silently replaces the other app's definition.
`Country` briefly ate `frappe/geo`'s, which is why the doctype is called
**Studbook Country**. `scripts/gen_doctypes.py` now refuses a name another app
already uses.

**Some fieldnames are Frappe's.** A Link field named `owner` is filled with the
session user; one named `country` is filled from the system default. Neither
errors — the row just quietly carries the wrong value, and the sync then sees a
difference on every run. Hence `party`, `owner_country`, `issuing_country` and
`event_country`. The generator refuses the reserved names now.

---

## Where things live

| Path | What |
| ---- | ---- |
| `hms/hms/documents.py` | the rules, and a self-check that runs without a database |
| `hms/hms/doctype/horse_document/` | the transaction and its validation |
| `hms/hms/doctype/horse_document_category/` | the control panel |
| `hms/api/events.py` | the poll, the watermark, the default actions |
| `hms/hms/doctype/horse_event/` | the event, its notification and `Create Transaction` |
| `hms/fixtures/` | the shipped categories and event types |
| `hms/patches/v1_0/documents_to_transactions.py` | the one-time migration off the old fields |

```bash
# the document rules, no site needed
/home/omix/frappe-bench/env/bin/python apps/hms/hms/hms/documents.py

# everything
bench --site losand.local run-tests --app hms
```

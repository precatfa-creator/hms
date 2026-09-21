#!/usr/bin/env python3
"""Build docs/HMS-Screens.pdf: every HMS screen, with what it does and how it
relates to the StudLib database.

	./env/bin/python apps/hms/scripts/gen_handbook.py

Takes the PNGs in apps/hms/screenshots (produced by capture_screenshots.py),
writes an HTML document beside them and runs wkhtmltopdf over it. Captions live
in SECTIONS below -- that is the only thing to edit when a screen changes.
"""

import html
import os
import subprocess
import sys

APP = "/home/omix/frappe-bench/apps/hms"
SHOTS = f"{APP}/screenshots"
OUT_HTML = f"{APP}/screenshots/handbook.html"
OUT_PDF = f"{APP}/docs/HMS-Screens.pdf"

# (section title, intro paragraphs, [(shot, caption)])
SECTIONS = [
	(
		"1. The workspace",
		["Everything starts here. The number cards and charts are ordinary Frappe "
		 "dashboard records, so they read live counts out of the site rather than "
		 "out of the studbook."],
		[("01-workspace",
		  "The HMS workspace. <b>New Events</b> counts studbook events nobody has "
		  "acted on yet; <b>Documents Incomplete</b> counts horses still missing a "
		  "required document. The link cards below group the whole app: Registry, "
		  "Documents, Events, Forms, Studbook Data and Setup.")],
	),
	(
		"2. The horse registry",
		["A Horse is a mirror of one row of the StudLib <code>horse</code> table. "
		 "The sync writes it; nothing here is typed in by hand once a horse is "
		 "coming from the studbook."],
		[("02-horse-list",
		  "The Horse list. The coloured indicator is <code>documents_status</code> "
		  "&mdash; red Not Yet, orange Partially Completed, green Completed. That "
		  "is ours, not the studbook's."),
		 ("03-horse-list-report",
		  "The same records in report view, where the studbook's own fields are "
		  "visible as columns: sex, registration status and origin.")],
	),
	(
		"3. A horse that came from the studbook",
		["Bint Misr was read out of StudLib by the sync. Every field on the "
		 "Identity and Studbook tabs is owned by the studbook and rewritten on "
		 "each run; nothing on this horse was typed here."],
		[("04-horse-synced-identity",
		  "The Identity tab. <b>Registry ID</b> is StudLib's <code>registry_id</code>, "
		  "<b>Studbook UUID</b> is its <code>uuid</code> &mdash; and the uuid, not the "
		  "registry number, is what the sync matches on, because a foal has no "
		  "registry number until it is registered. <b>Country of Origin</b> is greyed "
		  "out because it is derived: StudLib has no origin column, so a horse whose "
		  "birthplace country is flagged Local is Local and anything else is "
		  "Imported."),
		 ("05-horse-synced-studbook",
		  "The Studbook tab: volume, page and appendix in the current studbook and "
		  "in the previous one. These are <code>book_number</code>, "
		  "<code>book_page</code>, <code>book_appendix_number</code> and their "
		  "<code>previous_*</code> twins, with Book Type resolved from StudLib's "
		  "<code>book_type</code> table."),
		 ("06-horse-synced-ownership",
		  "The Ownership tab. <b>Owners</b> and <b>Breeders</b> are tables, not single "
		  "fields, because StudLib joins them many-to-many through "
		  "<code>horse_owner</code> and <code>horse_breeder</code> &mdash; a horse can "
		  "be owned by a syndicate. The flat owner block below still exists because "
		  "the printed paper forms are built on it."),
		 ("07-horse-synced-connections",
		  "The Connections panel at the bottom of the form. This replaced the old "
		  "Documents tab: documents, events and the paper forms are records in their "
		  "own right now, each counted here."),
		 ("08-horse-foal-pedigree",
		  "A foal's Pedigree tab. <b>Sire</b> and <b>Dam</b> are real links to other "
		  "Horse records, carrying StudLib's <code>father_id</code> and "
		  "<code>mother_id</code>. The text block underneath is kept for parents "
		  "outside this studbook, which have no record to link to."),
		 ("09-horse-foal-identity",
		  "The same foal's Identity tab. <b>Registration Status</b> reads "
		  "<i>Waiting for Laboratory</i> &mdash; this is StudLib's own registration "
		  "workflow (<code>horse.status</code>), which is why it has no Registry ID "
		  "yet.")],
	),
	(
		"4. Document status",
		["<code>documents_status</code> is Frappe's, not the studbook's. It is "
		 "recalculated from the Horse Documents a horse actually holds, against the "
		 "categories its origin and sex make mandatory. A re-sync never touches it."],
		[("10-horse-completed-identity",
		  "A horse whose documents are all in: <b>Documents</b> reads Completed."),
		 ("11-horse-completed-connections",
		  "Its Connections panel &mdash; five documents, one registration form, one "
		  "transfer."),
		 ("12-horse-partial-connections",
		  "A Partially Completed horse. Some required categories are filled, some "
		  "are not. Optional documents never move the status."),
		 ("13-horse-notyet-connections",
		  "A Not Yet horse: nothing uploaded against any required category."),
		 ("14-horse-new",
		  "A blank Horse. In practice horses arrive through the sync; this form is "
		  "for the rare record the studbook does not carry.")],
	),
	(
		"5. Documents as transactions",
		["A document used to be an attachment field on the Horse &mdash; one upload "
		 "per category, forever. It is now a <b>Horse Document</b> record, so a horse "
		 "can hold as many as its category allows: one Owner ID per co-owner, one "
		 "covering certificate per season."],
		[("15-document-list",
		  "Every uploaded document across the registry, with its horse, category and "
		  "date."),
		 ("16-document-marking",
		  "A Marking document. The category decided that this one needs a date and a "
		  "reference, and relabelled them <i>Marking Date</i> and <i>Marked By "
		  "(Doctor)</i>."),
		 ("17-document-owner-id",
		  "An Owner ID. The same five detail fields exist on every document; only the "
		  "ones its category asks for are shown."),
		 ("18-document-new",
		  "A blank Horse Document. The detail fields stay hidden until a category is "
		  "picked, because the category is what decides which of them apply.")],
	),
	(
		"6. Document categories &mdash; the control panel",
		["This is the doctype that replaced the hard-coded rules. Who needs a "
		 "document, how many they may upload and which details must come with it "
		 "are all fields here. Changing one takes effect on the next save of any "
		 "horse; no deployment."],
		[("19-category-list",
		  "The thirteen shipped categories, taken from the documents mapping."),
		 ("20-category-registration-form",
		  "Registration Form: applies to Local and Imported horses and is required "
		  "for both. <b>Maximum Uploads</b> is 1. It asks for a date, relabelled "
		  "<i>Date of Registration</i>."),
		 ("21-category-covering-certificate",
		  "Covering Certificate: <b>Sex</b> is set to Females, so it never applies to "
		  "a stallion &mdash; the mapping asks a male for a Covering Agreement "
		  "instead. <b>Maximum Uploads</b> is 0, meaning no limit, because a mare "
		  "collects one per season."),
		 ("22-category-owner-id",
		  "Owner ID: required for both origins and unlimited, so a horse owned by "
		  "three people can carry three IDs.")],
	),
	(
		"7. Events",
		["StudLib records a lifecycle event &mdash; a change of owner, a death, an "
		 "export &mdash; and HMS raises it here as a notification. An event is a "
		 "<i>notice</i>, not a state: StudLib writes the death date onto the horse "
		 "itself, and the horse sync already carries that. Nothing in the event "
		 "pipeline writes to a Horse, so the two can never corrupt each other."],
		[("23-event-list",
		  "Events read out of StudLib's <code>event</code> table. The indicator is "
		  "the handling state: orange New, blue Acknowledged, green Processed, grey "
		  "Ignored."),
		 ("24-event-new-status",
		  "A New Foal event nobody has acted on yet. <b>Studbook Event ID</b> is "
		  "StudLib's <code>event.id</code>; the poll uses it to skip what it has "
		  "already imported. The <b>Create Transaction</b> button turns the notice "
		  "into paperwork."),
		 ("25-event-processed",
		  "A change of owner, after Create Transaction. <b>Previous Owners</b> and "
		  "<b>New Owners</b> come from StudLib's <code>event_old_owner</code> and "
		  "<code>event_new_owner</code> join tables. <b>What Came Of It</b> links the "
		  "Owner Change Form and the Horse Document it produced."),
		 ("26-event-import",
		  "An import event. <b>Country</b> is StudLib's <code>country_id</code> on "
		  "the event, which is only set for imports and exports."),
		 ("27-event-type-list",
		  "The eight event types StudLib defines. The user guide's Events screen "
		  "offers only three of them; the rest arrive from the covering and foal "
		  "registration flows.")],
	),
	(
		"8. Owners and studbook reference data",
		["StudLib is normalised: colours, countries and book types are tables of "
		 "their own, and owners are a directory. The sync mirrors all four before it "
		 "touches a horse, so the Horse has something to link at."],
		[("28-owner-list", "The owner directory, mirrored from StudLib's "
		  "<code>owner</code> table."),
		 ("29-owner-record",
		  "One owner. <b>Business</b> switches which identifier applies &mdash; a "
		  "company has a business number, a person a national ID. <b>Suffix</b> is "
		  "globally unique and is what disambiguates two owners of the same name on "
		  "a printed certificate."),
		 ("30-country-list",
		  "Countries. Exactly one may be flagged <b>Local Country</b>; StudLib "
		  "enforces that with a partial unique index, and it is what makes a horse's "
		  "origin derivable rather than stored."),
		 ("31-color-list",
		  "Colours are breed-specific in StudLib &mdash; Bay exists once for Arabian "
		  "and once for Thoroughbred &mdash; so the record is named "
		  "<i>Colour (Breed)</i>. <b>Inheritance Rule</b> is StudLib's "
		  "<code>validation_rule</code>."),
		 ("32-book-type-list",
		  "Book types: the studbook sections a horse can be registered in, each "
		  "belonging to one breed and one issuing authority.")],
	),
	(
		"9. The sync and the poll",
		["Both connections live on one settings page. The studbook is read with a "
		 "read-only Postgres role and HMS never writes back to it."],
		[("33-settings-studbook",
		  "The studbook connection. <b>Test Connection</b> reads a row count and "
		  "nothing else. <b>Sync Horses Now</b> mirrors the reference tables, then "
		  "upserts every horse. The schedule underneath rewrites a Frappe Scheduled "
		  "Job, so due times, deduplication and run history all come free. The "
		  "history table at the bottom keeps the last twenty runs."),
		 ("34-settings-events",
		  "Event polling. <b>Backfill Past Events</b> off means the first poll starts "
		  "from the newest event, so years of history do not each fire a "
		  "notification. <b>Event Actions</b> is what an arriving event turns into: "
		  "change any row and the next event follows the new rule, with no "
		  "deployment.")],
	),
	(
		"10. The paper forms",
		["These are HMS's own: the studbook knows nothing about them. Each links "
		 "back to its horse, so it appears in that horse's Connections panel, and "
		 "each can be created straight from an event."],
		[("35-registration-list", "Registration forms for locally bred horses."),
		 ("36-registration-horse-data", "The horse's own data as declared on the form."),
		 ("37-registration-names",
		  "Three proposed names in order of priority, and the one approved."),
		 ("38-registration-pedigree",
		  "Sire and dam as declared, plus the covering that produced the foal."),
		 ("39-registration-owner", "Owner and breeder as declared."),
		 ("40-owner-change-list", "Transfers of ownership."),
		 ("41-owner-change-horse",
		  "The horse block is fetched from the Horse record, so it cannot drift."),
		 ("42-owner-change-parties",
		  "Transferor on the left, fetched; transferee on the right, typed in. When "
		  "this form is created from a change of owner event, the right-hand side "
		  "arrives already filled from the event."),
		 ("43-name-change-list", "Name changes."),
		 ("44-name-change-names", "Proposed and approved names.")],
	),
	(
		"11. Print formats",
		["The official bilingual paperwork, rendered from the same records."],
		[("45-print-registration", "The local-bred horse registration form."),
		 ("46-print-transfer", "The transfer of ownership form.")],
	),
]

MAPPING_ROWS = [
	("name", "name_en", "Official registered name. <code>name</code> is Frappe's docname, hence the alias."),
	("local_name", "name_ar", "The local-language name."),
	("uuid", "studbook_uuid", "<b>The sync key.</b> Stable from creation, unlike the registry number."),
	("registry_id", "registry_id", "Empty until the horse is registered."),
	("status", "status", "Registration workflow: New Foal &rarr; &hellip; &rarr; Register in Studbook."),
	("sex", "gender", "Seven values, not three: Stallion, Broodmare, Cryptorchid and Monorchid too."),
	("breed", "breed", "Arabian or Thoroughbred. Scopes colours and book types."),
	("ueln", "ueln_no", "15-character international code."),
	("transponder_code", "microchip_no", "ISO 11784/11785 microchip."),
	("date_of_death", "date_of_death", "<code>life_status</code> is derived from it."),
	("birthplace_country_id", "birthplace_country", "&rarr; Studbook Country. <b>Origin is derived from its Local flag.</b>"),
	("color_id", "color", "&rarr; Horse Color, which is breed-specific."),
	("book_type_id", "book_type", "&rarr; Book Type."),
	("father_id / mother_id", "sire / dam", "&rarr; Horse. Resolved in a second pass, so a foal read before its sire still links."),
	("horse_owner (M:N)", "owners", "Child table. A horse may have several owners at once."),
	("horse_breeder (M:N)", "breeders", "Child table. The dam's owners at foaling."),
	("&mdash;", "documents_status", "<b>Frappe's own.</b> Never written by the sync."),
]

CSS = """
@page { size: A4; margin: 18mm 15mm 16mm 15mm; }
body { font-family: "DejaVu Sans", "Noto Sans", sans-serif; font-size: 10pt;
       color: #1f2328; line-height: 1.5; }
h1 { font-size: 26pt; margin: 0 0 4mm 0; color: #14181c; }
h2 { font-size: 15pt; margin: 0 0 3mm 0; color: #14181c;
     border-bottom: 2px solid #3b7ddd; padding-bottom: 2mm; }
h3 { font-size: 11pt; margin: 6mm 0 2mm 0; color: #14181c; }
p  { margin: 0 0 3mm 0; }
code { font-family: "DejaVu Sans Mono", monospace; font-size: 8.6pt;
       background: #f2f4f6; padding: 0 1mm; border-radius: 2px; }
pre { font-family: "DejaVu Sans Mono", monospace; font-size: 8pt; line-height: 1.35;
      background: #f7f9fb; border: 1px solid #dde3e9; border-radius: 3px;
      padding: 4mm; white-space: pre; }
.cover { text-align: left; padding-top: 55mm; }
.cover .sub { font-size: 13pt; color: #5b6570; margin-top: 2mm; }
.cover .meta { margin-top: 20mm; font-size: 9.5pt; color: #5b6570; }
.section { page-break-before: always; }
.intro { color: #3d454d; }
figure { page-break-inside: avoid; margin: 0 0 7mm 0; }
figure img { max-width: 100%; max-height: 232mm; border: 1px solid #d5dbe1;
             border-radius: 3px; }
figcaption { font-size: 8.8pt; color: #4a535c; margin-top: 1.5mm;
             padding-left: 2mm; border-left: 3px solid #3b7ddd; }
figcaption .n { font-weight: bold; color: #1f2328; }
table { border-collapse: collapse; width: 100%; font-size: 8.6pt; }
th { background: #eef2f6; text-align: left; padding: 1.8mm 2mm;
     border: 1px solid #d5dbe1; }
td { padding: 1.8mm 2mm; border: 1px solid #d5dbe1; vertical-align: top; }
td.f { font-family: "DejaVu Sans Mono", monospace; font-size: 8pt; white-space: nowrap; }
.note { background: #fff8e6; border: 1px solid #f0dca8; border-radius: 3px;
        padding: 3mm 4mm; margin: 0 0 4mm 0; font-size: 9pt; }
.toc li { margin-bottom: 1.2mm; }
"""

ARCHITECTURE = """PostgreSQL (StudLib, read-only)              Frappe (HMS)
-------------------------------              ------------

country, horse_color, book_type   ---------> Studbook Country, Horse Color,
owner                              mirror    Book Type, Horse Owner
                                             |
horse  + its joins                ---------> Horse            (keyed on uuid)
horse_owner, horse_breeder                   Horse Party      (owners, breeders)
                                             |
                                             +-- Horse Document     ] Frappe's own,
                                             +-- documents_status   ] never written
                                             +-- paper forms        ] by the sync

event, event_type                 ---------> Horse Event  -> Notification
event_old_owner, event_new_owner    poll                   -> Create Transaction
                                                              |
                                                              +-> a paper form
                                                              +-> a Horse Document
"""


# A page holds an image about 1.45x as tall as it is wide before it has to be
# shrunk below legibility. Anything taller is cut into strips that each fill the
# page width instead.
MAX_ASPECT = 1.45
OVERLAP = 40  # px of shared content, so a cut never lands mid-row


def strips(shot):
	"""[(filename, is_part)] -- one entry for a normal shot, several for a tall one."""
	from PIL import Image

	path = f"{SHOTS}/{shot}.png"
	image = Image.open(path)
	width, height = image.size
	if height <= width * MAX_ASPECT:
		return [(f"{shot}.png", False)]

	parts = int(-(-height // (width * MAX_ASPECT)))
	step = height // parts
	out = []
	for index in range(parts):
		top = max(index * step - (OVERLAP if index else 0), 0)
		bottom = min((index + 1) * step + OVERLAP, height)
		name = f"parts/{shot}-{index + 1}.png"
		image.crop((0, top, width, bottom)).save(f"{SHOTS}/{name}")
		out.append((name, True))
	return out


def figure(number, shot, caption):
	if not os.path.exists(f"{SHOTS}/{shot}.png"):
		print(f"  ! missing {shot}.png", file=sys.stderr)
		return ""

	pieces = strips(shot)
	total = len(pieces)
	out = []
	for index, (name, is_part) in enumerate(pieces, start=1):
		label = (f"Figure {number}." if total == 1
		         else f"Figure {number}, {index} of {total}.")
		# only the last strip carries the caption text; the others just say
		# where they are in the sequence
		text = caption if index == total else "(continued below)"
		out.append(f'<figure><img src="{html.escape(name)}">'
		           f'<figcaption><span class="n">{label}</span> {text}</figcaption>'
		           f'</figure>\n')
	return "".join(out)


def build_html():
	parts = [f"<html><head><meta charset='utf-8'><style>{CSS}</style></head><body>"]

	parts.append(
		"<div class='cover'><h1>Horse Management System</h1>"
		"<div class='sub'>Every screen, and how it relates to the StudLib database</div>"
		"<div class='meta'>Frappe application <code>hms</code><br>"
		"Studbook data specification 1.01<br>"
		"Generated from a live site &mdash; every figure is a real record.</div></div>")

	# how it fits together
	parts.append("<div class='section'><h2>How HMS and StudLib fit together</h2>")
	parts.append(
		"<p class='intro'>StudLib is the system of record for horses: identity, "
		"pedigree, ownership. HMS holds the same horses plus the things StudLib "
		"knows nothing about &mdash; scanned documents, completion status and the "
		"paper forms. HMS reads StudLib through a <b>read-only</b> Postgres role and "
		"never writes back.</p>")
	parts.append(f"<pre>{ARCHITECTURE}</pre>")
	parts.append(
		"<h3>Two pipelines, kept apart</h3>"
		"<p>The <b>horse sync</b> carries state. The <b>event poll</b> carries "
		"notices. They never cross: StudLib records a death event <i>and</i> writes "
		"the death date onto the horse, so the sync already has the fact &mdash; the "
		"event exists only to tell someone and to start the paperwork. An event "
		"handled wrongly therefore cannot corrupt a horse record.</p>"
		"<div class='note'><b>Why the event poll looks backwards.</b> Postgres hands "
		"out sequence values before a transaction commits, so a transaction holding "
		"event 500 can commit after one holding 505. A plain <code>id &gt; "
		"watermark</code> would read 505, move past 500, and lose it forever. The "
		"poll therefore re-reads a window of 200 ids below the watermark and drops "
		"what it already has.</div>")

	parts.append("<h3>Who owns what</h3><table>"
	             "<tr><th style='width:50%'>StudLib owns</th><th>HMS owns</th></tr>"
	             "<tr><td>names, registry ids, UELN, microchip, sex, colour, breed, "
	             "strain, classification, registration status, all seven dates, "
	             "studbook volume and page, sire and dam, owners and breeders, "
	             "birthplace / import / export country</td>"
	             "<td>every Horse Document and its details, "
	             "<code>documents_status</code>, the registration and change forms, "
	             "Horse Events once they have been raised</td></tr></table>"
	             "<p style='margin-top:3mm'>The sync writes only the left column, so "
	             "re-running it can never cost anyone an upload.</p>")

	# field mapping
	parts.append("<h3>The field mapping</h3>"
	             "<p>Every Horse field carries its StudLib column name, with two "
	             "deliberate exceptions noted below.</p><table>"
	             "<tr><th style='width:26%'>StudLib column</th>"
	             "<th style='width:22%'>Horse field</th><th>Note</th></tr>")
	for column, field, note in MAPPING_ROWS:
		parts.append(f"<tr><td class='f'>{column}</td><td class='f'>{field}</td>"
		             f"<td>{note}</td></tr>")
	parts.append("</table></div>")

	# the screens
	number = 1
	for title, intros, shots in SECTIONS:
		parts.append(f"<div class='section'><h2>{title}</h2>")
		for intro in intros:
			parts.append(f"<p class='intro'>{intro}</p>")
		for shot, caption in shots:
			parts.append(figure(number, shot, caption))
			number += 1
		parts.append("</div>")

	parts.append("</body></html>")
	return "".join(parts)


def main():
	os.makedirs(f"{SHOTS}/parts", exist_ok=True)
	with open(OUT_HTML, "w") as fh:
		fh.write(build_html())
	print("wrote", OUT_HTML)

	subprocess.run([
		"wkhtmltopdf",
		"--enable-local-file-access",
		"--print-media-type",
		"--disable-smart-shrinking",
		"--footer-font-size", "7",
		"--footer-font-name", "DejaVu Sans",
		"--footer-left", "HMS — screens and the StudLib link",
		"--footer-right", "[page] / [topage]",
		"--footer-spacing", "6",
		OUT_HTML, OUT_PDF,
	], check=True)
	size = os.path.getsize(OUT_PDF)
	print(f"wrote {OUT_PDF}  {size // 1024} KB")


if __name__ == "__main__":
	main()

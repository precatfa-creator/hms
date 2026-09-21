#!/usr/bin/env python3
"""Generator for the HMS workspace, its dashboard charts and its number cards.

Charts and cards are imported from `hms/hms/dashboard_chart` and
`hms/hms/number_card` by frappe.utils.dashboard.sync_dashboards on every
migrate. Running this OVERWRITES those files and the workspace JSON.
"""

import json
import os
from datetime import datetime

MODULE_PATH = "/home/omix/frappe-bench/apps/hms/hms/hms"
MODULE = "HMS"
# a fresh timestamp on every run, sync_dashboards skips records whose stored
# `modified` already matches the file
NOW = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

HORSE = "Horse"
OWNER = "Horse Owner"
REG = "Registration Form for Local Horses"
OCF = "Owner Change Form"
NCF = "Name Change Form"
DOCUMENT = "Horse Document"
CATEGORY = "Horse Document Category"
EVENT = "Horse Event"
EVENT_TYPE = "Horse Event Type"
COLOR = "Horse Color"
COUNTRY = "Studbook Country"
BOOK = "Book Type"


def write(kind, name, doc):
	snake = name.lower().replace(" ", "_").replace("-", "_")
	folder = os.path.join(MODULE_PATH, kind, snake)
	os.makedirs(folder, exist_ok=True)
	doc.update({
		"creation": NOW,
		"docstatus": 0,
		"idx": 0,
		"modified": NOW,
		"modified_by": "Administrator",
		"module": MODULE,
		"name": name,
		"owner": "Administrator",
	})
	with open(os.path.join(folder, f"{snake}.json"), "w") as fh:
		json.dump(doc, fh, indent=1, sort_keys=True)
		fh.write("\n")
	print("wrote", kind, name)


def filters(*conditions):
	return json.dumps([list(c) + [False] for c in conditions])


# --------------------------------------------------------------------------
# number cards
# --------------------------------------------------------------------------
CARDS = [
	("Total Horses", HORSE, "[]", "#449CF0"),
	("Living Horses", HORSE, filters((HORSE, "life_status", "=", "Alive")), "#29CD42"),
	("Documents Completed", HORSE, filters((HORSE, "documents_status", "=", "Completed")), "#29CD42"),
	("Documents Incomplete", HORSE, filters((HORSE, "documents_status", "!=", "Completed")), "#ECAD4B"),
	("Imported Horses", HORSE, filters((HORSE, "origin", "=", "Imported")), "#7575FF"),
	("Registered Owners", OWNER, "[]", "#449CF0"),
	("Registration Forms", REG, "[]", "#ECAD4B"),
	("New Events", EVENT, filters((EVENT, "notification_status", "=", "New")), "#FF5858"),
	("Owner Change Forms", OCF, "[]", "#CB2929"),
	("Name Change Forms", NCF, "[]", "#CB2929"),
]

for label, doctype, filters_json, color in CARDS:
	write("number_card", label, {
		"aggregate_function_based_on": "",
		"color": color,
		"doctype": "Number Card",
		"document_type": doctype,
		"dynamic_filters_json": "[]",
		"filters_json": filters_json,
		"function": "Count",
		"is_public": 1,
		"is_standard": 1,
		"label": label,
		"parent_document_type": "",
		"report_function": "Sum",
		"show_percentage_stats": 1,
		"stats_time_interval": "Monthly",
		"type": "Document Type",
	})

# --------------------------------------------------------------------------
# dashboard charts
# --------------------------------------------------------------------------
GROUP_BY_CHARTS = [
	("Horses by Color", HORSE, "color", "Donut", "[]"),
	("Horses by Documents Status", HORSE, "documents_status", "Bar", "[]"),
	("Horses by Origin", HORSE, "origin", "Pie", "[]"),
	("Horses by Sex", HORSE, "gender", "Pie", filters((HORSE, "life_status", "=", "Alive"))),
]

for name, doctype, group_by, chart_type, filters_json in GROUP_BY_CHARTS:
	write("dashboard_chart", name, {
		"chart_name": name,
		"chart_type": "Group By",
		"custom_options": "",
		"doctype": "Dashboard Chart",
		"document_type": doctype,
		"dynamic_filters_json": "[]",
		"filters_json": filters_json,
		"group_by_based_on": group_by,
		"group_by_type": "Count",
		"is_public": 1,
		"is_standard": 1,
		"number_of_groups": 0,
		"roles": [],
		"time_interval": "Yearly",
		"timeseries": 0,
		"timespan": "Last Year",
		"type": chart_type,
		"use_report_chart": 0,
		"y_axis": [],
	})

TIMESERIES_CHARTS = [
	("Horse Registrations", REG, "creation", "Line", "[]"),
	("Ownership Transfers", OCF, "new_ownership_date", "Bar", "[]"),
	("Name Changes", NCF, "approval_date", "Bar", "[]"),
]

for name, doctype, based_on, chart_type, filters_json in TIMESERIES_CHARTS:
	write("dashboard_chart", name, {
		"based_on": based_on,
		"chart_name": name,
		"chart_type": "Count",
		"custom_options": "",
		"doctype": "Dashboard Chart",
		"document_type": doctype,
		"dynamic_filters_json": "[]",
		"filters_json": filters_json,
		"is_public": 1,
		"is_standard": 1,
		"number_of_groups": 0,
		"roles": [],
		"time_interval": "Monthly",
		"timeseries": 1,
		"timespan": "Last Year",
		"type": chart_type,
		"use_report_chart": 0,
		"y_axis": [],
	})

# --------------------------------------------------------------------------
# workspace
# --------------------------------------------------------------------------
SHORTCUTS = [
	(HORSE, "Blue", '{"life_status":["=","Alive"]}', "{} Alive"),
	(OWNER, "Grey", None, None),
	(EVENT, "Red", '{"notification_status":["=","New"]}', "{} New"),
	(DOCUMENT, "Purple", None, None),
	(REG, "Orange", None, None),
	(OCF, "Green", None, None),
	(NCF, "Green", None, None),
]

shortcuts = []
for label, color, stats_filter, fmt in SHORTCUTS:
	row = {"color": color, "doc_view": "List", "label": label, "link_to": label, "type": "DocType"}
	if stats_filter:
		row["stats_filter"] = stats_filter
		row["format"] = fmt
	shortcuts.append(row)

LINK_CARDS = [
	("Registry", [HORSE, OWNER]),
	("Documents", [DOCUMENT, CATEGORY]),
	("Events", [EVENT, EVENT_TYPE]),
	("Forms", [REG, OCF, NCF]),
	("Studbook Data", [COUNTRY, COLOR, BOOK]),
	("Setup", ["HMS Settings", "Print Format"]),
]

links = []
for card, doctypes in LINK_CARDS:
	links.append({
		"hidden": 0, "is_query_report": 0, "label": card, "link_count": len(doctypes),
		"onboard": 0, "type": "Card Break",
	})
	for doctype in doctypes:
		links.append({
			"dependencies": "", "hidden": 0, "is_query_report": 0, "label": doctype,
			"link_count": 0, "link_to": doctype, "link_type": "DocType", "onboard": 0,
			"type": "Link",
		})

CARD_ORDER = [label for label, *_ in CARDS]
CHART_ORDER = ["Horse Registrations", "Horses by Documents Status", "Horses by Color",
               "Horses by Origin", "Horses by Sex", "Ownership Transfers", "Name Changes"]

blocks = []
counter = [0]


def block(btype, data):
	counter[0] += 1
	blocks.append({"id": f"hms{counter[0]:03d}", "type": btype, "data": data})


def header(text):
	block("header", {"text": f'<span class="h4"><b>{text}</b></span>', "col": 12})


header("Shortcuts")
for label, *_ in SHORTCUTS:
	block("shortcut", {"shortcut_name": label, "col": 3})

block("spacer", {"col": 12})
header("Overview")
for label in CARD_ORDER:
	block("number_card", {"number_card_name": label, "col": 3})

block("spacer", {"col": 12})
header("Charts")
block("chart", {"chart_name": "Horse Registrations", "col": 12})
for name in ("Horses by Documents Status", "Horses by Color", "Horses by Origin", "Horses by Sex"):
	block("chart", {"chart_name": name, "col": 6})
block("chart", {"chart_name": "Ownership Transfers", "col": 6})
block("chart", {"chart_name": "Name Changes", "col": 6})

block("spacer", {"col": 12})
header("Masters & Forms")
for card, _ in LINK_CARDS:
	block("card", {"card_name": card, "col": 4})

workspace = {
	"charts": [{"chart_name": name, "label": name} for name in CHART_ORDER],
	"content": json.dumps(blocks),
	"custom_blocks": [],
	"doctype": "Workspace",
	"for_user": "",
	"hide_custom": 0,
	"icon": "users",
	"indicator_color": "green",
	"is_hidden": 0,
	"label": MODULE,
	"links": links,
	"number_cards": [{"label": label, "number_card_name": label} for label in CARD_ORDER],
	"parent_page": "",
	"public": 1,
	"quick_lists": [],
	"roles": [],
	"sequence_id": 1.0,
	"shortcuts": shortcuts,
	"title": MODULE,
}
write("workspace", MODULE, workspace)

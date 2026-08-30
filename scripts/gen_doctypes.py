#!/usr/bin/env python3
"""Generator for the HMS doctype JSON files.

The Documents tab is the same 12 attachments in four doctypes, so it is written
once here instead of four times by hand. Running this OVERWRITES the doctype
JSONs, including anything changed through the Desk UI - export the doctype back
into this script first if that happened.
"""

import json
import os

APP = "/home/omix/frappe-bench/apps/hms/hms/hms/doctype"
MODULE = "HMS"
NOW = "2026-07-26 10:00:00.000000"

# --------------------------------------------------------------------------
# shared document tab
# --------------------------------------------------------------------------
# key, label, [(companion fieldname, fieldtype, label, options)], depends_on
DOCS = [
    ("registration_form", "Registration Form",
     [("doc_registration_date", "Date", "Date of Registration", None)], None),
    ("breeding_certificate", "Breeding Certificate",
     [("doc_breeding_certificate_no", "Data", "Certificate Number", None)],
     'eval:doc.origin=="Local"'),
    ("dna_card", "DNA Result / Card",
     [("doc_dna_status", "Select", "DNA Status", "\nApproved\nDeclined")], None),
    ("marking", "Marking",
     [("doc_marking_by", "Data", "Marked By (Doctor)", None),
      ("doc_marking_date", "Date", "Marking Date", None)], None),
    ("owner_id", "Owner ID",
     [("doc_owner_id_date", "Date", "Date", None)], None),
    ("passport", "Passport",
     [("doc_passport_no", "Data", "Registration / Passport Number", None)],
     'eval:doc.origin=="Imported"'),
    ("export_certificate", "Export Certificate",
     [("doc_export_certificate_no", "Data", "Certificate Number", None),
      ("doc_export_date", "Date", "Date of Export", None)], None),
    ("covering_certificate", "Covering Certificate",
     [("doc_covering_season", "Data", "Season", None)],
     'eval:doc.gender=="Female"'),
    ("covering_agreement", "Covering Agreement",
     [("doc_covering_agreement_season", "Data", "Season", None)],
     'eval:doc.gender=="Male"'),
    ("owner_change_form", "Owner Change Form",
     [("doc_owner_change_date", "Date", "Date of the Event", None)], None),
    ("death_form", "Death Form",
     [("doc_death_event_date", "Date", "Date of the Event", None)], None),
    ("others", "Others",
     [("doc_others_note", "Small Text", "Note", None)], None),
]


def status_field():
    return {"fieldname": "status", "fieldtype": "Select", "label": "Status",
            "options": "Not Yet\nPartially Completed\nCompleted", "read_only": 1,
            "default": "Not Yet", "in_list_view": 1, "in_standard_filter": 1,
            "no_copy": 1}


def documents_tab():
    """Only the Horse carries the documents themselves."""
    f = [
        {"fieldname": "documents_tab", "fieldtype": "Tab Break", "label": "Documents"},
        status_field(),
    ]
    for key, label, companions, dep in DOCS:
        sec = {"fieldname": f"sec_doc_{key}", "fieldtype": "Section Break", "label": label}
        if dep:
            sec["depends_on"] = dep
        f.append(sec)
        f.append({"fieldname": f"doc_{key}", "fieldtype": "Attach", "label": label})
        f.append({"fieldname": f"col_doc_{key}", "fieldtype": "Column Break"})
        for cf, ct, cl, co in companions:
            fld = {"fieldname": cf, "fieldtype": ct, "label": cl}
            if co:
                fld["options"] = co
            f.append(fld)
    return f


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def fetch(fieldname, label, source, fieldtype="Data", options=None):
    f = {"fieldname": fieldname, "fieldtype": fieldtype, "label": label,
         "fetch_from": source, "read_only": 1}
    if options:
        f["options"] = options
    return f


def sec(fieldname, label=None):
    f = {"fieldname": fieldname, "fieldtype": "Section Break"}
    if label:
        f["label"] = label
    return f


def col(fieldname):
    return {"fieldname": fieldname, "fieldtype": "Column Break"}


def tab(fieldname, label):
    return {"fieldname": fieldname, "fieldtype": "Tab Break", "label": label}


def series(fieldname_options):
    # one series per doctype and it never changes, so it only takes up space
    return {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series",
            "options": fieldname_options, "reqd": 1, "set_only_once": 1,
            "default": fieldname_options.strip(), "hidden": 1, "print_hide": 1,
            "no_copy": 1}


def write_doctype(name, fields, **kw):
    snake = name.lower().replace(" ", "_").replace("-", "_")
    folder = os.path.join(APP, snake)
    os.makedirs(folder, exist_ok=True)
    init = os.path.join(folder, "__init__.py")
    if not os.path.exists(init):
        open(init, "w").close()

    doc = {
        "actions": [],
        "allow_rename": kw.get("allow_rename", 0),
        "creation": NOW,
        "doctype": "DocType",
        "editable_grid": 1,
        "engine": "InnoDB",
        "field_order": [f["fieldname"] for f in fields],
        "fields": fields,
        "index_web_pages_for_search": 1,
        "links": [],
        "modified": NOW,
        "modified_by": "Administrator",
        "module": MODULE,
        "name": name,
        "owner": "Administrator",
        "permissions": [],
        "row_format": "Dynamic",
        "sort_field": "modified",
        "sort_order": "DESC",
        "states": [],
    }
    if kw.get("istable"):
        doc["istable"] = 1
    else:
        doc["permissions"] = [{
            "create": 1, "delete": 1, "email": 1, "export": 1, "print": 1,
            "read": 1, "report": 1, "role": "System Manager", "share": 1,
            "write": 1,
        }]
        doc["track_changes"] = 1
    for k in ("autoname", "naming_rule", "title_field", "show_title_field_in_link",
              "search_fields", "default_print_format"):
        if k in kw:
            doc[k] = kw[k]

    path = os.path.join(folder, f"{snake}.json")
    with open(path, "w") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("wrote", path)
    return snake


def party_data(prefix, label, fetch_from_horse=False):
    """Owner / breeder block. Plain fields, typed in or filled from the studbook API."""
    def field(name, fieldtype, flabel, **extra):
        f = {"fieldname": f"{prefix}_{name}", "fieldtype": fieldtype,
             "label": f"{label} {flabel}".strip(), **extra}
        if fetch_from_horse:
            f["fetch_from"] = f"horse.{prefix_source}_{name}"
            f["read_only"] = 1
        return f

    prefix_source = "owner" if fetch_from_horse else prefix
    return [
        field("name_ar", "Data", "Name (Arabic)", in_list_view=1),
        field("name_en", "Data", "Name (English)"),
        field("national_id", "Data", "National ID / Passport No"),
        col(f"col_{prefix}_contact"),
        field("phone", "Data", "Phone No"),
        field("city", "Data", "City"),
        field("address", "Small Text", "Address"),
    ]


def parent_data(prefix, label):
    """Sire / Dam block. Plain fields, they are typed in or filled by the studbook API.

    Laid out in three columns: who it is, where it comes from, what it looks like.
    """
    return [
        {"fieldname": f"{prefix}_name_ar", "fieldtype": "Data",
         "label": f"{label}'s Name (Arabic)", "in_list_view": 1},
        {"fieldname": f"{prefix}_name_en", "fieldtype": "Data",
         "label": f"{label}'s Name (English)"},
        {"fieldname": f"{prefix}_registration_no", "fieldtype": "Data",
         "label": "Registration No"},
        col(f"col_{prefix}_origin"),
        {"fieldname": f"{prefix}_origin", "fieldtype": "Select", "label": "Country of Origin",
         "options": "\nLocal\nImported"},
        {"fieldname": f"{prefix}_date_of_birth", "fieldtype": "Date", "label": "Date of Birth"},
        {"fieldname": f"{prefix}_place_of_birth", "fieldtype": "Data", "label": "Place of Birth"},
        col(f"col_{prefix}_description"),
        {"fieldname": f"{prefix}_color", "fieldtype": "Data", "label": "Color"},
        {"fieldname": f"{prefix}_breed", "fieldtype": "Data", "label": "Breed"},
        {"fieldname": f"{prefix}_microchip_no", "fieldtype": "Data", "label": "Microchip No"},
    ]


# --------------------------------------------------------------------------
# 1. Horse Owner
# --------------------------------------------------------------------------
write_doctype(
    "Horse Owner",
    [
        series("OWN-.#####\n"),
        sec("sec_name"),
        {"fieldname": "owner_name_ar", "fieldtype": "Data", "label": "Name (Arabic)",
         "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
        {"fieldname": "owner_name_en", "fieldtype": "Data", "label": "Name (English)",
         "reqd": 1, "in_list_view": 1},
        {"fieldname": "national_id", "fieldtype": "Data", "label": "National ID No"},
        {"fieldname": "passport_no", "fieldtype": "Data", "label": "Passport No"},
        col("col_contact"),
        {"fieldname": "phone", "fieldtype": "Data", "label": "Phone No",
         "options": "Phone", "in_list_view": 1},
        {"fieldname": "email", "fieldtype": "Data", "label": "Email", "options": "Email"},
        {"fieldname": "city", "fieldtype": "Data", "label": "City"},
        {"fieldname": "address", "fieldtype": "Small Text", "label": "Complete Address"},
    ],
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    title_field="owner_name_en",
    show_title_field_in_link=1,
    search_fields="owner_name_ar,phone,national_id",
    allow_rename=1,
)

# --------------------------------------------------------------------------
# 2. child tables
# --------------------------------------------------------------------------
write_doctype(
    "Horse Ownership Log",
    [
        {"fieldname": "owner_name_en", "fieldtype": "Data", "label": "Owner",
         "in_list_view": 1, "reqd": 1, "columns": 3},
        {"fieldname": "owner_national_id", "fieldtype": "Data",
         "label": "National ID / Passport No", "in_list_view": 1, "columns": 2},
        {"fieldname": "from_date", "fieldtype": "Date", "label": "From Date",
         "in_list_view": 1, "columns": 2},
        {"fieldname": "to_date", "fieldtype": "Date", "label": "To Date",
         "in_list_view": 1, "columns": 2},
        {"fieldname": "owner_change_form", "fieldtype": "Link", "label": "Owner Change Form",
         "options": "Owner Change Form", "in_list_view": 1, "read_only": 1, "columns": 3},
    ],
    istable=1,
)

write_doctype(
    "Horse Name Log",
    [
        {"fieldname": "name_ar", "fieldtype": "Data", "label": "Name (Arabic)",
         "in_list_view": 1, "columns": 3},
        {"fieldname": "name_en", "fieldtype": "Data", "label": "Name (English)",
         "in_list_view": 1, "columns": 3},
        {"fieldname": "changed_on", "fieldtype": "Date", "label": "Changed On",
         "in_list_view": 1, "columns": 2},
        {"fieldname": "name_change_form", "fieldtype": "Link", "label": "Name Change Form",
         "options": "Name Change Form", "in_list_view": 1, "read_only": 1, "columns": 3},
    ],
    istable=1,
)

# --------------------------------------------------------------------------
# 3. Horse
# --------------------------------------------------------------------------
horse_fields = [
    tab("identity_tab", "Identity"),
    series("LY-.YYYY.-.#####\n"),
    sec("sec_names"),
    {"fieldname": "name_ar", "fieldtype": "Data", "label": "Name (Arabic)", "reqd": 1,
     "in_list_view": 1, "in_standard_filter": 1},
    {"fieldname": "name_en", "fieldtype": "Data", "label": "Name (English)", "reqd": 1,
     "in_list_view": 1},
    {"fieldname": "ueln_no", "fieldtype": "Data", "label": "UELN No"},
    {"fieldname": "microchip_no", "fieldtype": "Data", "label": "Microchip No"},
    col("col_identity"),
    {"fieldname": "origin", "fieldtype": "Select", "label": "Country of Origin",
     "options": "Local\nImported", "default": "Local", "reqd": 1, "in_standard_filter": 1},
    {"fieldname": "gender", "fieldtype": "Select", "label": "Sex",
     "options": "\nMale\nFemale\nGelding", "reqd": 1, "in_list_view": 1,
     "in_standard_filter": 1},
    {"fieldname": "registration_form", "fieldtype": "Link", "label": "Registration Form",
     "options": "Registration Form for Local Horses", "read_only": 1, "no_copy": 1},
    sec("sec_description", "Description"),
    {"fieldname": "color", "fieldtype": "Link", "label": "Color", "options": "Color"},
    {"fieldname": "breed", "fieldtype": "Data", "label": "Breed"},
    {"fieldname": "date_of_birth", "fieldtype": "Date", "label": "Date of Birth"},
    {"fieldname": "place_of_birth", "fieldtype": "Data", "label": "Place of Birth"},
    col("col_status"),
    {"fieldname": "current_location", "fieldtype": "Data", "label": "Current Location"},
    {"fieldname": "life_status", "fieldtype": "Select", "label": "Status of Life",
     "options": "Alive\nDeceased", "default": "Alive", "in_list_view": 1},
    {"fieldname": "death_date", "fieldtype": "Date", "label": "Date of Death",
     "depends_on": 'eval:doc.life_status=="Deceased"'},
    {"fieldname": "notification_date", "fieldtype": "Date", "label": "Notification Date"},

    tab("pedigree_tab", "Pedigree"),
    sec("sec_sire", "Sire's Data"),
] + parent_data("sire", "Sire") + [
    sec("sec_dam", "Dam's Data"),
] + parent_data("dam", "Dam") + [

    tab("ownership_tab", "Ownership"),
    sec("sec_owner", "Owner"),
] + party_data("owner", "Owner") + [
    {"fieldname": "owner_since", "fieldtype": "Date", "label": "Owner Since"},
    sec("sec_breeder", "Breeder"),
] + party_data("breeder", "Breeder") + [
    sec("sec_history", "History"),
    {"fieldname": "ownership_history", "fieldtype": "Table", "label": "Ownership History",
     "options": "Horse Ownership Log", "read_only": 1},
    {"fieldname": "name_history", "fieldtype": "Table", "label": "Name History",
     "options": "Horse Name Log", "read_only": 1},
] + documents_tab()

write_doctype(
    "Horse",
    horse_fields,
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    title_field="name_en",
    show_title_field_in_link=1,
    search_fields="name_ar,name_en,microchip_no",
    allow_rename=1,
)

# --------------------------------------------------------------------------
# 4. Registration Form for Local Horses
# --------------------------------------------------------------------------
reg_fields = [
    tab("horse_data_tab", "Horse Data"),
    series("REG-LOC-.YYYY.-.#####\n"),
    sec("sec_horse"),
    {"fieldname": "gender", "fieldtype": "Select", "label": "Sex",
     "options": "\nMale\nFemale", "reqd": 1, "in_list_view": 1},
    {"fieldname": "color", "fieldtype": "Link", "label": "Color", "options": "Color"},
    {"fieldname": "breed", "fieldtype": "Data", "label": "Breed"},
    {"fieldname": "date_of_birth", "fieldtype": "Date", "label": "Date of Birth", "reqd": 1},
    {"fieldname": "place_of_birth", "fieldtype": "Data", "label": "Place of Birth"},
    col("col_horse"),
    {"fieldname": "microchip_no", "fieldtype": "Data", "label": "Microchip No"},
    {"fieldname": "current_location", "fieldtype": "Data", "label": "Current Location of Horse"},
    {"fieldname": "life_status", "fieldtype": "Select", "label": "Status of Life",
     "options": "Alive\nDeceased", "default": "Alive"},
    {"fieldname": "death_date", "fieldtype": "Date", "label": "Date of Death",
     "depends_on": 'eval:doc.life_status=="Deceased"'},
    {"fieldname": "notification_date", "fieldtype": "Date", "label": "Notification Date"},
    {"fieldname": "origin", "fieldtype": "Select", "label": "Country of Origin",
     "options": "Local\nImported", "default": "Local", "read_only": 1},

    tab("names_tab", "Proposed Names"),
    sec("sec_proposed", "Proposed Names in Order of Priority"),
    {"fieldname": "name_1_ar", "fieldtype": "Data", "label": "Name 1 (Arabic)", "reqd": 1},
    {"fieldname": "name_2_ar", "fieldtype": "Data", "label": "Name 2 (Arabic)"},
    {"fieldname": "name_3_ar", "fieldtype": "Data", "label": "Name 3 (Arabic)"},
    col("col_proposed_en"),
    {"fieldname": "name_1_en", "fieldtype": "Data", "label": "Name 1 (English)", "reqd": 1},
    {"fieldname": "name_2_en", "fieldtype": "Data", "label": "Name 2 (English)"},
    {"fieldname": "name_3_en", "fieldtype": "Data", "label": "Name 3 (English)"},
    sec("sec_approved", "Approved Name"),
    {"fieldname": "approved_name_ar", "fieldtype": "Data", "label": "Approved Name (Arabic)",
     "allow_on_submit": 1},
    col("col_approved"),
    {"fieldname": "approved_name_en", "fieldtype": "Data", "label": "Approved Name (English)",
     "allow_on_submit": 1},

    tab("pedigree_tab", "Pedigree"),
    sec("sec_sire", "Sire's Data"),
] + parent_data("sire", "Sire") + [
    sec("sec_dam", "Dam's Data"),
] + parent_data("dam", "Dam") + [
    {"fieldname": "dam_life_status", "fieldtype": "Select", "label": "Status of Life",
     "options": "\nAlive\nDeceased"},
    {"fieldname": "dam_current_location", "fieldtype": "Data",
     "label": "Current Location of Dam"},
    sec("sec_covering", "Covering"),
    {"fieldname": "covering_location", "fieldtype": "Select", "label": "Location of Covering",
     "options": "\nLocal\nExternal"},
    col("col_covering"),
    {"fieldname": "covering_date_1", "fieldtype": "Date", "label": "Date of 1st Covering"},
    {"fieldname": "covering_date_2", "fieldtype": "Date", "label": "Date of 2nd Covering"},

    tab("owner_tab", "Owner & Breeder"),
    sec("sec_owner", "Owner's Data"),
] + party_data("owner", "Owner") + [
    sec("sec_breeder", "Breeder's Data"),
] + party_data("breeder", "Breeder") + [
] + [
    tab("result_tab", "Registration"),
    sec("sec_result"),
    {"fieldname": "horse", "fieldtype": "Link", "label": "Registered Horse",
     "options": "Horse", "no_copy": 1},
]

write_doctype(
    "Registration Form for Local Horses",
    reg_fields,
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    search_fields="name_1_en,owner_name_en,horse",
    default_print_format="Local-Bred Horse Registration Form",
)

# --------------------------------------------------------------------------
# 5. Owner Change Form
# --------------------------------------------------------------------------
def horse_fetch_block():
    return [
        {"fieldname": "horse", "fieldtype": "Link", "label": "Horse", "options": "Horse",
         "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
        fetch("horse_name_ar", "Horse's Name (Arabic)", "horse.name_ar"),
        fetch("horse_name_en", "Horse's Name (English)", "horse.name_en"),
        fetch("date_of_birth", "Date of Birth", "horse.date_of_birth", "Date"),
        fetch("place_of_birth", "Place of Birth", "horse.place_of_birth"),
        col("col_horse"),
        fetch("gender", "Sex", "horse.gender"),
        fetch("color", "Color", "horse.color", "Link", "Color"),
        fetch("origin", "Country of Origin", "horse.origin"),
        fetch("microchip_no", "Microchip No", "horse.microchip_no"),
        fetch("ueln_no", "UELN No", "horse.ueln_no"),
        sec("sec_pedigree", "Pedigree"),
        fetch("sire_name_en", "Sire's Name", "horse.sire_name_en"),
        fetch("sire_registration_no", "Sire Registration No", "horse.sire_registration_no"),
        col("col_pedigree"),
        fetch("dam_name_en", "Dam's Name", "horse.dam_name_en"),
        fetch("dam_registration_no", "Dam Registration No", "horse.dam_registration_no"),
    ]


ocf_fields = [
    tab("horse_tab", "Horse Information"),
    series("OCF-.YYYY.-.#####\n"),
    sec("sec_horse"),
] + horse_fetch_block() + [
    tab("parties_tab", "Parties"),
    sec("sec_transferor", "Transferor Information (Current Owner)"),
    fetch("current_owner_name_ar", "Full Name (Arabic)", "horse.owner_name_ar"),
    fetch("current_owner_name_en", "Full Name (English)", "horse.owner_name_en"),
    fetch("current_owner_national_id", "National ID / Passport No", "horse.owner_national_id"),
    fetch("current_owner_address", "Address", "horse.owner_address", "Small Text"),
    fetch("current_owner_city", "City", "horse.owner_city"),
    fetch("current_owner_phone", "Phone No", "horse.owner_phone"),
    fetch("current_ownership_date", "Horse Ownership Date", "horse.owner_since", "Date"),
    col("col_transferee"),
    {"fieldname": "new_owner_name_ar", "fieldtype": "Data", "label": "Full Name (Arabic)",
     "reqd": 1, "in_list_view": 1},
    {"fieldname": "new_owner_name_en", "fieldtype": "Data", "label": "Full Name (English)"},
    {"fieldname": "new_owner_national_id", "fieldtype": "Data",
     "label": "National ID / Passport No"},
    {"fieldname": "new_owner_address", "fieldtype": "Small Text", "label": "Address"},
    {"fieldname": "new_owner_city", "fieldtype": "Data", "label": "City"},
    {"fieldname": "new_owner_phone", "fieldtype": "Data", "label": "Phone No"},
    {"fieldname": "new_ownership_date", "fieldtype": "Date", "label": "Horse Ownership Date",
     "reqd": 1},
    sec("sec_legal", "Legal"),
    {"fieldname": "legal_contract_officer", "fieldtype": "Data",
     "label": "Legal Contract Officer's Name"},
    col("col_legal"),
    {"fieldname": "endorsement_date", "fieldtype": "Date", "label": "Endorsement Date"},
]

write_doctype(
    "Owner Change Form",
    ocf_fields,
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    search_fields="horse,new_owner_name_en",
    default_print_format="Horse Transfer of Ownership Form",
)

# --------------------------------------------------------------------------
# 6. Name Change Form
# --------------------------------------------------------------------------
ncf_fields = [
    tab("horse_tab", "Horse Information"),
    series("NCF-.YYYY.-.#####\n"),
    sec("sec_horse"),
] + horse_fetch_block() + [
    sec("sec_owner", "Owner"),
    fetch("owner_name_ar", "Owner's Name (Arabic)", "horse.owner_name_ar"),
    fetch("owner_name_en", "Owner's Name (English)", "horse.owner_name_en"),
    fetch("owner_national_id", "National ID / Passport No", "horse.owner_national_id"),
    fetch("owner_address", "Address", "horse.owner_address", "Small Text"),
    col("col_owner"),
    fetch("owner_city", "City", "horse.owner_city"),
    fetch("owner_phone", "Phone No", "horse.owner_phone"),

    tab("names_tab", "Names"),
    sec("sec_proposed", "Proposed Names in Order of Priority"),
    {"fieldname": "name_1_ar", "fieldtype": "Data", "label": "Name 1 (Arabic)", "reqd": 1},
    {"fieldname": "name_2_ar", "fieldtype": "Data", "label": "Name 2 (Arabic)"},
    {"fieldname": "name_3_ar", "fieldtype": "Data", "label": "Name 3 (Arabic)"},
    col("col_proposed_en"),
    {"fieldname": "name_1_en", "fieldtype": "Data", "label": "Name 1 (English)", "reqd": 1},
    {"fieldname": "name_2_en", "fieldtype": "Data", "label": "Name 2 (English)"},
    {"fieldname": "name_3_en", "fieldtype": "Data", "label": "Name 3 (English)"},
    sec("sec_approved", "Approved Name"),
    {"fieldname": "approved_name_ar", "fieldtype": "Data", "label": "Approved Name (Arabic)",
     "reqd": 1},
    {"fieldname": "approval_date", "fieldtype": "Date", "label": "Approval Date"},
    col("col_approved"),
    {"fieldname": "approved_name_en", "fieldtype": "Data", "label": "Approved Name (English)",
     "reqd": 1},
]

write_doctype(
    "Name Change Form",
    ncf_fields,
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    search_fields="horse,approved_name_en",
)

#!/usr/bin/env python3
"""Generator for the HMS doctype JSON files.

Running this OVERWRITES the doctype JSONs, including anything changed through
the Desk UI - export the doctype back into this script first if that happened.

The Horse mirrors the StudLib ``horse`` table column for column. Two deliberate
aliases, kept because the whole app (print formats, forms, the type-ahead
bridge) is already built on them:

    StudLib ``name``        -> ``name_en``   (``name`` is the Frappe docname)
    StudLib ``local_name``  -> ``name_ar``

Everything else carries the StudLib column name. ``hms/api/legacy_sync.py``
holds the full map.
"""

import json
import os

APPS = "/home/omix/frappe-bench/apps"
APP = f"{APPS}/hms/hms/hms/doctype"
MODULE = "HMS"
NOW = "2026-09-21 10:00:00.000000"

BREEDS = "\nArabian\nThoroughbred"
SEXES = "\nMale\nFemale\nStallion\nBroodmare\nGelding\nCryptorchid\nMonorchid"
# StudLib horse.status - the registration workflow, not our document tally
REG_STATUS = ("\nNew Foal\nNew Imported\nWaiting for Marking Data\nWaiting for Laboratory"
              "\nLaboratory Data Entered\nRegister in Studbook\nRejected\nExternal")
CLASSIFICATION = "\nRacing\nJumping\nBeauty\nUnknown"
DOC_STATUS = "Not Yet\nPartially Completed\nCompleted"


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


def check(fieldname, label, default=0, **extra):
    return {"fieldname": fieldname, "fieldtype": "Check", "label": label,
            "default": str(default), **extra}


def data(fieldname, label, **extra):
    return {"fieldname": fieldname, "fieldtype": "Data", "label": label, **extra}


def date(fieldname, label, **extra):
    return {"fieldname": fieldname, "fieldtype": "Date", "label": label, **extra}


def link(fieldname, label, doctype, **extra):
    return {"fieldname": fieldname, "fieldtype": "Link", "label": label,
            "options": doctype, **extra}


def select(fieldname, label, options, **extra):
    return {"fieldname": fieldname, "fieldtype": "Select", "label": label,
            "options": options, **extra}


def integer(fieldname, label, **extra):
    return {"fieldname": fieldname, "fieldtype": "Int", "label": label, **extra}


# Never call a Link field plain "country": Frappe fills any field with that
# fieldname from the session/global default, so every row silently acquires
# the system country whether the studbook said one or not -- and the sync then
# sees a difference on every run.


def studbook_id():
    """Every mirrored doctype keeps the StudLib primary key it came from.

    Indexed, not unique: an Int column defaults to 0, so a unique constraint
    would collide across every row that has never been synced.
    """
    return integer("studbook_id", "Studbook ID", read_only=1, no_copy=1,
                   search_index=1, hidden=1)


def series(fieldname_options):
    # one series per doctype and it never changes, so it only takes up space
    return {"fieldname": "naming_series", "fieldtype": "Select", "label": "Series",
            "options": fieldname_options, "reqd": 1, "set_only_once": 1,
            "default": fieldname_options.strip(), "hidden": 1, "print_hide": 1,
            "no_copy": 1}


def check_not_taken(snake):
    """A DocType name is global. Two apps shipping the same one does not
    error -- the later migrate silently replaces the other app's definition,
    which is how `Country` briefly ate frappe/geo's."""
    import glob

    clashes = [
        path for path in glob.glob(f"{APPS}/*/*/*/doctype/{snake}/{snake}.json")
        if "/apps/hms/" not in path
    ]
    if clashes:
        raise SystemExit(
            f"DocType '{snake}' already exists in another app: {clashes[0]}\n"
            f"Pick another name -- a duplicate overwrites theirs on migrate."
        )


# Fieldnames Frappe already owns or fills from a default. A field of one of
# these names does not error -- it silently carries the wrong value.
RESERVED_FIELDNAMES = {
    "name", "owner", "creation", "modified", "modified_by", "docstatus",
    "parent", "parentfield", "parenttype", "idx", "doctype", "country",
    "company", "_user_tags", "_comments", "_assign", "_liked_by",
}


def check_fieldnames(name, fields):
    bad = sorted({f["fieldname"] for f in fields} & RESERVED_FIELDNAMES)
    if bad:
        raise SystemExit(
            f"{name}: {bad} are fieldnames Frappe already uses or defaults. "
            f"Rename them -- they fail silently, not loudly."
        )


def write_doctype(name, fields, **kw):
    snake = name.lower().replace(" ", "_").replace("-", "_")
    check_not_taken(snake)
    check_fieldnames(name, fields)
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
              "search_fields", "default_print_format", "is_submittable"):
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
    """Sire / Dam block.

    StudLib holds ``father_id`` / ``mother_id`` as FKs back to ``horse``; those
    are the ``sire`` / ``dam`` Links. These flat fields stay because the print
    formats and the paper forms are built on them, and because an external
    parent has no Horse record to point at.
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


# ==========================================================================
# 1. Reference data mirrored from StudLib
# ==========================================================================
# Named Studbook Country, not Country: Frappe ships its own Country doctype
# and a second one of that name silently replaces it.
write_doctype(
    "Studbook Country",
    [
        data("country_name", "Country Name", reqd=1, unique=1, in_list_view=1),
        data("alpha2", "ISO Alpha-2", in_list_view=1, length=2),
        data("alpha3", "ISO Alpha-3", in_list_view=1, length=3),
        data("numeric_code", "ISO Numeric Code", length=3),
        col("col_country"),
        check("is_local", "Local Country", 0, in_list_view=1,
              description="The one country this studbook authority operates in. "
                          "A horse born here is Local; anywhere else is Imported."),
        studbook_id(),
    ],
    autoname="field:country_name",
    naming_rule="By fieldname",
    search_fields="alpha2,alpha3",
    allow_rename=1,
)

write_doctype(
    "Horse Color",
    [
        data("color_name", "Color Name", reqd=1, in_list_view=1),
        data("short_name", "Short Name", in_list_view=1,
             description="Abbreviation used on certificates, e.g. b. / ch. / gr."),
        col("col_color"),
        select("horse_breed", "Breed", BREEDS.strip(), reqd=1, in_list_view=1,
               in_standard_filter=1),
        select("validation_rule", "Inheritance Rule", "\nBoth Parents\nAt Least One Parent"),
        studbook_id(),
    ],
    # colors are unique per breed, so "Bay" exists twice
    autoname="format:{color_name} ({horse_breed})",
    naming_rule="Expression",
    title_field="color_name",
    show_title_field_in_link=1,
    search_fields="short_name",
)

write_doctype(
    "Book Type",
    [
        data("code", "Code", reqd=1, in_list_view=1),
        data("authority", "Issuing Authority", in_list_view=1),
        col("col_book_type"),
        select("horse_breed", "Breed", BREEDS.strip(), reqd=1, in_list_view=1,
               in_standard_filter=1),
        link("issuing_country", "Country", "Studbook Country"),
        check("is_libyan", "National Studbook"),
        studbook_id(),
    ],
    autoname="format:{code} ({horse_breed})",
    naming_rule="Expression",
    title_field="authority",
    search_fields="code,authority",
)

write_doctype(
    "Horse Event Type",
    [
        data("event_type", "Event Type", reqd=1, unique=1, in_list_view=1,
             description="The StudLib enum, e.g. CHANGE_OWNER."),
        data("description", "Description", in_list_view=1),
        col("col_event_type"),
        check("selectable", "Selectable", 1, in_list_view=1),
        studbook_id(),
    ],
    autoname="field:event_type",
    naming_rule="By fieldname",
    title_field="description",
    show_title_field_in_link=1,
    allow_rename=1,
)


# ==========================================================================
# 2. Owners
# ==========================================================================
write_doctype(
    "Horse Owner",
    [
        series("OWN-.#####\n"),
        sec("sec_name"),
        {"fieldname": "owner_name_ar", "fieldtype": "Data", "label": "Name (Arabic)",
         "reqd": 1, "in_list_view": 1, "in_standard_filter": 1},
        {"fieldname": "owner_name_en", "fieldtype": "Data", "label": "Name (English)",
         "reqd": 1, "in_list_view": 1},
        data("suffix", "Suffix", unique=1,
             description="Globally unique short identifier printed on certificates."),
        col("col_kind"),
        check("business", "Business / Farm / Syndicate", 0, in_list_view=1),
        data("business_number", "Business Number", depends_on="eval:doc.business"),
        {"fieldname": "national_id", "fieldtype": "Data", "label": "National ID No",
         "depends_on": "eval:!doc.business"},
        {"fieldname": "passport_no", "fieldtype": "Data", "label": "Passport No",
         "depends_on": "eval:!doc.business"},
        data("farm_name", "Farm / Stud Name"),

        sec("sec_contact", "Contact"),
        {"fieldname": "phone", "fieldtype": "Data", "label": "Phone No",
         "options": "Phone", "in_list_view": 1},
        {"fieldname": "email", "fieldtype": "Data", "label": "Email", "options": "Email"},
        col("col_address"),
        {"fieldname": "address", "fieldtype": "Small Text", "label": "Street Address"},
        {"fieldname": "city", "fieldtype": "Data", "label": "City"},
        data("region", "Region / State"),
        data("postal_code", "Postal Code"),
        link("owner_country", "Country", "Studbook Country"),

        sec("sec_location", "Location"),
        {"fieldname": "latitude", "fieldtype": "Float", "label": "Latitude", "precision": "6"},
        col("col_longitude"),
        {"fieldname": "longitude", "fieldtype": "Float", "label": "Longitude", "precision": "6"},

        sec("sec_note"),
        {"fieldname": "note", "fieldtype": "Small Text", "label": "Internal Note",
         "description": "Never printed on official documents."},
        studbook_id(),
    ],
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    title_field="owner_name_en",
    show_title_field_in_link=1,
    search_fields="owner_name_ar,phone,national_id",
    allow_rename=1,
)


# ==========================================================================
# 3. Child tables
# ==========================================================================
# StudLib horse_owner / horse_breeder are both M:N horse <-> owner, so one
# child doctype serves both tables on the Horse.
write_doctype(
    "Horse Party",
    [
        # "party", not "owner": every Frappe document already has an `owner`
        # field, and a Link of that name is silently filled with the session
        # user instead of what you set.
        link("party", "Owner", "Horse Owner", in_list_view=1, reqd=1, columns=3),
        fetch("owner_name_en", "Name", "party.owner_name_en", "Data"),
        fetch("national_id", "National ID", "party.national_id", "Data"),
        date("since", "Since", in_list_view=1, columns=2),
        integer("studbook_owner_id", "Studbook Owner ID", read_only=1, hidden=1),
    ],
    istable=1,
)

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

# the owners on either side of a CHANGE_OWNER event. Name kept alongside the
# Link because the event may name an owner we have not mirrored yet.
write_doctype(
    "Horse Event Owner",
    [
        link("party", "Owner", "Horse Owner", in_list_view=1, columns=3),
        data("owner_name", "Name", in_list_view=1, columns=4),
        data("national_id", "National ID", in_list_view=1, columns=3),
        integer("studbook_owner_id", "Studbook Owner ID", read_only=1, hidden=1),
    ],
    istable=1,
)

# HMS Settings: what an incoming event turns into, without a deploy
write_doctype(
    "Horse Event Action",
    [
        link("event_type", "Event Type", "Horse Event Type", in_list_view=1, reqd=1,
             columns=2),
        check("enabled", "Enabled", 1, in_list_view=1, columns=1),
        link("target_doctype", "Creates", "DocType", in_list_view=1, columns=3),
        link("document_category", "Document Category", "Horse Document Category",
             in_list_view=1, columns=3),
        link("notify_role", "Notify Role", "Role", in_list_view=1, columns=2),
    ],
    istable=1,
)


# ==========================================================================
# 4. Documents - the settings doctype and the transaction
# ==========================================================================
write_doctype(
    "Horse Document Category",
    [
        data("category", "Category", reqd=1, unique=1, in_list_view=1),
        check("disabled", "Disabled", 0, in_list_view=1),
        col("col_category"),
        integer("sort_order", "Sort Order", default="0"),
        {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},

        sec("sec_applicability", "Applies To"),
        check("applies_to_local", "Local Horses", 1, in_list_view=1),
        check("required_for_local", "Required for Local", 0,
              depends_on="eval:doc.applies_to_local"),
        col("col_imported"),
        check("applies_to_imported", "Imported Horses", 1, in_list_view=1),
        check("required_for_imported", "Required for Imported", 0,
              depends_on="eval:doc.applies_to_imported"),
        col("col_scope"),
        select("applies_to_sex", "Sex", "All\nMales\nFemales", default="All",
               description="Males covers Male, Stallion, Gelding, Cryptorchid and "
                           "Monorchid. Females covers Female and Broodmare."),
        select("applies_to_breed", "Breed", "All\nArabian\nThoroughbred", default="All"),
        link("applies_to_country", "Country of Origin", "Studbook Country",
             description="Leave empty to apply to every country of origin."),

        sec("sec_limits", "Limits"),
        integer("max_count", "Maximum Uploads", default="1",
                description="How many documents of this category one horse may have. "
                            "0 means no limit."),
        col("col_expiry"),
        check("has_expiry", "Has Expiry Date"),

        sec("sec_companions", "Required Details"),
        check("needs_document_date", "Date"),
        data("document_date_label", "Date Label", default="Date",
             depends_on="eval:doc.needs_document_date"),
        check("needs_reference_no", "Reference Number"),
        data("reference_no_label", "Reference Number Label", default="Reference Number",
             depends_on="eval:doc.needs_reference_no"),
        col("col_companions"),
        check("needs_doc_status", "Approval Status"),
        check("needs_season", "Season"),
        check("needs_notes", "Note"),
    ],
    autoname="field:category",
    naming_rule="By fieldname",
    search_fields="description",
    allow_rename=1,
)

write_doctype(
    "Horse Document",
    [
        series("HDOC-.YYYY.-.#####\n"),
        sec("sec_what"),
        link("horse", "Horse", "Horse", reqd=1, in_list_view=1, in_standard_filter=1),
        link("category", "Category", "Horse Document Category", reqd=1, in_list_view=1,
             in_standard_filter=1),
        {"fieldname": "attachment", "fieldtype": "Attach", "label": "Attachment",
         "reqd": 1, "in_list_view": 1},
        col("col_details"),
        # the five companion shapes every category in the mapping needs;
        # which of them show and which are required comes from the category.
        date("document_date", "Date", in_list_view=1),
        data("reference_no", "Reference Number"),
        select("doc_status", "Approval Status", "\nApproved\nDeclined"),
        data("season", "Season"),
        date("expiry_date", "Expiry Date"),
        {"fieldname": "notes", "fieldtype": "Small Text", "label": "Note"},

        sec("sec_source", "Source"),
        link("source_event", "From Event", "Horse Event", read_only=1, no_copy=1),
        link("source_form_type", "From Form Type", "DocType", read_only=1, no_copy=1),
        {"fieldname": "source_form", "fieldtype": "Dynamic Link", "label": "From Form",
         "options": "source_form_type", "read_only": 1, "no_copy": 1},
        col("col_source"),
        check("is_complete", "Complete", 0, read_only=1, no_copy=1),
        integer("studbook_file_id", "Studbook File ID", read_only=1, no_copy=1, hidden=1),
    ],
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    title_field="category",
    search_fields="horse,category,reference_no",
)


# ==========================================================================
# 5. Events
# ==========================================================================
write_doctype(
    "Horse Event",
    [
        series("HEV-.YYYY.-.#####\n"),
        sec("sec_event"),
        link("event_type", "Event Type", "Horse Event Type", reqd=1, in_list_view=1,
             in_standard_filter=1),
        date("event_date", "Event Date", in_list_view=1),
        link("horse", "Horse", "Horse", in_list_view=1, in_standard_filter=1),
        col("col_event"),
        select("notification_status", "Status",
               "New\nAcknowledged\nProcessed\nIgnored", default="New",
               in_list_view=1, in_standard_filter=1, no_copy=1),
        # indexed rather than unique for the same reason as studbook_id; the
        # poller checks for an existing id before it inserts
        integer("studbook_event_id", "Studbook Event ID", read_only=1,
                search_index=1, no_copy=1),
        data("unresolved_horse", "Unresolved Horse", read_only=1, no_copy=1,
             depends_on="eval:!doc.horse",
             description="The event names a studbook horse this site has not "
                         "synced yet. It links itself on the next horse sync."),

        sec("sec_detail", "Details"),
        {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
        {"fieldname": "additional_information", "fieldtype": "Small Text",
         "label": "Additional Information"},
        link("event_country", "Country", "Studbook Country",
             description="Origin or destination for Import and Export events."),
        col("col_detail"),
        link("secondary_horse", "Secondary Horse", "Horse",
             description="The stallion in a Covered event, the sire in a New Foal."),
        link("offspring_horse", "Offspring", "Horse"),
        check("cover", "Covered"),
        check("pregnant", "Pregnant"),
        check("twins", "Twins"),
        select("foal_sex", "Foal Sex", SEXES),

        sec("sec_owners", "Ownership Change"),
        {"fieldname": "old_owners", "fieldtype": "Table", "label": "Previous Owners",
         "options": "Horse Event Owner"},
        col("col_owners"),
        {"fieldname": "new_owners", "fieldtype": "Table", "label": "New Owners",
         "options": "Horse Event Owner"},

        sec("sec_result", "What Came Of It"),
        link("created_document", "Document", "Horse Document", read_only=1, no_copy=1),
        col("col_result"),
        link("created_form_type", "Form Type", "DocType", read_only=1, no_copy=1),
        {"fieldname": "created_form", "fieldtype": "Dynamic Link", "label": "Form",
         "options": "created_form_type", "read_only": 1, "no_copy": 1},
    ],
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    title_field="event_type",
    search_fields="horse,event_type,event_date",
)


# ==========================================================================
# 6. Horse - a mirror of the StudLib horse table
# ==========================================================================
horse_fields = [
    tab("identity_tab", "Identity"),
    series("LY-.YYYY.-.#####\n"),
    sec("sec_names"),
    {"fieldname": "name_en", "fieldtype": "Data", "label": "Name (English)", "reqd": 1,
     "in_list_view": 1, "in_standard_filter": 1,
     "description": "The official registered name. StudLib <code>name</code>."},
    {"fieldname": "name_ar", "fieldtype": "Data", "label": "Name (Arabic)", "reqd": 1,
     "in_list_view": 1, "description": "StudLib <code>local_name</code>."},
    data("name_suffix", "Name Suffix", length=10,
         description="Appended when several horses share a name."),
    col("col_identity"),
    select("breed", "Breed", BREEDS, reqd=1, in_standard_filter=1),
    select("gender", "Sex", SEXES, reqd=1, in_list_view=1, in_standard_filter=1),
    select("horse_classification", "Classification", CLASSIFICATION),
    select("status", "Registration Status", REG_STATUS, in_standard_filter=1),
    col("col_documents"),
    select("documents_status", "Documents", DOC_STATUS, read_only=1, default="Not Yet",
           in_list_view=1, in_standard_filter=1, no_copy=1),
    select("origin", "Country of Origin", "\nLocal\nImported", read_only=1,
           in_standard_filter=1,
           description="Derived from the birthplace country's Local flag."),

    sec("sec_registry", "Registry Numbers"),
    data("registry_id", "Registry ID"),
    data("previous_registry_id", "Previous Registry ID"),
    data("ueln_no", "UELN No", length=15, description="StudLib <code>ueln</code>."),
    col("col_registry"),
    data("legacy_registry_id", "Legacy Registry ID"),
    data("legacy_ueln", "Legacy UELN", length=15),
    data("studbook_uuid", "Studbook UUID", read_only=1, unique=1, no_copy=1,
         description="The StudLib <code>uuid</code>. This is what the sync keys on."),
    studbook_id(),

    sec("sec_transponder", "Identification"),
    data("microchip_no", "Microchip No", length=15,
         description="StudLib <code>transponder_code</code>."),
    data("second_microchip_no", "Second Microchip No"),
    data("transponder_site", "Transponder Site"),
    col("col_transponder"),
    link("color", "Color", "Horse Color"),
    data("strain", "Strain", depends_on="eval:doc.breed=='Arabian'",
         description="Arabian strain, e.g. Kuhailan, Saqlawi, Dahman."),
    data("blood_code", "Blood Code"),
    check("dna_sample_exists", "DNA Sample Collected"),

    sec("sec_birth", "Birth"),
    date("date_of_birth", "Date of Birth"),
    link("birthplace_country", "Birthplace Country", "Studbook Country"),
    data("place_of_birth", "Place of Birth"),
    date("date_of_declaration", "Date of Declaration"),
    col("col_life"),
    date("date_of_death", "Date of Death"),
    select("life_status", "Status of Life", "Alive\nDeceased", default="Alive",
           read_only=1, in_list_view=1,
           description="Derived from the date of death."),
    data("current_location", "Current Location"),
    date("notification_date", "Notification Date"),

    sec("sec_control", "Signalement"),
    date("date_of_control", "Date of Control"),
    col("col_control"),
    data("controlled_by", "Controlled By"),

    sec("sec_movement", "Import & Export"),
    date("date_of_importing", "Date of Import"),
    link("import_country", "Import Country", "Studbook Country"),
    col("col_export"),
    date("date_of_exporting", "Date of Export"),
    link("export_country", "Export Country", "Studbook Country"),

    sec("sec_notes"),
    {"fieldname": "notes", "fieldtype": "Text", "label": "Notes"},

    tab("studbook_tab", "Studbook"),
    sec("sec_current_book", "Current Studbook"),
    date("date_of_registration", "Date of Registration"),
    link("book_type", "Book Type", "Book Type"),
    integer("book_number", "Volume"),
    integer("book_page", "Page"),
    integer("book_appendix_number", "Appendix"),
    col("col_previous_book"),
    link("previous_book_type", "Previous Book Type", "Book Type"),
    integer("previous_book_number", "Previous Volume"),
    integer("previous_book_page", "Previous Page"),
    integer("previous_book_appendix_number", "Previous Appendix"),

    tab("pedigree_tab", "Pedigree"),
    sec("sec_parents", "Parents"),
    link("sire", "Sire", "Horse", description="StudLib <code>father_id</code>."),
    col("col_dam_link"),
    link("dam", "Dam", "Horse", description="StudLib <code>mother_id</code>."),
    sec("sec_sire", "Sire's Data"),
] + parent_data("sire", "Sire") + [
    sec("sec_dam", "Dam's Data"),
] + parent_data("dam", "Dam") + [

    tab("ownership_tab", "Ownership"),
    sec("sec_owners", "Owners"),
    {"fieldname": "owners", "fieldtype": "Table", "label": "Owners",
     "options": "Horse Party",
     "description": "A horse may be owned by several parties at once."},
    sec("sec_breeders", "Breeders"),
    {"fieldname": "breeders", "fieldtype": "Table", "label": "Breeders",
     "options": "Horse Party",
     "description": "The owners of the dam at the time of foaling."},

    sec("sec_owner", "Primary Owner"),
] + party_data("owner", "Owner") + [
    {"fieldname": "owner_since", "fieldtype": "Date", "label": "Owner Since"},
    sec("sec_breeder", "Primary Breeder"),
] + party_data("breeder", "Breeder") + [
    sec("sec_history", "History"),
    {"fieldname": "ownership_history", "fieldtype": "Table", "label": "Ownership History",
     "options": "Horse Ownership Log", "read_only": 1},
    {"fieldname": "name_history", "fieldtype": "Table", "label": "Name History",
     "options": "Horse Name Log", "read_only": 1},
]

write_doctype(
    "Horse",
    horse_fields,
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    title_field="name_en",
    show_title_field_in_link=1,
    search_fields="name_ar,name_en,microchip_no,registry_id",
    allow_rename=1,
)


# ==========================================================================
# 7. Registration Form for Local Horses
# ==========================================================================
reg_fields = [
    tab("horse_data_tab", "Horse Data"),
    series("REG-LOC-.YYYY.-.#####\n"),
    sec("sec_horse"),
    {"fieldname": "gender", "fieldtype": "Select", "label": "Sex",
     "options": "\nMale\nFemale", "reqd": 1, "in_list_view": 1},
    {"fieldname": "color", "fieldtype": "Link", "label": "Color", "options": "Horse Color"},
    {"fieldname": "breed", "fieldtype": "Select", "label": "Breed", "options": BREEDS},
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
    link("source_event", "From Event", "Horse Event", read_only=1, no_copy=1),
]

write_doctype(
    "Registration Form for Local Horses",
    reg_fields,
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    search_fields="name_1_en,owner_name_en,horse",
    default_print_format="Local-Bred Horse Registration Form",
)


# ==========================================================================
# 8. Owner Change Form
# ==========================================================================
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
        fetch("color", "Color", "horse.color", "Link", "Horse Color"),
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
    link("source_event", "From Event", "Horse Event", read_only=1, no_copy=1),
]

write_doctype(
    "Owner Change Form",
    ocf_fields,
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    search_fields="horse,new_owner_name_en",
    default_print_format="Horse Transfer of Ownership Form",
)


# ==========================================================================
# 9. Name Change Form
# ==========================================================================
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
    link("source_event", "From Event", "Horse Event", read_only=1, no_copy=1),
]

write_doctype(
    "Name Change Form",
    ncf_fields,
    autoname="naming_series:",
    naming_rule="By \"Naming Series\" field",
    search_fields="horse,approved_name_en",
)

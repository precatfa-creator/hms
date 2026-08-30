"""Shared logic for the Documents tab of the Horse.

Every document is an Attach field (``doc_<key>``) on the Horse plus the
companion fields next to it. A document counts as complete only when the attachment *and* all of its
companion fields are filled. ``status`` is derived from the starred (required)
documents only, which differ for local and imported horses.
"""

# key -> companion fieldnames
DOC_COMPANIONS = {
	"registration_form": ["doc_registration_date"],
	"breeding_certificate": ["doc_breeding_certificate_no"],
	"dna_card": ["doc_dna_status"],
	"marking": ["doc_marking_by", "doc_marking_date"],
	"owner_id": ["doc_owner_id_date"],
	"passport": ["doc_passport_no"],
	"export_certificate": ["doc_export_certificate_no", "doc_export_date"],
	"covering_certificate": ["doc_covering_season"],
	"covering_agreement": ["doc_covering_agreement_season"],
	"owner_change_form": ["doc_owner_change_date"],
	"death_form": ["doc_death_event_date"],
	"others": ["doc_others_note"],
}

# the starred documents of the mapping, per origin
REQUIRED = {
	"Local": ["registration_form", "breeding_certificate", "dna_card", "marking", "owner_id"],
	"Imported": ["registration_form", "dna_card", "owner_id", "passport", "export_certificate"],
}

ALL_FIELDS = [f"doc_{key}" for key in DOC_COMPANIONS] + [
	field for companions in DOC_COMPANIONS.values() for field in companions
]

NOT_YET = "Not Yet"
PARTIAL = "Partially Completed"
COMPLETED = "Completed"


def is_complete(doc, key):
	if not doc.get(f"doc_{key}"):
		return False
	return all(doc.get(field) for field in DOC_COMPANIONS[key])


def compute_status(doc):
	required = REQUIRED.get(doc.get("origin") or "Local", REQUIRED["Local"])
	done = sum(1 for key in required if is_complete(doc, key))
	if done == len(required):
		return COMPLETED
	return PARTIAL if done else NOT_YET


def set_status(doc):
	doc.status = compute_status(doc)


def _self_check():
	local = {"origin": "Local"}
	assert compute_status(local) == NOT_YET

	local["doc_registration_form"] = "/files/a.pdf"
	assert compute_status(local) == NOT_YET, "attachment without its date is not done"

	local["doc_registration_date"] = "2026-01-01"
	assert compute_status(local) == PARTIAL

	for key in REQUIRED["Local"]:
		local[f"doc_{key}"] = "/files/a.pdf"
		for field in DOC_COMPANIONS[key]:
			local[field] = "x"
	assert compute_status(local) == COMPLETED

	# same set is only partial for an imported horse: passport + export cert missing
	imported = dict(local, origin="Imported")
	assert compute_status(imported) == PARTIAL

	for key in ("passport", "export_certificate"):
		imported[f"doc_{key}"] = "/files/a.pdf"
		for field in DOC_COMPANIONS[key]:
			imported[field] = "x"
	assert compute_status(imported) == COMPLETED

	# optional documents never affect the status
	assert compute_status({"origin": "Local", "doc_others": "/files/a.pdf"}) == NOT_YET
	print("documents self-check ok")


if __name__ == "__main__":
	_self_check()

#!/usr/bin/env python3
"""Leave HMS as the only workspace in the desk sidebar.

	cd frappe-bench/sites && ../env/bin/python ../apps/hms/scripts/only_hms_workspace.py <site>
	                                                                                   <site> --restore

Hiding is done by clearing ``public``, not ``is_hidden``: a Workspace Manager -
and Administrator always counts as one - sees hidden workspaces anyway, but a
non-public workspace only shows to the user named in ``for_user``.

A migrate re-imports the workspaces of every installed app and puts them back,
so run this again afterwards.
"""

import sys

import frappe

KEEP = "HMS"


def apply(restore=False):
	names = frappe.get_all(
		"Workspace",
		filters={"name": ("!=", KEEP), "public": 0 if restore else 1},
		pluck="name",
	)
	for name in names:
		frappe.db.set_value("Workspace", name, "public", 1 if restore else 0)

	frappe.db.commit()
	frappe.clear_cache()

	visible = frappe.get_all("Workspace", filters={"public": 1}, pluck="name")
	print(("restored" if restore else "hidden") + f": {len(names)}")
	print("sidebar now shows:", sorted(visible))


if __name__ == "__main__":
	site = sys.argv[1]
	frappe.init(site=site)
	frappe.connect()
	frappe.set_user("Administrator")
	apply(restore="--restore" in sys.argv)

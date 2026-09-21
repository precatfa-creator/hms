#!/usr/bin/env python3
"""Capture desk screenshots of the whole HMS app into apps/hms/screenshots.

Drives a Chrome started with --remote-debugging-port over CDP, so form tabs can
be clicked before each shot.

	google-chrome --headless=new --remote-debugging-port=9222 \
		--window-size=1600,1200 --user-data-dir=/tmp/hms-chrome &
	cd frappe-bench/sites && ../env/bin/python ../apps/hms/scripts/capture_screenshots.py <sid>
"""

import base64
import json
import os
import sys
import time

import requests
import websocket

SID = sys.argv[1]
BASE = "http://localhost:8000"
OUT = "/home/omix/frappe-bench/apps/hms/screenshots"
DEBUG = "http://127.0.0.1:9222"

# label, route, tab to click (None = whatever opens first)
SHOTS = [
	# the workspace
	("01-workspace", "/app/hms", None),

	# the horse registry
	("02-horse-list", "/app/horse", None),
	("03-horse-list-report", "/app/horse/view/report", None),

	# a horse that came from the studbook: registry id, uuid, derived origin
	("04-horse-synced-identity", "/app/horse/LY-2026-00010", "Identity"),
	("05-horse-synced-studbook", "/app/horse/LY-2026-00010", "Studbook"),
	("06-horse-synced-ownership", "/app/horse/LY-2026-00010", "Ownership"),
	("07-horse-synced-connections", "/app/horse/LY-2026-00010", "@.form-links"),
	# a synced foal, whose sire and dam are real Horse links
	("08-horse-foal-pedigree", "/app/horse/LY-2026-00009", "Pedigree"),
	("09-horse-foal-identity", "/app/horse/LY-2026-00009", "Identity"),

	# the three document states
	("10-horse-completed-identity", "/app/horse/LY-2026-00011", "Identity"),
	("11-horse-completed-connections", "/app/horse/LY-2026-00011", "@.form-links"),
	("12-horse-partial-connections", "/app/horse/LY-2026-00024", "@.form-links"),
	("13-horse-notyet-connections", "/app/horse/LY-2026-00022", "@.form-links"),
	("14-horse-new", "/app/horse/new", "Identity"),

	# documents
	("15-document-list", "/app/horse-document", None),
	("16-document-marking", "/app/horse-document/HDOC-2026-00045", None),
	("17-document-owner-id", "/app/horse-document/HDOC-2026-00041", None),
	("18-document-new", "/app/horse-document/new", None),
	("19-category-list", "/app/horse-document-category", None),
	("20-category-registration-form", "/app/horse-document-category/Registration Form", None),
	("21-category-covering-certificate", "/app/horse-document-category/Covering Certificate", None),
	("22-category-owner-id", "/app/horse-document-category/Owner ID", None),

	# events
	("23-event-list", "/app/horse-event", None),
	("24-event-new-status", "/app/horse-event/HEV-2026-00011", None),
	("25-event-processed", "/app/horse-event/HEV-2026-00012", None),
	("26-event-import", "/app/horse-event/HEV-2026-00009", None),
	("27-event-type-list", "/app/horse-event-type", None),

	# owners and reference data
	("28-owner-list", "/app/horse-owner", None),
	("29-owner-record", "/app/horse-owner/OWN-00001", None),
	("30-country-list", "/app/studbook-country", None),
	("31-color-list", "/app/horse-color", None),
	("32-book-type-list", "/app/book-type", None),

	# the sync and the poll
	("33-settings-studbook", "/app/hms-settings", "Studbook"),
	("34-settings-events", "/app/hms-settings", "Events"),

	# the paper forms
	("35-registration-list", "/app/registration-form-for-local-horses", None),
	("36-registration-horse-data", "/app/registration-form-for-local-horses/REG-LOC-2026-00008", "Horse Data"),
	("37-registration-names", "/app/registration-form-for-local-horses/REG-LOC-2026-00008", "Proposed Names"),
	("38-registration-pedigree", "/app/registration-form-for-local-horses/REG-LOC-2026-00008", "Pedigree"),
	("39-registration-owner", "/app/registration-form-for-local-horses/REG-LOC-2026-00008", "Owner & Breeder"),
	("40-owner-change-list", "/app/owner-change-form", None),
	("41-owner-change-horse", "/app/owner-change-form/OCF-2026-00004", "Horse Information"),
	("42-owner-change-parties", "/app/owner-change-form/OCF-2026-00004", "Parties"),
	("43-name-change-list", "/app/name-change-form", None),
	("44-name-change-names", "/app/name-change-form/NCF-2026-00001", "Names"),

	# print
	("45-print-registration", "/app/print/Registration Form for Local Horses/REG-LOC-2026-00008", None),
	("46-print-transfer", "/app/print/Owner Change Form/OCF-2026-00004", None),
]


class CDP:
	def __init__(self):
		targets = requests.get(f"{DEBUG}/json/list").json()
		page = next(t for t in targets if t["type"] == "page")
		# Chrome >=111 rejects a handshake whose Origin it was not told to allow;
		# an empty origin sidesteps it, and so does --remote-allow-origins=*
		self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60,
		                                      max_size=100 * 1024 * 1024, origin="")
		self.id = 0
		self.send("Page.enable")
		self.send("Runtime.enable")
		self.send("Network.enable")

	def send(self, method, **params):
		self.id += 1
		self.ws.send(json.dumps({"id": self.id, "method": method, "params": params}))
		while True:
			message = json.loads(self.ws.recv())
			if message.get("id") == self.id:
				if "error" in message:
					raise RuntimeError(f"{method}: {message['error']}")
				return message.get("result", {})

	def js(self, expression):
		result = self.send("Runtime.evaluate", expression=expression, awaitPromise=True,
		                   returnByValue=True)
		return result.get("result", {}).get("value")

	def goto(self, url):
		self.send("Page.navigate", url=url)

	def screenshot_element(self, path, selector, pad=20):
		"""Capture just one region. Frappe 15 renders the connections at the
		bottom of the form rather than in a tab of their own, so a full-page
		shot buries them.

		Shot full-page and cropped afterwards, rather than clipped by CDP: the
		sticky page header is position:fixed, so it paints over any clip taken
		with a short viewport.
		"""
		from PIL import Image

		self.screenshot(path)
		box = self.js(ELEMENT_BOX % json.dumps(selector))
		if not box:
			return None

		image = Image.open(path)
		left = max(int(box["x"]) - pad, 0)
		top = max(int(box["y"]) - pad, 0)
		right = min(int(box["x"] + box["width"]) + pad, image.width)
		bottom = min(int(box["y"] + box["height"]) + pad, image.height)
		if bottom - top < 40 or right - left < 40:
			return None
		image.crop((left, top, right, bottom)).save(path)
		return bottom - top, os.path.getsize(path)

	def screenshot(self, path):
		"""Grow the viewport to the full content height first, so nothing is cut off."""
		height = int(self.js(CONTENT_HEIGHT) or 1200)
		self.send("Emulation.setDeviceMetricsOverride", width=1600, height=height,
		          deviceScaleFactor=1, mobile=False)
		time.sleep(1.5)  # charts redraw on resize
		data = self.send("Page.captureScreenshot", format="png", captureBeyondViewport=True)
		self.send("Emulation.clearDeviceMetricsOverride")
		with open(path, "wb") as fh:
			fh.write(base64.b64decode(data["data"]))
		return height, os.path.getsize(path)


READY = """
(() => {
	if (!window.frappe || !frappe.router) return false;
	if (document.querySelector('.freeze, .page-loading, .msgprint-dialog')) return false;
	if (!document.querySelector('.page-head .title-text, .print-format, .layout-main-section')) return false;

	// no widget may still say Loading...
	const widgets = [...document.querySelectorAll('.widget')];
	if (widgets.some(w => /Loading[.]{3}/.test(w.innerText))) return false;

	// every number card shows a figure
	const cards = [...document.querySelectorAll('.number-widget-box')];
	if (cards.some(c => !/[0-9]/.test(c.innerText))) return false;

	// every chart has drawn its svg
	const charts = [...document.querySelectorAll('.chart-container')];
	if (charts.some(c => !c.querySelector('svg'))) return false;

	// a list view has rows, or says it has none
	const list = document.querySelector('.list-view-container');
	if (list && !list.querySelector('.list-row-container, .no-result, .msg-box')) return false;

	return true;
})()
"""

ELEMENT_BOX = """
(() => {
	const el = document.querySelector(%s);
	if (!el) return null;
	// page coordinates, not viewport: the crop happens against a full-page shot
	const r = el.getBoundingClientRect();
	return {x: r.x + window.scrollX, y: r.y + window.scrollY,
	        width: r.width, height: r.height};
})()
"""

# The sidebar, the comment box and the activity feed are most of a form's
# height and none of its meaning. Hiding them lets the form itself use the full
# width, so it is still legible once scaled onto a page.
HIDE_CHROME = """
(() => {
	const gone = ['.layout-side-section', '.form-footer', '.comment-box',
	              '.new-timeline', '.form-message', '.freeze'];
	gone.forEach(sel => document.querySelectorAll(sel)
		.forEach(el => { el.style.display = 'none'; }));
	const main = document.querySelector('.layout-main-section-wrapper');
	if (main) { main.classList.remove('col-lg-8'); main.classList.add('col-lg-12'); }
	return true;
})()
"""

CONTENT_HEIGHT = """
(() => {
	const main = document.querySelector('.layout-main-section');
	const height = Math.max(document.body.scrollHeight, main ? main.scrollHeight + 260 : 0);
	return Math.min(Math.max(height, 900), 8000);
})()
"""

CLICK_TAB = """
(() => {
	const label = %s;
	const tabs = [...document.querySelectorAll('.form-tabs .nav-link, .form-tabs a')];
	const tab = tabs.find(t => t.textContent.trim().toLowerCase() === label.toLowerCase());
	if (!tab) return tabs.map(t => t.textContent.trim());
	tab.click();
	return true;
})()
"""


def wait_ready(cdp, timeout=40):
	deadline = time.time() + timeout
	while time.time() < deadline:
		if cdp.js(READY):
			time.sleep(1.5)  # let charts and grids settle
			return True
		time.sleep(0.4)
	return False


def main():
	os.makedirs(OUT, exist_ok=True)
	cdp = CDP()
	cdp.send("Network.setCookie", name="sid", value=SID, domain="localhost", path="/")
	cdp.goto(f"{BASE}/app/hms")
	wait_ready(cdp)

	for label, route, tab in SHOTS:
		cdp.goto(BASE + requests.utils.quote(route, safe="/?=&"))
		ok = wait_ready(cdp)
		cdp.js(HIDE_CHROME)
		time.sleep(0.6)

		selector = None
		if tab and tab.startswith("@"):
			selector, tab = tab[1:], None
		if tab:
			found = cdp.js(CLICK_TAB % json.dumps(tab))
			if found is not True:
				print(f"  ! {label}: tab {tab!r} not found, tabs are {found}")
			time.sleep(1.0)

		path = os.path.join(OUT, f"{label}.png")
		if selector:
			time.sleep(1.0)
			result = cdp.screenshot_element(path, selector)
			if not result:
				print(f"  ! {label}: {selector} not on the page")
				continue
			height, size = result
		else:
			height, size = cdp.screenshot(path)
		print(f"{label:<32} {'ok ' if ok else 'SLOW'} {height:>5}px {size // 1024:>5} KB")


if __name__ == "__main__":
	main()

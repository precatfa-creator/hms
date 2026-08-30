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
	("01-workspace-hms", "/app/hms", None),
	("02-horse-list", "/app/horse", None),
	("03-horse-list-report", "/app/horse/view/report", None),
	("04-horse-completed-identity", "/app/horse/LY-2026-00003", "Identity"),
	("05-horse-completed-pedigree", "/app/horse/LY-2026-00003", "Pedigree"),
	("06-horse-completed-ownership", "/app/horse/LY-2026-00003", "Ownership"),
	("07-horse-completed-documents", "/app/horse/LY-2026-00003", "Documents"),
	("08-horse-partial-documents", "/app/horse/LY-2026-00011", "Documents"),
	("09-horse-notyet-documents", "/app/horse/LY-2026-00013", "Documents"),
	("10-horse-imported-identity", "/app/horse/LY-2026-00005", "Identity"),
	("11-horse-new-identity", "/app/horse/new", "Identity"),
	("12-horse-new-pedigree", "/app/horse/new", "Pedigree"),
	("13-horse-new-documents", "/app/horse/new", "Documents"),
	("14-owner-list", "/app/horse-owner", None),
	("15-owner-record", "/app/horse-owner/OWN-00001", None),
	("16-owner-new", "/app/horse-owner/new", None),
	("17-registration-list", "/app/registration-form-for-local-horses", None),
	("18-registration-horse-data", "/app/registration-form-for-local-horses/REG-LOC-2026-00005", "Horse Data"),
	("19-registration-names", "/app/registration-form-for-local-horses/REG-LOC-2026-00005", "Proposed Names"),
	("20-registration-pedigree", "/app/registration-form-for-local-horses/REG-LOC-2026-00005", "Pedigree"),
	("21-registration-owner", "/app/registration-form-for-local-horses/REG-LOC-2026-00005", "Owner & Breeder"),
	("22-registration-result", "/app/registration-form-for-local-horses/REG-LOC-2026-00005", "Registration"),
	("23-registration-new", "/app/registration-form-for-local-horses/new", "Horse Data"),
	("24-owner-change-list", "/app/owner-change-form", None),
	("25-owner-change-horse", "/app/owner-change-form/OCF-2026-00003", "Horse Information"),
	("26-owner-change-parties", "/app/owner-change-form/OCF-2026-00003", "Parties"),
	("27-owner-change-new", "/app/owner-change-form/new", "Horse Information"),
	("28-name-change-list", "/app/name-change-form", None),
	("29-name-change-horse", "/app/name-change-form/NCF-2026-00001", "Horse Information"),
	("30-name-change-names", "/app/name-change-form/NCF-2026-00001", "Names"),
	("31-name-change-new", "/app/name-change-form/new", "Horse Information"),
	("32-print-registration", "/app/print/Registration Form for Local Horses/REG-LOC-2026-00005", None),
	("33-print-transfer", "/app/print/Owner Change Form/OCF-2026-00003", None),
]


class CDP:
	def __init__(self):
		targets = requests.get(f"{DEBUG}/json/list").json()
		page = next(t for t in targets if t["type"] == "page")
		self.ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=60,
		                                      max_size=100 * 1024 * 1024)
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
	if (widgets.some(w => /Loading\.\.\./.test(w.innerText))) return false;

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
		if tab:
			found = cdp.js(CLICK_TAB % json.dumps(tab))
			if found is not True:
				print(f"  ! {label}: tab {tab!r} not found, tabs are {found}")
			time.sleep(1.0)
		height, size = cdp.screenshot(os.path.join(OUT, f"{label}.png"))
		print(f"{label:<32} {'ok ' if ok else 'SLOW'} {height:>5}px {size // 1024:>5} KB")


if __name__ == "__main__":
	main()

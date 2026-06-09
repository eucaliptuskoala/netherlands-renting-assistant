from playwright.sync_api import sync_playwright

from interface import RentProviderInterface
from model import House


def _first_of(obj, keys):
    for k in keys:
        v = obj.get(k)
        if v is not None and v != "":
            return v
    return None


class Xior(RentProviderInterface):
    PROPERTIES = [
        {
            "name": "Kronehoefstraat",
            "url": "https://www.xiorstudenthousing.eu/netherlands/eindhoven/kronehoefstraat-student-accommodation/",
        },
        {
            "name": "Zernikestraat",
            "url": "https://www.xiorstudenthousing.eu/netherlands/eindhoven/zernikestraat-student-accommodation/",
        },
    ]

    def __init__(self, city="eindhoven", price=[0, 9000], header=None):
        super().__init__(city, price)

    def Run(self):
        houses = []
        try:
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-gpu",
                    ],
                )
                page = browser.new_page(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 720},
                )

                page.route(
                    "**/*",
                    lambda route: route.abort()
                    if "challenges.cloudflare.com" in route.request.url
                    else route.continue_(),
                )

                for prop in self.PROPERTIES:
                    try:
                        prop_houses = self._scrape_property(page, prop)
                        houses.extend(prop_houses)
                        print(
                            f"    [debug] Xior {prop['name']}: {len(prop_houses)} listing(s)",
                            flush=True,
                        )
                    except Exception as e:
                        print(
                            f"    [error] Xior {prop['name']}: {e}",
                            flush=True,
                        )

                browser.close()
        except Exception as e:
            print(f"    [error] Xior browser startup: {e}", flush=True)

        return houses

    def _accept_cookies(self, page):
        try:
            btn = page.query_selector(".cky-btn-accept")
            if btn:
                btn.click()
                page.wait_for_timeout(500)
        except Exception:
            pass

    def _scrape_property(self, page, prop):
        page.goto(prop["url"], wait_until="load", timeout=30000)
        self._accept_cookies(page)

        page_id = str(page.evaluate("window.xior?.page_id") or "")
        semester_id = str(
            page.evaluate("document.getElementById('yardi-semester')?.value") or ""
        )
        ajax_url = str(page.evaluate("xiorajax?.ajaxurl") or "")
        building_name = str(
            page.evaluate("window.xior?.building_name") or prop["name"]
        )

        if not all([page_id, semester_id, ajax_url]):
            debug = (
                f"page_id={page_id} "
                f"semester={bool(semester_id)} "
                f"ajax={bool(ajax_url)}"
            )
            print(
                f"    [debug] Xior {prop['name']}: missing metadata {debug}",
                flush=True,
            )
            return []

        rooms = page.evaluate(
            """() => {
            const form = document.getElementById('yardi-modal-form');
            if (!form) return [];
            const inputs = form.querySelectorAll('input[name="room_type"]');
            const seen = {};
            inputs.forEach(el => {
                if (el.dataset.roomId && !seen[el.dataset.roomId]) {
                    seen[el.dataset.roomId] = true;
                }
            });
            return Object.keys(seen);
        }"""
        )

        if not rooms:
            print(
                f"    [debug] Xior {prop['name']}: no room types found",
                flush=True,
            )
            return []

        houses = []
        for room_id in rooms:
            result = page.evaluate(
                """async (args) => {
                const fd = new FormData();
                fd.append('action', 'yardi_room_availability');
                fd.append('property_page_id', args.page_id);
                fd.append('room_type_id', args.room_id);
                fd.append('semester_id', args.semester_id);
                fd.append('cf-turnstile-response', '');
                try {
                    const resp = await fetch(args.ajax_url, { method: 'POST', body: fd });
                    return await resp.json();
                } catch (e) {
                    return {error: e.message};
                }
            }""",
                {
                    "page_id": page_id,
                    "room_id": room_id,
                    "semester_id": semester_id,
                    "ajax_url": ajax_url,
                },
            )

            if result.get("error"):
                print(
                    f"    [error] Xior {prop['name']} room {room_id}: {result['error']}",
                    flush=True,
                )
                continue

            if not result.get("success"):
                continue

            for unit in result.get("data", {}).get("units", []):
                unit_id = _first_of(unit, ["apartmentId", "unit_id", "id", "UnitID"])
                room_name = _first_of(unit, ["apartmentName", "unit_name", "room_name", "name"])

                price = int(float(
                    _first_of(unit, ["minimumRent", "rent", "price", "MinimumRent", "minRent"])
                    or 0
                ))
                if not self._isPriceMatched(price):
                    continue

                house_id = (
                    f"xior-{unit_id}" if unit_id else f"xior-{building_name.lower()}-{room_id}"
                )
                sqm = _first_of(unit, ["sqM", "sqm", "size_sqm", "area", "size", "SquareMeters"])

                houses.append(
                    House(
                        id=house_id,
                        URL=prop["url"],
                        address=f"{building_name} - {room_name}" if room_name else building_name,
                        price=price,
                        living_area=f"{sqm} m\u00b2" if sqm else "",
                    )
                )

        return houses

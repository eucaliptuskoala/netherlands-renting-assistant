# model.py — Simple data class for a rental listing
# A "model" in programming is just structured data.
# This keeps all listing fields in one place so we don't have to pass 5 separate arguments everywhere.

class House:
    def __init__(self, id, url, address, price, living_area):
        self.id = id                # Unique identifier from the rental website
        self.URL = url              # Full link to the listing
        self.address = address      # Street name (e.g. "Stationsweg 12")
        self.price = price          # Monthly rent in euros (integer)
        self.living_area = living_area  # Living area in m² (string, e.g. "65 m²")

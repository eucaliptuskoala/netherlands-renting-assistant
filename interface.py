# interface.py — Abstract base class for all rent providers (Funda, Pararius, etc.)
# This ensures every scraper follows the same pattern, so main.py can treat them all the same way.
# If you want to add a new website (e.g., huurwoningen.nl), you create a class that inherits from this.

class RentProviderInterface:
    def __init__(self, city, price):
        """Store the city and price range that all scrapers will need."""
        self._min_price = price[0]  # Lower bound for monthly rent
        self._max_price = price[1]  # Upper bound for monthly rent
        self._city = city           # City to search in (e.g. "eindhoven")

    def _isPriceMatched(self, price):
        """Check if a listing's price falls within the configured range."""
        if price >= self._min_price and price <= self._max_price:
            return True
        return False

    def Run(self):
        """Template method — each provider must implement this. Should return a list of House objects."""
        pass

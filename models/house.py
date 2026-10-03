from dataclasses import dataclass


@dataclass
class House:
    id: str
    URL: str
    address: str
    price: int
    living_area: str

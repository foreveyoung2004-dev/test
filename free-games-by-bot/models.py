from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Giveaway:
    source: str
    item_id: str
    title: str
    url: str
    image: str | None
    old_price: str | None
    end_at: datetime | None
    region: str

    @property
    def key(self) -> tuple[str, str]:
        return self.source, self.item_id

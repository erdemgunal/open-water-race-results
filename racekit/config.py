from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path

def _provider_domain(subdomain: str) -> str:
    return ".".join((subdomain, "raceresult", "com"))

@dataclass(frozen=True)
class ListSpec:
    role: str
    page: str
    listname: str
    contest: str = "0"

@dataclass(frozen=True)
class EventConfig:
    key: str
    name: str
    event_id: int
    year: int
    distance_m: float
    data_dir: str | Path | None = None
    output_dir: str | Path | None = None
    lists: tuple[ListSpec, ...] = ()
    result_role: str = ""
    default_bib: int | None = None
    known_key: str | None = None
    owner_highlight: tuple[str, str] | None = None
    auto_lookup: dict | None = None
    bootstrap_server: str = _provider_domain("my4")
    dataset_name: str | None = None
    snapshot_keep: int = 10

    def dataset_stem(self) -> str:
        return self.dataset_name or f"{self.key}_dataset"
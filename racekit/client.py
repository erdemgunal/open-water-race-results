from __future__ import annotations

import logging

from racekit.config import _provider_domain
from pathlib import Path
import requests
import json
import time

logger = logging.getLogger(__name__)

_ORIGIN = f"https://{_provider_domain('my')}"

HEADERS = {
    "user-agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9,tr;q=0.8",
    "origin": _ORIGIN,
    "referer": f"{_ORIGIN}/",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}

TIMEOUT = 30
SLEEP_BETWEEN_REQUESTS = 0.5

class RaceResultClient:
    def __init__(self, cfg, offline):
        self.cfg = cfg
        self.offline = offline
        self.server = cfg.bootstrap_server
        self.key = cfg.known_key
        self.contests: dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        if not offline:
            self._discover()

    def _get_json(self, url, params):
        resp = self.session.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"API hatası: {data['error']} (url={resp.url})")
        return data

    def _discover(self):
        pages = sorted({spec.page for spec in self.cfg.lists})
        for page in pages:
            url = f"https://{self.cfg.bootstrap_server}/{self.cfg.event_id}/{page}/config"
            try:
                cfg_data = self._get_json(url, {"lang": "en", "mid": 0, "standalone": "false"})
            except Exception as exc:
                logger.warning("   ! config yok (%s): %s", page, exc)
                continue
            if cfg_data.get("server"):
                self.server = cfg_data["server"]
            if cfg_data.get("key"):
                self.key = cfg_data["key"]
            if cfg_data.get("eventname"):
                self.eventname = cfg_data["eventname"]
            self.contests.update(cfg_data.get("contests") or {})
        if not self.key:
            raise RuntimeError(
                "RaceResult config keşfedilemedi (key bulunamadı). "
                "EventConfig.known_key ya da <KEY>_KEY ortam değişkeniyle fallback sağlayın."
            )
        logger.info(
            "-> keşif: server=%s key=%s contests=%s",
            self.server, self.key, self.contests or "(yok)",
        )

    def fetch_list(self, spec):
        raw_path = self.cfg.data_dir / f"{spec.role}_raw.json"
        if self.offline:
            if not raw_path.exists():
                raise FileNotFoundError(
                    f"{raw_path} yok. Önce çevrimiçi modda çalıştırın: "
                    f"python fetch_results.py   (yarış klasörünün içinden)"
                )
            data = json.loads(raw_path.read_text(encoding="utf-8"))
            logger.info("-> %s: %s okundu (offline)", spec.role, raw_path.name)
            return data

        url = f"https://{self.server}/{self.cfg.event_id}/{spec.page}/list"
        params = {
            "key": self.key,
            "listname": spec.listname,
            "page": spec.page,
            "contest": spec.contest,
            "r": "all",
            "l": 0,
            "fav": "",
            "openedGroups": "{}",
            "term": "",
        }
        data = self._get_json(url, params)
        nrows = self._count_rows(data.get("data"))
        logger.info("-> %s: API'dan çekildi (%d satır)", spec.role, nrows)
        time.sleep(SLEEP_BETWEEN_REQUESTS)
        return data

    def fetch_all(self):
        raw = {}
        for spec in self.cfg.lists:
            raw[spec.role] = self.fetch_list(spec)

        if not self.offline:
            self.cfg.data_dir.mkdir(parents=True, exist_ok=True)
            for spec in self.cfg.lists:
                raw_path = self.cfg.data_dir / f"{spec.role}_raw.json"
                raw_path.write_text(
                    json.dumps(raw[spec.role], ensure_ascii=False, indent=2), encoding="utf-8"
                )
                logger.info("   -> %s yazıldı", raw_path.name)
        return raw

    @staticmethod
    def _count_rows(nested):
        if isinstance(nested, list):
            return len(nested)
        if isinstance(nested, dict):
            total = 0
            for v in nested.values():
                if isinstance(v, list):
                    total += len(v)
                elif isinstance(v, dict):
                    total += sum(len(x) for x in v.values() if isinstance(x, list))
            return total
        return 0
"""
Space-Track.org API Client
Handles authentication, rate limiting, and queries for:
  - satcat (satellite catalog)
  - cdm_public (archived conjunction data messages)
  - gp (general perturbations / orbital elements)
"""

import time
import json
import logging
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://www.space-track.org"
LOGIN_URL = f"{BASE_URL}/ajaxauth/login"
QUERY_URL = f"{BASE_URL}/basicspacedata/query"

# Fengyun-1C international designator prefix
FENGYUN_1C_INTDES = "1999-025"

# Rate limit: stay well under 30 req/min
REQUEST_DELAY_SECONDS = 3


class SpaceTrackClient:
    """Authenticated client for Space-Track.org REST API."""

    def __init__(self, username: str, password: str, cache_dir: Optional[Path] = None):
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.authenticated = False
        self.cache_dir = cache_dir or Path("data/raw")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._last_request_time = 0.0

    def login(self) -> bool:
        """Authenticate with Space-Track and establish session cookie."""
        logger.info("Authenticating with Space-Track.org...")
        resp = self.session.post(LOGIN_URL, data={
            "identity": self.username,
            "password": self.password,
        })

        if resp.status_code == 200 and '"Login" : "Failed"' not in resp.text:
            self.authenticated = True
            logger.info("[OK] Authentication successful")
            return True
        else:
            logger.error(f"[FAIL] Authentication failed: {resp.status_code} - {resp.text[:200]}")
            return False

    def _throttle(self):
        """Enforce minimum delay between requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY_SECONDS:
            wait = REQUEST_DELAY_SECONDS - elapsed
            logger.debug(f"Rate limiting: waiting {wait:.1f}s")
            time.sleep(wait)
        self._last_request_time = time.time()

    def _query(self, url: str, cache_key: Optional[str] = None, force_refresh: bool = False) -> list:
        """
        Execute a Space-Track API query.
        Optionally cache the result to disk.
        """
        # Check cache first
        if cache_key and not force_refresh:
            cache_path = self.cache_dir / f"{cache_key}.json"
            if cache_path.exists():
                logger.info(f"Loading cached data: {cache_path}")
                with open(cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)

        if not self.authenticated:
            if not self.login():
                raise RuntimeError("Failed to authenticate with Space-Track.org")

        self._throttle()
        logger.info(f"Querying: {url[:120]}...")

        resp = self.session.get(url)
        resp.raise_for_status()

        try:
            data = resp.json()
        except json.JSONDecodeError:
            logger.error(f"Non-JSON response: {resp.text[:300]}")
            raise

        # Cache result
        if cache_key:
            cache_path = self.cache_dir / f"{cache_key}.json"
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Cached {len(data)} records → {cache_path}")

        return data

    # ──────────────────────────────────────────────
    # Domain-specific queries
    # ──────────────────────────────────────────────

    def get_fengyun_catalog(self, force_refresh: bool = False) -> list[dict]:
        """
        Fetch all objects in the satellite catalog related to Fengyun-1C.
        Uses OBJECT_NAME search for reliability.

        Returns list of dicts with keys:
            NORAD_CAT_ID, OBJECT_NAME, OBJECT_TYPE, INTLDES, LAUNCH, DECAY, ...
        """
        url = (
            f"{QUERY_URL}/class/satcat"
            f"/OBJECT_NAME/FENGYUN 1C~~"
            f"/orderby/NORAD_CAT_ID asc"
            f"/format/json"
        )
        return self._query(url, cache_key="fengyun_catalog", force_refresh=force_refresh)

    def get_cdm_public_by_name(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        force_refresh: bool = False,
    ) -> list[dict]:
        """
        Fetch public CDMs where either SAT_1_NAME or SAT_2_NAME
        contains 'FENGYUN 1C'.

        The cdm_public class only contains CDMs archived >72h after TCA.

        Args:
            date_from: TCA start date (YYYY-MM-DD), default '2025-01-01'
            date_to:   TCA end date (YYYY-MM-DD), default 'now'
        """
        date_from = date_from or "2025-01-01"
        date_to = date_to or "now"

        results = []

        # Query for SAT_1_NAME containing FENGYUN 1C
        url_sat1 = (
            f"{QUERY_URL}/class/cdm_public"
            f"/SAT_1_NAME/~~FENGYUN 1C~~"
            f"/TCA/{date_from}--{date_to}"
            f"/orderby/TCA asc"
            f"/format/json"
        )
        data_sat1 = self._query(url_sat1, cache_key=f"cdm_sat1_{date_from}_{date_to}", force_refresh=force_refresh)
        logger.info(f"CDMs with FY-1C as SAT_1: {len(data_sat1)}")
        results.extend(data_sat1)

        # Query for SAT_2_NAME containing FENGYUN 1C
        url_sat2 = (
            f"{QUERY_URL}/class/cdm_public"
            f"/SAT_2_NAME/~~FENGYUN 1C~~"
            f"/TCA/{date_from}--{date_to}"
            f"/orderby/TCA asc"
            f"/format/json"
        )
        data_sat2 = self._query(url_sat2, cache_key=f"cdm_sat2_{date_from}_{date_to}", force_refresh=force_refresh)
        logger.info(f"CDMs with FY-1C as SAT_2: {len(data_sat2)}")
        results.extend(data_sat2)

        # Deduplicate by CDM_ID (in case same CDM appears in both queries)
        seen = set()
        deduped = []
        for cdm in results:
            cdm_id = cdm.get("CDM_ID")
            if cdm_id not in seen:
                seen.add(cdm_id)
                deduped.append(cdm)

        logger.info(f"Total unique CDMs fetched: {len(deduped)}")
        return deduped

    def get_gp_data(self, norad_ids: list[int], force_refresh: bool = False) -> list[dict]:
        """
        Fetch latest GP (orbital element) data for a list of NORAD IDs.
        Used to determine orbital regime (LEO filter via perigee height).

        Batches requests to avoid URL length limits.
        """
        all_data = []
        batch_size = 200  # Space-Track comma-delimited limit

        for i in range(0, len(norad_ids), batch_size):
            batch = norad_ids[i:i + batch_size]
            id_list = ",".join(str(nid) for nid in batch)
            batch_num = (i // batch_size) + 1
            total_batches = (len(norad_ids) + batch_size - 1) // batch_size

            url = (
                f"{QUERY_URL}/class/gp"
                f"/NORAD_CAT_ID/{id_list}"
                f"/orderby/NORAD_CAT_ID asc"
                f"/format/json"
            )

            cache_key = f"gp_batch_{batch_num}" if not force_refresh else None
            data = self._query(url, cache_key=cache_key, force_refresh=force_refresh)
            logger.info(f"GP batch {batch_num}/{total_batches}: {len(data)} records")
            all_data.extend(data)

        return all_data

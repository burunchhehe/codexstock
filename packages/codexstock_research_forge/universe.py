from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
import http.cookiejar
from html.parser import HTMLParser
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


class UniverseStore:
    """Versioned point-in-time symbol master used as survivorship-bias evidence."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def register(self, dataset_id: str, records: list[dict[str, Any]], source: str, evidence: dict[str, Any] | None = None) -> dict[str, Any]:
        if not dataset_id or not dataset_id.replace("-", "").replace("_", "").isalnum():
            raise ValueError("universe dataset_id must be alphanumeric with dash/underscore")
        if not source.strip() or len(records) == 0:
            raise ValueError("universe source and records are required")
        normalized = [self._record(value) for value in records]
        keys = [(row["symbol"], row["listing_date"], row.get("delisting_date")) for row in normalized]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate universe validity interval")
        integrity = self._integrity(normalized)
        if integrity["overlap_count"]:
            raise ValueError("overlapping universe validity intervals: " + ", ".join(integrity["overlapping_symbols"][:10]))
        declared_evidence = dict(evidence or {"grade": "declared_intervals"})
        if bool(declared_evidence.get("complete_daily_history")) and integrity["missing_lineage_evidence_count"]:
            raise ValueError("complete universe history requires official lineage evidence for reused symbol intervals")
        canonical = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        payload = {
            "schema_version": 1,
            "dataset_id": dataset_id,
            "source": source.strip(),
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "record_count": len(normalized),
            "content_hash": f"sha256:{digest}",
            "evidence": declared_evidence,
            "integrity": integrity,
            "records": normalized,
        }
        self._write(self.root / f"{dataset_id}.json", payload)
        return {key: value for key, value in payload.items() if key != "records"}

    def get(self, dataset_id: str) -> dict[str, Any]:
        safe = dataset_id.replace("-", "").replace("_", "")
        if not dataset_id or not safe.isalnum():
            raise ValueError("invalid universe dataset id")
        path = self.root / f"{dataset_id}.json"
        if not path.is_file():
            raise ValueError(f"universe dataset not found: {dataset_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("schema_version") != 1:
            raise ValueError("unsupported universe dataset")
        records = payload.get("records")
        if not isinstance(records, list) or not records:
            raise ValueError("universe dataset integrity verification failed")
        canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        expected = f"sha256:{hashlib.sha256(canonical.encode('utf-8')).hexdigest()}"
        if payload.get("record_count") != len(records) or payload.get("content_hash") != expected:
            raise ValueError("universe dataset integrity verification failed")
        return payload

    def query(self, dataset_id: str, as_of: str, markets: list[str] | None = None, security_types: list[str] | None = None) -> dict[str, Any]:
        target = date.fromisoformat(as_of)
        payload = self.get(dataset_id)
        dataset_evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
        rows = []
        for row in payload["records"]:
            listed = date.fromisoformat(row["listing_date"])
            delisted = date.fromisoformat(row["delisting_date"]) if row.get("delisting_date") else None
            active = listed <= target and (delisted is None or target <= delisted)
            active = active and (not markets or row["market"] in markets)
            active = active and (not security_types or row["security_type"] in security_types)
            if active:
                rows.append(row)
        coverage_start = str(dataset_evidence.get("coverage_start") or "")
        coverage_end = str(dataset_evidence.get("coverage_end") or "")
        coverage_ok = not coverage_start or coverage_start <= as_of <= coverage_end
        return {"dataset_id": dataset_id, "as_of": as_of, "symbols": rows, "count": len(rows), "content_hash": payload["content_hash"], "coverage_ok": coverage_ok, "dataset_evidence": dataset_evidence}

    def validate_period(self, dataset_id: str, symbols: list[str], start_date: str, end_date: str) -> dict[str, Any]:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if end < start:
            raise ValueError("universe validation end_date precedes start_date")
        payload = self.get(dataset_id)
        dataset_evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
        evidence = []
        for symbol in symbols:
            candidates = [row for row in payload["records"] if row["symbol"] == symbol]
            covering = []
            for row in candidates:
                listed = date.fromisoformat(row["listing_date"])
                delisted = date.fromisoformat(row["delisting_date"]) if row.get("delisting_date") else None
                if listed <= start and (delisted is None or delisted >= end):
                    covering.append(row)
            evidence.append({"symbol": symbol, "covered": bool(covering), "matching_intervals": covering})
        blockers = [row["symbol"] for row in evidence if not row["covered"]]
        coverage_start = str(dataset_evidence.get("coverage_start") or "")
        coverage_end = str(dataset_evidence.get("coverage_end") or "")
        coverage_ok = not coverage_start or (coverage_start <= start_date and coverage_end >= end_date)
        grade = str(dataset_evidence.get("grade") or "declared_intervals")
        grade_ok = grade in {"declared_intervals", "official_snapshot", "official_daily_history", "complete_listing_history"}
        if grade == "official_fixed_pre_start_instruments":
            frozen_as_of = str(dataset_evidence.get("frozen_as_of") or "")
            official_source_urls = dataset_evidence.get("official_source_urls")
            source_urls_ok = bool(
                isinstance(official_source_urls, list)
                and official_source_urls
                and all(
                    str(value).startswith(("https://www.ssga.com/", "https://www.invesco.com/"))
                    for value in official_source_urls
                )
            )
            matching = [interval for row in evidence for interval in row["matching_intervals"]]
            grade_ok = bool(
                dataset_evidence.get("official") is True
                and dataset_evidence.get("frozen_before_test") is True
                and dataset_evidence.get("selection_rule_complete") is True
                and dataset_evidence.get("claim_scope") == "timing_exit_and_risk_management_only"
                and dataset_evidence.get("stock_selection_claim_allowed") is False
                and frozen_as_of
                and frozen_as_of <= start_date
                and matching
                and all(str(interval.get("listing_date") or "") <= frozen_as_of for interval in matching)
                and all(
                    str(interval.get("source_url") or "").startswith(
                        ("https://www.ssga.com/", "https://www.invesco.com/")
                    )
                    for interval in matching
                )
                and source_urls_ok
            )
        if grade == "official_listing_interval_history":
            clipped = int(dataset_evidence.get("precoverage_listing_dates_clipped") or 0)
            matching = [interval for row in evidence for interval in row["matching_intervals"]]
            # The merged official dataset may be incomplete for unrelated delisted securities while
            # still carrying an exact KIND listing date for every requested security. Conservatively
            # reject any requested interval pinned to the provider's clipping boundary.
            grade_ok = bool(matching) and not (clipped and any(interval["listing_date"] == coverage_start for interval in matching))
        if not coverage_ok:
            blockers.append("dataset_coverage")
        if not grade_ok:
            blockers.append("evidence_grade")
        return {
            "passed": not blockers,
            "dataset_id": dataset_id,
            "content_hash": payload["content_hash"],
            "source": payload["source"],
            "start_date": start_date,
            "end_date": end_date,
            "symbols": evidence,
            "uncovered_symbols": blockers,
            "dataset_evidence": dataset_evidence,
            "coverage_ok": coverage_ok,
            "evidence_grade_ok": grade_ok,
        }

    def status(self) -> dict[str, Any]:
        datasets, invalid = [], []
        for path in sorted(self.root.glob("*.json")):
            try:
                payload = self.get(path.stem)
                datasets.append({key: payload.get(key) for key in ("dataset_id", "source", "registered_at", "record_count", "content_hash", "evidence")})
            except Exception as exc:
                invalid.append({"path": str(path), "error": str(exc)})
        return {"ok": not invalid, "dataset_count": len(datasets), "datasets": datasets, "invalid": invalid}

    def integrity(self, dataset_id: str) -> dict[str, Any]:
        payload = self.get(dataset_id); result = self._integrity(payload["records"])
        return {"ok": result["overlap_count"] == 0, "dataset_id": dataset_id, "content_hash": payload["content_hash"], **result}

    @staticmethod
    def _record(value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("universe record must be an object")
        symbol = str(value.get("symbol") or "").upper()
        market, security_type = str(value.get("market") or ""), str(value.get("security_type") or "")
        listing_date, delisting_date = str(value.get("listing_date") or ""), str(value.get("delisting_date") or "")
        if not symbol.isalnum() or not market or not security_type:
            raise ValueError("universe symbol, market, and security_type are required")
        listed = date.fromisoformat(listing_date)
        delisted = date.fromisoformat(delisting_date) if delisting_date else None
        if delisted and delisted < listed:
            raise ValueError("delisting_date precedes listing_date")
        row = {
            "symbol": symbol,
            "name": str(value.get("name") or symbol),
            "market": market,
            "security_type": security_type,
            "listing_date": listing_date,
            "delisting_date": delisting_date or None,
        }
        lineage_id = str(value.get("lineage_id") or "")
        source_url, source_hash = str(value.get("source_url") or ""), str(value.get("source_hash") or "")
        if lineage_id: row["lineage_id"] = lineage_id
        if source_url: row["source_url"] = source_url
        if source_hash: row["source_hash"] = source_hash
        return row

    @staticmethod
    def _integrity(records: list[dict[str, Any]]) -> dict[str, Any]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in records: grouped.setdefault(str(row["symbol"]), []).append(row)
        overlaps, reused, missing = [], [], []
        for symbol, intervals in grouped.items():
            intervals = sorted(intervals, key=lambda row: (row["listing_date"], row.get("delisting_date") or "9999-12-31"))
            for previous, current in zip(intervals, intervals[1:]):
                previous_end = previous.get("delisting_date")
                if not previous_end or current["listing_date"] <= previous_end:
                    overlaps.append({"symbol": symbol, "previous": previous, "current": current}); continue
                transition = {"symbol": symbol, "previous_delisting_date": previous_end, "next_listing_date": current["listing_date"], "previous_name": previous["name"], "next_name": current["name"]}
                reused.append(transition)
                verified = all(str(row.get("lineage_id") or "") and str(row.get("source_url") or "").startswith(("https://kind.krx.co.kr/", "https://data.krx.co.kr/")) and str(row.get("source_hash") or "").startswith("sha256:") and len(str(row.get("source_hash") or "")) == 71 for row in (previous, current))
                if not verified: missing.append(transition)
        return {"interval_count": len(records), "symbol_count": len(grouped), "multi_interval_symbol_count": sum(len(rows) > 1 for rows in grouped.values()), "overlap_count": len(overlaps), "overlapping_symbols": sorted({row["symbol"] for row in overlaps}), "overlap_samples": overlaps[:20], "code_reuse_transition_count": len(reused), "code_reuse_samples": reused[:20], "missing_lineage_evidence_count": len(missing), "missing_lineage_samples": missing[:20], "lineage_evidence_complete": not missing and not overlaps}

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)


class KrxOpenApiUniverseProvider:
    """Official KRX Open API security-master snapshot provider."""

    ENDPOINTS = {
        "KOSPI": "sto/stk_isu_base_info",
        "KOSDAQ": "sto/ksq_isu_base_info",
        "KONEX": "sto/knx_isu_base_info",
    }

    def __init__(self, api_key: str, base_url: str = "https://data-dbg.krx.co.kr/svc/apis") -> None:
        if not api_key.strip():
            raise ValueError("KRX API key is not configured")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")

    def fetch_snapshot(self, as_of: str, markets: list[str] | None = None, timeout: float = 15.0) -> dict[str, Any]:
        compact_date = date.fromisoformat(as_of).strftime("%Y%m%d")
        requested = markets or ["KOSPI", "KOSDAQ", "KONEX"]
        records, errors = [], {}
        for market in requested:
            if market not in self.ENDPOINTS:
                raise ValueError(f"unsupported KRX market: {market}")
            url = f"{self.base_url}/{self.ENDPOINTS[market]}?{urllib.parse.urlencode({'basDd': compact_date})}"
            request = urllib.request.Request(url, headers={"AUTH_KEY": self.api_key, "User-Agent": "CodexStock-Research-Forge/0.3"})
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                rows = payload.get("OutBlock_1") or payload.get("output") or []
                if not isinstance(rows, list):
                    raise ValueError("unexpected KRX response schema")
                for row in rows:
                    if isinstance(row, dict):
                        normalized = self._normalize(row, market, as_of)
                        if normalized:
                            records.append(normalized)
            except Exception as exc:
                errors[market] = str(exc)
        if not records:
            raise ValueError(f"KRX snapshot returned no records: {errors}")
        return {
            "as_of": as_of,
            "records": records,
            "markets_requested": requested,
            "markets_succeeded": sorted(set(row["market"] for row in records)),
            "errors": errors,
            "source": "KRX Open API security master",
            "evidence": {"grade": "official_snapshot", "coverage_start": as_of, "coverage_end": as_of, "official": True},
        }

    @staticmethod
    def _normalize(row: dict[str, Any], market: str, as_of: str) -> dict[str, Any] | None:
        symbol = str(row.get("ISU_SRT_CD") or row.get("ISU_CD") or "").strip()
        if symbol.startswith("KR") and len(symbol) > 6:
            symbol = symbol[-6:]
        symbol = symbol.zfill(6) if symbol.isdigit() else symbol
        if not symbol or not symbol.isalnum():
            return None
        raw_listing = str(row.get("LIST_DD") or "").replace("/", "").replace("-", "")
        listing = f"{raw_listing[:4]}-{raw_listing[4:6]}-{raw_listing[6:8]}" if len(raw_listing) == 8 else as_of
        group = str(row.get("SECUGRP_NM") or row.get("KIND_STKCERT_TP_NM") or "COMMON").upper()
        security_type = "COMMON" if "주권" in group or "보통" in group or group == "COMMON" else group
        return {"symbol": symbol, "name": str(row.get("ISU_ABBRV") or row.get("ISU_NM") or symbol), "market": market, "security_type": security_type, "listing_date": listing, "delisting_date": None}


class KindOfficialUniverseProvider:
    """Unauthenticated official KRX KIND current listed-company snapshot."""

    URL = "https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13"

    def fetch_snapshot(self, as_of: str | None = None, timeout: float = 20.0) -> dict[str, Any]:
        requested_date = date.fromisoformat(as_of) if as_of else date.today()
        if requested_date != date.today():
            raise ValueError("KIND company list is a current snapshot and cannot prove a historical as-of date")
        request = urllib.request.Request(self.URL, headers={"User-Agent": "CodexStock-Research-Forge/0.3", "Accept": "application/vnd.ms-excel,text/html"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            content_type = str(response.headers.get("Content-Type") or "")
        parser = _KindTableParser()
        parser.feed(raw.decode("euc-kr"))
        if not parser.rows or parser.rows[0][:3] != ["회사명", "시장구분", "종목코드"]:
            raise ValueError("unexpected KIND listed-company response schema")
        records = []
        markets = {"유가": "KOSPI", "코스닥": "KOSDAQ", "코넥스": "KONEX"}
        for values in parser.rows[1:]:
            if len(values) < 6:
                continue
            name, market_raw, symbol, _, _, listing_date = values[:6]
            market = markets.get(market_raw.strip())
            symbol = symbol.strip().zfill(6)
            if not market or not symbol.isdigit() or len(symbol) != 6:
                continue
            date.fromisoformat(listing_date)
            records.append({"symbol": symbol, "name": name.strip(), "market": market, "security_type": "COMMON", "listing_date": listing_date, "delisting_date": None})
        if len(records) < 1000:
            raise ValueError(f"KIND snapshot unexpectedly small: {len(records)}")
        raw_record_count = len(records)
        unique: dict[str, dict[str, Any]] = {}
        for record in records:
            prior = unique.get(record["symbol"])
            if prior is not None and prior != record:
                raise ValueError(f"KIND returned conflicting duplicate symbol: {record['symbol']}")
            unique[record["symbol"]] = record
        records = [unique[key] for key in sorted(unique)]
        canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        today = requested_date.isoformat()
        return {
            "as_of": today, "records": records,
            "source": "KRX KIND listed-company Excel",
            "source_url": self.URL, "source_bytes": len(raw),
            "raw_record_count": raw_record_count, "record_count": len(records),
            "duplicate_record_count": raw_record_count - len(records),
            "source_hash": f"sha256:{hashlib.sha256(raw).hexdigest()}",
            "normalized_hash": f"sha256:{hashlib.sha256(canonical).hexdigest()}",
            "content_type": content_type,
            "evidence": {"grade": "official_snapshot", "coverage_start": today, "coverage_end": today, "official": True, "includes_delisted": False, "historical_query_allowed": False, "exact_duplicates_removed": raw_record_count - len(records)},
        }


class KrxGlobalListingHistoryProvider:
    """Official OTP-backed KRX Global listing/delisting history combined with a current KIND snapshot."""

    BASE = "https://global.krx.co.kr"
    DATA_URL = BASE + "/contents/GLB/99/GLB99000001.jspx"
    OTP_URL = BASE + "/contents/COM/GenerateOTP.jspx"
    LISTING_BLD = "GLB/03/0306/0306010000/glb0306010000_01"
    DELISTING_BLD = "GLB/03/0306/0306050000/glb0306050000"

    def fetch_history(self, start: str, end: str, current_snapshot: dict[str, Any] | None = None, timeout: float = 20.0) -> dict[str, Any]:
        first, last = date.fromisoformat(start), date.fromisoformat(end)
        if last < first or last > date.today(): raise ValueError("invalid KRX listing-history period")
        snapshot = current_snapshot or KindOfficialUniverseProvider().fetch_snapshot(last.isoformat())
        if str(snapshot.get("as_of")) != last.isoformat(): raise ValueError("current snapshot date must equal history end")
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        listing_rows, delisting_rows, source_chunks = [], [], []
        cursor = first
        while cursor <= last:
            chunk_end = min(last, date(cursor.year, 12, 31))
            listings, listing_raw = self._query_retry(opener, self.LISTING_BLD, cursor, chunk_end, timeout, {"bnd_lst_typ": "1"})
            relistings, relisting_raw = self._query_retry(opener, self.LISTING_BLD, cursor, chunk_end, timeout, {"bnd_lst_typ": "2"})
            delistings, delisting_raw = self._query_retry(opener, self.DELISTING_BLD, cursor, chunk_end, timeout, {"del_cd": "1"})
            listing_rows.extend(listings); listing_rows.extend(relistings); delisting_rows.extend(delistings)
            source_chunks.append({"start": cursor.isoformat(), "end": chunk_end.isoformat(), "listing_hash": _sha(listing_raw), "relisting_hash": _sha(relisting_raw), "delisting_hash": _sha(delisting_raw), "listing_count": len(listings), "relisting_count": len(relistings), "delisting_count": len(delistings)})
            cursor = date(chunk_end.year + 1, 1, 1)
        listings_by_symbol: dict[str, list[str]] = {}
        for row in listing_rows:
            symbol = _krx_symbol(row.get("isu_cd")); listed = _krx_date(row.get("lst_dt") or row.get("re_lst_dt"))
            if symbol and listed and first.isoformat() <= listed <= last.isoformat(): listings_by_symbol.setdefault(symbol, []).append(listed)
        records = [UniverseStore._record(row) for row in snapshot.get("records") or []]
        clipped, normalized_delistings, skipped = 0, 0, 0
        for row in delisting_rows:
            symbol = _krx_symbol(row.get("isu_cd")); delisted = _krx_date(row.get("chg_dt")); market = _market_from_reason(str(row.get("tr_stp_rsn") or ""))
            if not symbol or not delisted or not market: skipped += 1; continue
            candidates = sorted(value for value in listings_by_symbol.get(symbol, []) if value <= delisted)
            listed = candidates[-1] if candidates else first.isoformat()
            clipped += not bool(candidates)
            records.append({"symbol": symbol, "name": str(row.get("kor_cor_nm") or symbol).strip(), "market": market, "security_type": "COMMON", "listing_date": listed, "delisting_date": delisted})
            normalized_delistings += 1
        records.sort(key=lambda value: (value["symbol"], value["listing_date"], value.get("delisting_date") or "9999"))
        canonical = json.dumps(records, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
        return {"as_of": last.isoformat(), "coverage_start": first.isoformat(), "coverage_end": last.isoformat(), "records": records, "source": "KRX Global official listing statistics + KRX KIND current snapshot", "source_url": self.BASE + "/contents/GLB/03/0306/0306050000/GLB0306050000.jsp", "record_count": len(records), "current_record_count": len(snapshot.get("records") or []), "delisted_record_count": normalized_delistings, "listing_event_count": len(listing_rows), "clipped_precoverage_listing_count": clipped, "skipped_row_count": skipped, "source_chunks": source_chunks, "normalized_hash": f"sha256:{hashlib.sha256(canonical).hexdigest()}", "evidence": {"grade": "official_listing_interval_history", "official": True, "coverage_start": first.isoformat(), "coverage_end": last.isoformat(), "includes_delisted": normalized_delistings > 0, "historical_query_allowed": True, "complete_daily_history": clipped == 0, "precoverage_listing_dates_clipped": clipped}}

    def _query(self, opener: Any, bld: str, start: date, end: date, timeout: float, extra: dict[str, str]) -> tuple[list[dict[str, Any]], bytes]:
        otp_query = urllib.parse.urlencode({"name": "form", "bld": bld})
        otp_request = urllib.request.Request(self.OTP_URL + "?" + otp_query, headers={"User-Agent": "CodexStock-Research-Forge/0.3", "Referer": self.BASE})
        with opener.open(otp_request, timeout=timeout) as response: code = response.read().decode("utf-8").strip()
        fields = {"market_gubun": "0", "isu_cdnm": "All", "isu_cd": "", "isu_nm": "", "isu_srt_cd": "", "fromdate": start.strftime("%Y%m%d"), "todate": end.strftime("%Y%m%d"), "code": code, **extra}
        request = urllib.request.Request(self.DATA_URL, data=urllib.parse.urlencode(fields).encode(), headers={"User-Agent": "CodexStock-Research-Forge/0.3", "Referer": self.BASE, "Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with opener.open(request, timeout=timeout) as response: raw = response.read()
        payload = json.loads(raw.decode("utf-8")); rows = next((value for value in payload.values() if isinstance(value, list)), [])
        return [dict(value) for value in rows if isinstance(value, dict)], raw

    def _query_retry(self, opener: Any, bld: str, start: date, end: date, timeout: float, extra: dict[str, str]) -> tuple[list[dict[str, Any]], bytes]:
        last_error: Exception | None = None
        for attempt in range(3):
            try: return self._query(opener, bld, start, end, timeout, extra)
            except Exception as exc:
                last_error = exc
                if attempt < 2: __import__("time").sleep(0.5 * (2 ** attempt))
        raise RuntimeError(f"KRX Global query failed after retries for {start}..{end}: {last_error}") from last_error


class PointInTimeUniverseHistory:
    """Immutable official-snapshot chain used to reconstruct the universe on each captured date."""

    def __init__(self, root: Path) -> None:
        self.root = root / "history"
        self.root.mkdir(parents=True, exist_ok=True)

    def create_baseline(self, dataset_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        path = self._path(dataset_id)
        if path.exists():
            raise ValueError("point-in-time universe history already exists")
        as_of = date.fromisoformat(str(snapshot.get("as_of") or "")).isoformat()
        records = sorted((UniverseStore._record(row) for row in snapshot.get("records") or []), key=lambda row: row["symbol"])
        if not records:
            raise ValueError("history baseline requires records")
        payload = {
            "schema_version": 1, "dataset_id": dataset_id, "source": snapshot.get("source"),
            "baseline_date": as_of, "coverage_end": as_of,
            "snapshots": [{"as_of": as_of, "record_count": len(records), "source_hash": snapshot.get("source_hash"), "normalized_hash": snapshot.get("normalized_hash")}],
            "baseline": records, "events": [],
            "evidence": {**dict(snapshot.get("evidence") or {}), "grade": "official_snapshot_chain", "historical_query_allowed": True, "complete_daily_history": False},
        }
        self._save(path, payload)
        return self._summary(payload)

    def append_snapshot(self, dataset_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        payload = self.get(dataset_id)
        as_of = date.fromisoformat(str(snapshot.get("as_of") or "")).isoformat()
        if as_of == payload["coverage_end"]:
            if payload["snapshots"][-1].get("normalized_hash") == snapshot.get("normalized_hash"):
                summary = self._summary(payload); summary["new_event_count"] = 0; summary["idempotent"] = True
                return summary
            raise ValueError("same-date official snapshot changed; preserve both source artifacts for manual reconciliation")
        if as_of < payload["coverage_end"]:
            raise ValueError("snapshot date must increase monotonically")
        previous = {row["symbol"]: row for row in self.query(dataset_id, payload["coverage_end"])["symbols"]}
        current = {row["symbol"]: UniverseStore._record(row) for row in snapshot.get("records") or []}
        if not current:
            raise ValueError("snapshot requires records")
        events = payload["events"]
        event_count_before = len(events)
        for symbol in sorted(previous.keys() - current.keys()):
            events.append({"effective_date": as_of, "type": "DELIST_OR_REMOVE", "symbol": symbol, "before": previous[symbol], "source_hash": snapshot.get("source_hash")})
        for symbol in sorted(current.keys() - previous.keys()):
            events.append({"effective_date": as_of, "type": "LIST_OR_ADD", "symbol": symbol, "after": current[symbol], "source_hash": snapshot.get("source_hash")})
        for symbol in sorted(previous.keys() & current.keys()):
            if previous[symbol] != current[symbol]:
                events.append({"effective_date": as_of, "type": "UPDATE", "symbol": symbol, "before": previous[symbol], "after": current[symbol], "source_hash": snapshot.get("source_hash")})
        payload["coverage_end"] = as_of
        payload["snapshots"].append({"as_of": as_of, "record_count": len(current), "source_hash": snapshot.get("source_hash"), "normalized_hash": snapshot.get("normalized_hash")})
        payload["evidence"]["coverage_start"] = payload["baseline_date"]
        payload["evidence"]["coverage_end"] = as_of
        self._save(self._path(dataset_id), payload)
        summary = self._summary(payload)
        summary["new_event_count"] = len(events) - event_count_before
        return summary

    def query(self, dataset_id: str, as_of: str) -> dict[str, Any]:
        payload = self.get(dataset_id)
        target = date.fromisoformat(as_of).isoformat()
        if target < payload["baseline_date"] or target > payload["coverage_end"]:
            raise ValueError("as_of is outside captured snapshot-chain coverage")
        state = {row["symbol"]: dict(row) for row in payload["baseline"]}
        applied = 0
        for event in payload["events"]:
            if event["effective_date"] > target: break
            if event["type"] == "DELIST_OR_REMOVE": state.pop(event["symbol"], None)
            elif event["type"] == "CODE_CHANGE":
                state.pop(event["old_symbol"], None)
                state[event["new_symbol"]] = dict(event["after"])
            else: state[event["symbol"]] = dict(event["after"])
            applied += 1
        rows = [state[key] for key in sorted(state)]
        canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        exact_snapshot = any(row["as_of"] == target for row in payload["snapshots"])
        return {"dataset_id": dataset_id, "as_of": target, "symbols": rows, "count": len(rows), "applied_events": applied, "exact_snapshot": exact_snapshot, "result_hash": f"sha256:{hashlib.sha256(canonical.encode()).hexdigest()}", "evidence": payload["evidence"]}

    def record_official_code_change(
        self, dataset_id: str, effective_date: str, old_symbol: str,
        new_record: dict[str, Any], source_url: str, source_hash: str,
    ) -> dict[str, Any]:
        payload = self.get(dataset_id)
        effective = date.fromisoformat(effective_date).isoformat()
        if not payload["baseline_date"] <= effective <= payload["coverage_end"]:
            raise ValueError("corporate action is outside captured history coverage")
        old_symbol = old_symbol.upper()
        after = UniverseStore._record(new_record)
        if not old_symbol.isalnum() or after["symbol"] == old_symbol:
            raise ValueError("code change requires distinct alphanumeric symbols")
        if not source_url.startswith(("https://kind.krx.co.kr/", "https://data.krx.co.kr/")):
            raise ValueError("code change source must be an official KRX URL")
        if not source_hash.startswith("sha256:") or len(source_hash) != 71:
            raise ValueError("code change requires a SHA-256 source hash")
        before_state = {row["symbol"]: row for row in self.query(dataset_id, effective)["symbols"]}
        if old_symbol not in before_state:
            raise ValueError("old symbol is not active on the effective date")
        event = {"effective_date": effective, "type": "CODE_CHANGE", "old_symbol": old_symbol, "new_symbol": after["symbol"], "before": before_state[old_symbol], "after": after, "source_url": source_url, "source_hash": source_hash, "official": True}
        if any(existing == event for existing in payload["events"]):
            return {"ok": True, "idempotent": True, "event": event, **self._summary(payload)}
        payload["events"].append(event)
        payload["events"].sort(key=lambda value: (value["effective_date"], value["type"], value.get("symbol") or value.get("old_symbol") or ""))
        self._save(self._path(dataset_id), payload)
        return {"ok": True, "idempotent": False, "event": event, **self._summary(payload)}

    def get(self, dataset_id: str) -> dict[str, Any]:
        path = self._path(dataset_id)
        if not path.is_file(): raise ValueError("point-in-time universe history not found")
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != 1: raise ValueError("unsupported universe history")
        return payload

    def status(self) -> dict[str, Any]:
        rows = [self._summary(json.loads(path.read_text(encoding="utf-8"))) for path in sorted(self.root.glob("*.json"))]
        return {"ok": True, "history_count": len(rows), "histories": rows}

    def _path(self, dataset_id: str) -> Path:
        if not dataset_id or not dataset_id.replace("-", "").replace("_", "").isalnum(): raise ValueError("invalid history dataset id")
        return self.root / f"{dataset_id}.json"

    @staticmethod
    def _summary(payload: dict[str, Any]) -> dict[str, Any]:
        return {"dataset_id": payload["dataset_id"], "source": payload.get("source"), "baseline_date": payload["baseline_date"], "coverage_end": payload["coverage_end"], "snapshot_count": len(payload["snapshots"]), "event_count": len(payload["events"]), "evidence": payload["evidence"]}

    @staticmethod
    def _save(path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)


def _sha(raw: bytes) -> str:
    return f"sha256:{hashlib.sha256(raw).hexdigest()}"


def _krx_symbol(value: Any) -> str:
    text = str(value or "").strip().upper()
    if text.startswith("KR") and len(text) > 6: text = text[-6:]
    return text.zfill(6) if text.isdigit() and len(text) <= 6 else (text if len(text) == 6 and text.isalnum() else "")


def _krx_date(value: Any) -> str:
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) != 8: return ""
    try: return date(int(digits[:4]), int(digits[4:6]), int(digits[6:])).isoformat()
    except ValueError: return ""


def _market_from_reason(reason: str) -> str:
    upper = reason.upper()
    if "KOSDAQ" in upper: return "KOSDAQ"
    if "KONEX" in upper: return "KONEX"
    if "STOCK" in upper or "KOSPI" in upper: return "KOSPI"
    return ""


class _KindTableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr": self._row = []
        elif tag in {"td", "th"} and self._row is not None: self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None: self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            if self._row: self.rows.append(self._row)
            self._row = None

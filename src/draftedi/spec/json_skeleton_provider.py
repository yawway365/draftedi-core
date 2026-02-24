"""JSONSkeletonSpecProvider — X12SpecProvider backed by structural-only JSON skeleton files."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from draftedi.spec.protocol import (
    TransactionSetSpec,
    SegmentSpec,
    ElementSpec,
    RelationalCondition,
)


class JSONSkeletonSpecProvider:
    """X12SpecProvider backed by skeleton JSON files.

    Satisfies X12SpecProvider via structural subtyping (duck typing). No explicit
    inheritance from X12SpecProvider is used; this avoids coupling draftedi-core's
    public implementations to the Protocol class. (ref: DL-004)

    Skeleton files contain structural facts only: types, lengths, requirements, loop
    structure, relational conditions. element_name and segment_name are always None
    because ASC X12 descriptive names are copyrighted and intentionally excluded from
    open-source distribution. (ref: DL-004)

    Caching: per-instance dict avoids lru_cache memory leak on instance methods.
    Cache is populated on first access and never invalidated. Spec files are treated
    as static artifacts; users who modify JSON files after construction must create a
    new provider instance. (ref: R-003)

    Parameters
    ----------
    specs_dir : str or Path
        Directory containing skeleton JSON files named {version}-{tsid}.json.
    """

    def __init__(self, specs_dir: Union[str, Path]) -> None:
        self._dir = Path(specs_dir)
        self._cache: dict[str, dict] = {}

    def _load(self, version: str, ts_id: str) -> Optional[dict]:
        """Load and cache the JSON skeleton for (version, ts_id).

        Returns None when the file does not exist; callers must handle None
        rather than catching FileNotFoundError. Cache key is "{version}-{ts_id}".
        Once cached, the dict is returned directly on subsequent calls without
        re-reading disk. (ref: R-003)
        """
        key = f"{version}-{ts_id}"
        if key not in self._cache:
            path = self._dir / f"{key}.json"
            if not path.exists():
                return None
            with open(path, encoding="utf-8") as f:
                self._cache[key] = json.load(f)
        return self._cache[key]

    def get_transaction_set(self, version: str, ts_id: str) -> Optional[TransactionSetSpec]:
        """Return the TransactionSetSpec for (version, ts_id), or None if not found.

        Loads and caches the skeleton JSON. transaction_set_name is None because
        copyrighted ASC X12 descriptive names are excluded from skeleton files. (ref: DL-004)
        """
        spec = self._load(version, ts_id)
        if not spec:
            return None
        return TransactionSetSpec(
            transaction_set_id=spec["_meta"]["transaction_set_id"],
            transaction_set_name=None,
            functional_group_id=spec["_meta"]["functional_group_id"],
            segments=self._map_segments(spec["segments"]),
        )

    def get_element_codes(self, version: str, element_id: str) -> list[str]:
        """Return allowed code values for element_id within the given version.

        Searches only already-cached transaction sets for the version prefix.
        Returns an empty list when no codes are found or when includes_codes is
        false in the skeleton. Callers that need all codes for a version should
        call get_transaction_set() first to populate the cache. (ref: DL-004)
        """
        for key, spec in self._cache.items():
            if key.startswith(version + "-"):
                for seg in spec["segments"].values():
                    for elem in seg["elements"]:
                        if elem["element_id"] == element_id and elem.get("codes"):
                            return list(elem["codes"])
        return []

    def get_segment_spec(self, version: str, segment_id: str) -> Optional[SegmentSpec]:
        """Return the SegmentSpec for segment_id within the given version, or None.

        Searches cached transaction sets first; if not found, scans the specs_dir
        for all {version}-*.json files and loads them to populate the cache before
        retrying. segment_name is None for the same reason as transaction_set_name.
        (ref: DL-004)
        """
        for key, spec in self._cache.items():
            if key.startswith(version + "-"):
                seg = spec["segments"].get(segment_id)
                if seg:
                    return self._map_segment(segment_id, seg)
        for path in self._dir.glob(f"{version}-*.json"):
            ts_id = path.stem.split("-", 1)[1]
            self._load(version, ts_id)
            loaded = self._cache.get(f"{version}-{ts_id}", {})
            seg = loaded.get("segments", {}).get(segment_id)
            if seg:
                return self._map_segment(segment_id, seg)
        return None

    def get_available_versions(self) -> list[str]:
        """Return sorted list of X12 version strings present in specs_dir.

        Extracts the version prefix (first hyphen-delimited token) from each
        *.json filename. Does not load or validate file contents. (ref: DL-004)
        """
        versions: set[str] = set()
        for f in self._dir.glob("*.json"):
            parts = f.stem.split("-", 1)
            if len(parts) == 2:
                versions.add(parts[0])
        return sorted(versions)

    @staticmethod
    def _map_segment(segment_id: str, raw: dict) -> SegmentSpec:
        """Map a raw skeleton JSON segment dict to a SegmentSpec TypedDict.

        segment_name is always None. element_name is always None. Both omitted
        to exclude copyrighted ASC X12 descriptive text. (ref: DL-004)
        """
        return SegmentSpec(
            segment_id=segment_id,
            segment_name=None,
            requirement=raw["req"],
            max_use=raw["max_use"],
            loop_id=raw.get("loop"),
            loop_level=raw["loop_level"],
            loop_repeat=raw["loop_repeat"],
            sequence=raw["seq"],
            area=raw["area"],
            elements=[
                ElementSpec(
                    element_id=e["element_id"],
                    element_name=None,
                    data_type=e["type"],
                    min_length=e["min"],
                    max_length=e["max"],
                    requirement=e["req"],
                    sequence=e["pos"],
                    repetition_count=e["repeat"],
                )
                for e in raw["elements"]
            ],
            relational_conditions=[
                RelationalCondition(
                    condition_type=c["type"],
                    element_positions=c["positions"],
                )
                for c in raw.get("relational_conditions", [])
            ],
        )

    def _map_segments(self, raw_segments: dict) -> list[SegmentSpec]:
        """Map the segments dict from a skeleton JSON file to a SegmentSpec list.

        Preserves dict insertion order, which matches the seq field ordering
        in well-formed skeleton files generated by build_skeleton.py.
        """
        return [self._map_segment(seg_id, seg) for seg_id, seg in raw_segments.items()]

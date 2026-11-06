"""Pure transformations for Census-vintage place and metro geography data.

Network acquisition and publication-vintage selection are intentionally handled
by separate source adapters; these functions normalize already-fetched records.
"""
from __future__ import annotations
from typing import Any, Mapping


def _required(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    raise ValueError(f"missing required geography field: {' or '.join(keys)}")


def normalize_place(
    row: Mapping[str, Any],
    *,
    vintage: int,
    population: int | None = None,
    population_vintage: int | None = None,
) -> dict[str, Any]:
    """Normalize a Census place record without confusing places and metros."""
    geoid = _required(row, "GEOID", "GEO_ID")
    name = _required(row, "NAME", "name")
    statefp = _required(row, "STATE", "STATEFP", "STATEFP20")
    placefp = _required(row, "PLACE", "PLACEFP", "PLACEFP20")
    if not geoid.isdigit() or len(geoid) < 5:
        raise ValueError("place GEOID must be a numeric Census geographic identifier")
    if population is not None and (isinstance(population, bool) or population < 0):
        raise ValueError("population must be a non-negative integer")
    if population is not None and population_vintage is None:
        raise ValueError("population_vintage is required when population is supplied")
    return {
        "jurisdiction_id": f"census-place:{geoid}",
        "jurisdiction_type": "incorporated_place_or_census_place",
        "name": name,
        "geoid": geoid,
        "state_fips": statefp,
        "place_fips": placefp,
        "geography_vintage": vintage,
        "population": population,
        "population_vintage": population_vintage,
        "population_is_estimate": population is not None,
    }


def normalize_county_cbsa_membership(row: Mapping[str, Any], *, vintage: int) -> dict[str, Any]:
    """Normalize OMB/Census county-to-CBSA membership; not a legal city boundary."""
    state = _required(row, "FIPS State Code", "STATEFP", "state_fips")
    county = _required(row, "FIPS County Code", "COUNTYFP", "county_fips")
    cbsa = _required(row, "CBSA Code", "CBSA", "cbsa_code")
    title = _required(row, "CBSA Title", "NAME", "cbsa_title")
    area_type = _required(row, "Metropolitan/Micropolitan Statistical Area",
                          "LSAD", "area_type")
    if not (state.isdigit() and county.isdigit() and cbsa.isdigit()):
        raise ValueError("state, county and CBSA codes must be numeric")
    county_geoid = state.zfill(2) + county.zfill(3)
    return {
        "county_geoid": county_geoid,
        "cbsa_code": cbsa.zfill(5),
        "cbsa_title": title,
        "area_type": area_type,
        "delineation_vintage": vintage,
        "is_legal_municipal_boundary": False,
    }


def major_market_tier(rank: int | None) -> str:
    """Prioritization only: no place or metro is excluded from coverage."""
    if rank is None:
        return "unranked"
    if isinstance(rank, bool) or rank < 1:
        raise ValueError("rank must be a positive integer or None")
    if rank <= 50:
        return "top_50_metro_areas"
    if rank <= 100:
        return "top_100_metro_areas"
    return "other_metro_or_micropolitan_area"


def place_population_tier(population: int | None, *, threshold: int = 50000) -> str:
    if threshold < 0:
        raise ValueError("threshold must be non-negative")
    if population is None:
        return "population_unknown"
    if isinstance(population, bool) or population < 0:
        raise ValueError("population must be a non-negative integer")
    return "above_configured_place_threshold" if population >= threshold else "below_configured_place_threshold"

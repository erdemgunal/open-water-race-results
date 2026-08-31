from __future__ import annotations
import pandas as pd
import re

def to_nullable_int(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce").astype("Int64")

def strip_localized(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    m = re.match(r"^\{EN:([^|]*)\|", s)
    return m.group(1).strip() if m else s

def parse_nation(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    m = re.search(r"flags/([A-Z]{2})\.svg", s)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Z]{2}", s):
        return s
    return s or None

def parse_gender(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if s in ("M", "F"):
        return s
    m = re.search(r"\{EN:(Female|Male)\|", s)
    if m:
        return "M" if m.group(1) == "Male" else "F"
    if "Female" in s:
        return "F"
    if "Male" in s:
        return "M"
    return None

def gender_from_key(key) -> str | None:
    s = "" if key is None else str(key)
    if "Female" in s:
        return "F"
    if "Male" in s:
        return "M"
    return None

STATUS_MAP = {
    "FINISHED": "FINISHED",
    "DNS": "DNS",
    "DNF": "DNF",
    "DSQ": "DSQ",
    "A.K.": "DNS",
    "A.K": "DNS",
    "": "DNS",
}

def parse_time(text) -> tuple[str, int | None]:
    text = "" if text is None else str(text).strip()
    upper = text.upper()
    if upper in STATUS_MAP:
        return STATUS_MAP[upper], None
    m = re.fullmatch(r"(\d+):(\d{2})(?::(\d{2}))?(?:[.,](\d+))?", text)
    if m:
        if m.group(3) is None:
            seconds = int(m.group(1)) * 60 + int(m.group(2))
        else:
            seconds = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
        return "FINISHED", seconds
    return "UNKNOWN", None

def parse_rank(value) -> int | None:
    if value is None:
        return None
    s = str(value).strip()
    m = re.match(r"^(\d{1,6})\.?$", s)
    return int(m.group(1)) if m else None

def age_band(age_group) -> str:
    s = "" if age_group is None else str(age_group)
    m = re.search(r"\(([^()]*)\)", s)
    inner = m.group(1) if m else s
    mm = re.search(r"(\d{1,2}\s*[-–]\s*\d{1,2}|\d{1,2}\s*\+)", inner)
    if mm:
        return mm.group(1).replace(" ", "")
    return inner.strip()

def band_sort_key(band) -> int:
    m = re.match(r"\s*(\d{1,3})", str(band))
    return int(m.group(1)) if m else 999

def classify_columns(dfields: list) -> dict[int, str]:
    out: dict[int, str] = {}
    for idx, expr in enumerate(dfields):
        e = str(expr)
        if e == "BIB":
            out[idx] = "bib"
        elif e == "ID":
            out[idx] = "id"
        elif e == "FLNAME":
            out[idx] = "full_name"
        elif e == "FIRSTNAME":
            out[idx] = "first_name"
        elif e == "LASTNAME":
            out[idx] = "last_name"
        elif e in ("GenderMF", "GenderFix"):
            out[idx] = "gender"
        elif e == "NATION.FLAG":
            out[idx] = "nation_flag"
        elif e == "YEAR":
            out[idx] = "birth_year"
        elif e == "AGEGROUP.NAME":
            out[idx] = "age_group"
        elif "WithStatus([OverallRank.p])" in e or e == "OverallRank.p":
            out[idx] = "overall_rank"
        elif "WithStatus([GenderRank.p])" in e or e == "GenderRank.p":
            out[idx] = "gender_rank"
        elif "WithStatus([AgeGroupRank.p])" in e or e == "AgeGroupRank.p":
            out[idx] = "age_group_rank"
        elif "WithStatus([DisabledRank.p])" in e:
            out[idx] = "disabled_rank"
        elif "Swim.Text" in e or "Swim.TEXT" in e or "Finish.Chip" in e:
            out[idx] = "time_expr"
        elif e in ("Status.Text", "Status"):
            out[idx] = "status_raw"
    return out

CANONICAL_COLS = [
    "bib", "id", "first_name", "last_name", "full_name",
    "nation_flag", "birth_year", "gender", "age_group",
    "overall_rank", "gender_rank", "age_group_rank", "disabled_rank",
    "status_raw", "time_expr",
]

def _iter_rows(nested):
    if isinstance(nested, dict):
        for gkey, group in nested.items():
            if isinstance(group, dict):
                for skey, sub in group.items():
                    for row in sub:
                        yield gkey, skey, row
            elif isinstance(group, list):
                for row in group:
                    yield gkey, None, row
    elif isinstance(nested, list):
        for row in nested:
            yield None, None, row

def normalize_list(raw: dict, role: str, result_role: str) -> pd.DataFrame:
    dfields = raw.get("DataFields") or []
    nested = raw.get("data") or {}
    if not dfields:
        print(f"!! [{role}] DataFields boş — payload yapısını *_raw.json üzerinden inceleyin.")
        return pd.DataFrame()

    colmap = classify_columns(dfields)
    records = []
    for gkey, skey, row in _iter_rows(nested):
        row = list(row) if isinstance(row, (list, tuple)) else []
        if len(row) != len(dfields):
            row = (row + [None] * len(dfields))[: len(dfields)]
        rec = {colmap.get(idx): (val if colmap.get(idx) is not None else None)
               for idx, val in enumerate(row)}
        rec["_group_key"] = gkey
        rec["_subgroup_key"] = skey
        records.append(rec)
    if not records:
        print(f"!! [{role}] satır bulunamadı.")
        return pd.DataFrame()

    df = pd.DataFrame(records)
    out = pd.DataFrame(index=df.index)
    for c in CANONICAL_COLS:
        out[c] = df[c].to_numpy() if c in df.columns else pd.Series([None] * len(df), index=df.index)
    out["_group_key"] = df["_group_key"].to_numpy()
    out["_subgroup_key"] = df["_subgroup_key"].to_numpy()

    for c in ("bib", "id", "birth_year"):
        out[c] = to_nullable_int(out[c])

    if out["full_name"].isna().all() and "first_name" in out.columns:
        fn = out["first_name"].astype("string").fillna("").str.strip()
        ln = out["last_name"].astype("string").fillna("").str.strip()
        out["full_name"] = (fn + " " + ln).str.strip()
        out.loc[out["full_name"] == "", "full_name"] = pd.NA

    out["nation"] = out["nation_flag"].map(parse_nation)

    if out["gender"].notna().any():
        out["gender"] = out["gender"].map(parse_gender)
    else:
        g = out["_group_key"].map(gender_from_key)
        sg = out["_subgroup_key"].map(gender_from_key)
        out["gender"] = sg.where(sg.notna(), g)
    out["gender"] = out["gender"].where(out["gender"].notna(), pd.NA)

    out["age_group"] = out["age_group"].map(strip_localized)

    for c in ("overall_rank", "gender_rank", "age_group_rank", "disabled_rank"):
        out[c] = to_nullable_int(out[c].map(parse_rank))

    if role == result_role:
        parsed = out["time_expr"].map(parse_time)
        out["status"] = parsed.map(lambda t: t[0])
        out["swim_seconds"] = pd.Series(
            [t[1] for t in parsed], index=out.index, dtype="Int64"
        )
        out["time_text"] = out["time_expr"].map(lambda v: None if v is None else str(v).strip())
    else:
        out["status"] = pd.Series([pd.NA] * len(out), dtype="object")
        out["time_text"] = pd.Series([pd.NA] * len(out), dtype="object")
        out["swim_seconds"] = pd.Series([pd.NA] * len(out), dtype="Int64")

    out = out.drop(columns=["_group_key", "_subgroup_key"])
    out = out.drop(columns=["nation_flag", "status_raw", "time_expr"])
    return out
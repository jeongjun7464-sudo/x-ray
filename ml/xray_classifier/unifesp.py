import pandas as pd

DEFAULT_MAPPING = {
    "TORAX": "CHEST", "CHEST": "CHEST", "ABDOME": "ABDOMEN", "ABDOMEN": "ABDOMEN",
    "COLUNA": "SPINE", "SPINE": "SPINE", "BACIA": "PELVIS_HIP", "PELVIS": "PELVIS_HIP",
    "JOELHO": "KNEE", "KNEE": "KNEE", "MAO": "HAND", "HAND": "HAND",
    "PUNHO": "WRIST", "WRIST": "WRIST", "PE": "FOOT", "FOOT": "FOOT",
}

def load_unifesp_manifest(path: str, label_column: str = "label", mapping: dict[str, str] | None = None) -> pd.DataFrame:
    """Preserve source labels and add normalized service labels without inventing patient IDs."""
    frame = pd.read_csv(path)
    if label_column not in frame:
        raise ValueError(f"missing UNIFESP label column: {label_column}")
    lookup = mapping or DEFAULT_MAPPING
    frame["source_anatomical_region"] = frame[label_column].astype(str)
    frame["service_anatomical_region"] = frame[label_column].astype(str).str.upper().map(lookup).fillna("UNKNOWN")
    return frame

from pathlib import Path
import json
from tempfile import NamedTemporaryFile
from typing import Any, Dict, List, Union
from distiller.schemas.pipeline_config import PipelineConfig

Json = Union[Dict[str, Any], List[Any], str, int, float, bool, None]

with open('config.json', 'r') as f:
    json_str = f.read()
config = PipelineConfig.model_validate_json(json_str)

def _merge_dict_of_lists(old: Dict[str, Json], new: Dict[str, Json]) -> Dict[str, Json]:
    """Merge *new* into *old* (list values are extended, others overwritten)."""
    merged = old.copy()
    for key, new_val in new.items():
        if key in merged and isinstance(merged[key], list) and isinstance(new_val, list):
            merged[key] = merged[key] + new_val
        else:
            merged[key] = new_val
    return merged


def save_json(data: dict, filename: str, model_name: str) -> Path:
    """
    Persist *data* into ``source/evaluation/processed/<model_name>/{filename}.json``

    Parameters
    ----------
    data       : dict   – payload you want merged into the file
    filename   : str    – basename without ``.json``
    model_name : str    – sub‑directory used to separate results by model

    Returns
    -------
    pathlib.Path pointing to the updated file
    """
    # ── dynamic root based on `model_name` ───────────────────────────────
    root = Path("source/evaluation/processed") / config.version / model_name
    root.mkdir(parents=True, exist_ok=True)

    file_path = root / f"{filename}.json"

    # ── load existing payload (if any) ──────────────────────────────────
    if file_path.exists():
        try:
            with file_path.open("r", encoding="utf-8") as f:
                old_payload: Json = json.load(f)
        except json.JSONDecodeError:
            old_payload = {}
    else:
        old_payload = {}

    # ── validate & merge ────────────────────────────────────────────────
    if not isinstance(data, dict):
        raise TypeError("`data` must be a dict whose values are JSON‑serialisable.")
    if old_payload and not isinstance(old_payload, dict):
        raise ValueError(
            f"{file_path} contains a top‑level list, but the code now expects a dict."
            " Please convert or delete the file first."
        )

    new_payload = _merge_dict_of_lists(old_payload, data)

    # ── atomic write ────────────────────────────────────────────────────
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=file_path.parent,
        prefix=file_path.stem,
        suffix=".tmp",
    ) as tmp:
        json.dump(new_payload, tmp, ensure_ascii=False, indent=2)
        tmp_path = Path(tmp.name)

    tmp_path.replace(file_path)
    return file_path

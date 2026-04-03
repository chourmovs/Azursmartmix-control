from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from azursmartmix_control.config import Settings


class MountpointsSaveRequest(BaseModel):
    outputs: List[Dict[str, Any]] = Field(default_factory=list)


def _backup_text_file(path: str) -> str:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak-{ts}"
    with open(path, "rb") as src, open(bak, "wb") as dst:
        dst.write(src.read())
    return bak


def read_config_yaml(config_file: str) -> Dict[str, Any]:
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"config file not found: {config_file}")
    with open(config_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config root is not a mapping: {config_file}")
    return data


def write_config_yaml_atomic(config_file: str, data: Dict[str, Any]) -> None:
    parent = os.path.dirname(config_file) or "."
    os.makedirs(parent, exist_ok=True)

    st = None
    try:
        st = os.stat(config_file)
    except Exception:
        st = None

    tmp = f"{config_file}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
    os.replace(tmp, config_file)

    if st is not None:
        try:
            os.chmod(config_file, st.st_mode)
        except Exception:
            pass


def normalize_mountpoint_output(item: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None

    out = dict(item)

    str_keys = (
        "name",
        "type",
        "host",
        "mount",
        "username",
        "password",
        "stream_name",
        "description",
        "genre",
        "format",
    )
    int_keys = ("port", "bitrate_kbps", "sample_rate", "channels", "protocol")
    bool_keys = ("public", "cbr", "send_title_info")

    for k in str_keys:
        if k in out and out[k] is not None:
            out[k] = str(out[k]).strip()

    for k in int_keys:
        if k in out and out[k] not in (None, ""):
            try:
                out[k] = int(out[k])
            except Exception as e:
                raise ValueError(f"invalid integer for {k}: {out[k]!r}") from e

    for k in bool_keys:
        if k in out:
            v = out.get(k)
            if isinstance(v, bool):
                continue
            if isinstance(v, (int, float)):
                out[k] = bool(v)
                continue
            s = str(v or "").strip().lower()
            if s in {"1", "true", "yes", "on"}:
                out[k] = True
            elif s in {"0", "false", "no", "off", ""}:
                out[k] = False
            else:
                raise ValueError(f"invalid boolean for {k}: {v!r}")

    name = str(out.get("name") or "").strip()
    if not name:
        raise ValueError("mountpoint field 'name' is required")

    mount = str(out.get("mount") or "").strip()
    if not mount:
        raise ValueError("mountpoint field 'mount' is required")
    if not mount.startswith("/"):
        out["mount"] = "/" + mount

    fmt = str(out.get("format") or "").strip()
    if fmt:
        out["format"] = fmt.lower()

    mtype = str(out.get("type") or "").strip()
    if not mtype:
        out["type"] = "icecast"

    return out


def get_mountpoints_payload(settings: Settings) -> Dict[str, Any]:
    data = read_config_yaml(settings.azuramix_config_file)
    raw_outputs = data.get("outputs") or []
    outputs: List[Dict[str, Any]] = []
    if isinstance(raw_outputs, list):
        for item in raw_outputs:
            norm = normalize_mountpoint_output(item)
            if norm is not None:
                outputs.append(norm)

    return {
        "ok": True,
        "source": "config_yaml",
        "config_dir": settings.azuramix_config_dir,
        "config_file": settings.azuramix_config_file,
        "count": len(outputs),
        "outputs": outputs,
    }


def save_mountpoints_payload(settings: Settings, outputs_in: List[Dict[str, Any]]) -> Dict[str, Any]:
    data = read_config_yaml(settings.azuramix_config_file)

    outputs: List[Dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_mounts: set[str] = set()

    for raw in outputs_in if isinstance(outputs_in, list) else []:
        norm = normalize_mountpoint_output(raw)
        if norm is None:
            continue
        name_key = str(norm.get("name") or "").strip().casefold()
        mount_key = str(norm.get("mount") or "").strip().casefold()
        if name_key in seen_names:
            raise ValueError(f"duplicate mountpoint name: {norm.get('name')!r}")
        if mount_key in seen_mounts:
            raise ValueError(f"duplicate mount path: {norm.get('mount')!r}")
        seen_names.add(name_key)
        seen_mounts.add(mount_key)
        outputs.append(norm)

    backup = _backup_text_file(settings.azuramix_config_file)
    data["outputs"] = outputs
    write_config_yaml_atomic(settings.azuramix_config_file, data)

    return {
        "ok": True,
        "source": "config_yaml",
        "config_dir": settings.azuramix_config_dir,
        "config_file": settings.azuramix_config_file,
        "count": len(outputs),
        "outputs": outputs,
        "backup": backup,
        "restart_required": True,
        "message": "Saved to config.yml. Restart/Recreate required.",
    }

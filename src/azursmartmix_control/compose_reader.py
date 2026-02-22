from __future__ import annotations

"""
compose_reader.py

Historiquement: helpers YAML pour lire/écrire services[].environment dans docker-compose.yml.
Nouveau besoin: ne PLUS modifier docker-compose.yml ; éditer uniquement un fichier dotenv (azuramix.env).

On conserve les helpers YAML (read-only / legacy) et on ajoute:
- get_env_from_host_envfile(path): parse dotenv -> dict
- set_env_in_host_envfile(path, env_updates): merge updates + backup + écriture atomique en préservant un maximum de lignes existantes
"""

import datetime as dt
import os
import re
from typing import Any, Dict, List, Tuple


# ----------------------------
# YAML helpers (legacy)
# ----------------------------

def _require_yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except Exception as e:
        raise RuntimeError(
            "Missing dependency 'pyyaml' (import yaml failed). Add pyyaml to your dependencies."
        ) from e


def _normalize_env(env: Any) -> Dict[str, str]:
    """Normalize compose 'environment' which can be:
    - dict: {KEY: VALUE}
    - list: ["KEY=VALUE", "KEY2=VALUE2"]
    """
    out: Dict[str, str] = {}
    if env is None:
        return out

    if isinstance(env, dict):
        for k, v in env.items():
            if k is None:
                continue
            kk = str(k)
            vv = "" if v is None else str(v)
            out[kk] = vv
        return out

    if isinstance(env, list):
        for item in env:
            if item is None:
                continue
            s = str(item)
            if "=" in s:
                k, v = s.split("=", 1)
                out[str(k)] = str(v)
            else:
                out[s] = ""
        return out

    return out


def _denormalize_env(env_map: Dict[str, str], prefer: str = "dict") -> Any:
    """Convert back to compose environment format.
    prefer='dict' keeps a mapping (more readable).
    """
    if prefer == "list":
        return [f"{k}={v}" for k, v in env_map.items()]
    return dict(env_map)


def _load_compose(path: str) -> Dict[str, Any]:
    yaml = _require_yaml()
    if not os.path.exists(path):
        raise FileNotFoundError(f"compose file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"compose root is not a mapping: {path}")
    return data


def _dump_compose(path: str, data: Dict[str, Any]) -> None:
    yaml = _require_yaml()
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        )
    os.replace(tmp, path)


def _backup_file(path: str) -> str:
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = f"{path}.bak-{ts}"
    with open(path, "rb") as src, open(bak, "wb") as dst:
        dst.write(src.read())
    return bak


def get_service_env(compose_path: str, service_name: str) -> Dict[str, Any]:
    """Existing helper used by UI (read-only). Returns structured env from compose_path."""
    data = _load_compose(compose_path)
    services = data.get("services") or {}
    if not isinstance(services, dict):
        services = {}

    svc = services.get(service_name) or {}
    if not isinstance(svc, dict):
        svc = {}

    env = _normalize_env(svc.get("environment"))
    return {
        "ok": True,
        "compose_path": compose_path,
        "service": service_name,
        "environment": env,
        "count": len(env),
    }


def get_service_env_from_host_compose(host_compose_path: str, service_name: str) -> Dict[str, Any]:
    """Read env from host compose file (mounted into container)."""
    return get_service_env(host_compose_path, service_name)


def set_service_env_in_host_compose(
    host_compose_path: str,
    service_name: str,
    env_map: Dict[str, str],
    env_format_prefer: str = "dict",
) -> Dict[str, Any]:
    """Legacy writer: Write env_map into services[service_name].environment of the compose file.

    NOTE: Conservé pour compat / rollback, mais le control-plane n'est plus censé l'utiliser.
    """
    data = _load_compose(host_compose_path)
    services = data.get("services")
    if not isinstance(services, dict):
        services = {}
        data["services"] = services

    svc = services.get(service_name)
    if not isinstance(svc, dict):
        svc = {}
        services[service_name] = svc

    clean: Dict[str, str] = {}
    for k, v in (env_map or {}).items():
        if k is None:
            continue
        kk = str(k).strip()
        if not kk:
            continue
        vv = "" if v is None else str(v)
        clean[kk] = vv

    backup = _backup_file(host_compose_path)
    svc["environment"] = _denormalize_env(clean, prefer=env_format_prefer)
    _dump_compose(host_compose_path, data)

    return {
        "ok": True,
        "compose_path": host_compose_path,
        "service": service_name,
        "count": len(clean),
        "backup": backup,
    }


# ----------------------------
# dotenv helpers (NEW)
# ----------------------------

_RE_ENV_KV = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def _parse_dotenv_value(raw: str) -> str:
    """Parse a dotenv value. Conservative: avoid stripping inline comments (passwords may contain '#')."""
    v = (raw or "").strip()
    if not v:
        return ""
    if len(v) >= 2 and v[0] == v[-1] and v[0] in ("'", '"'):
        # remove surrounding quotes; keep escapes untouched (minimal surprise)
        return v[1:-1]
    return v


def _format_dotenv_value(v: str) -> str:
    """Format a dotenv value. Quote only when needed (spaces, #, quotes)."""
    s = "" if v is None else str(v)
    if s == "":
        return ""
    needs_quote = any(c in s for c in [" ", "\t", "#", '"', "'"])
    if not needs_quote:
        return s
    # Use double quotes and escape backslash + double quote
    esc = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{esc}"'


def _read_text_lines(path: str) -> List[str]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"env file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read().splitlines(True)  # keep line endings


def _write_text_lines_atomic(path: str, lines: List[str]) -> None:
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)

    st = None
    try:
        st = os.stat(path)
    except Exception:
        st = None

    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line)
        if lines and not lines[-1].endswith(("\n", "\r\n")):
            f.write("\n")

    os.replace(tmp, path)

    # best-effort preserve mode
    if st is not None:
        try:
            os.chmod(path, st.st_mode)
        except Exception:
            pass


def _parse_dotenv_lines(lines: List[str]) -> Tuple[Dict[str, str], Dict[str, int]]:
    """Return (env_map, key_to_line_index) for KEY=VALUE lines."""
    env: Dict[str, str] = {}
    idx: Dict[str, int] = {}
    for i, line in enumerate(lines):
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        m = _RE_ENV_KV.match(line)
        if not m:
            continue
        k = m.group(1).strip()
        raw_v = m.group(2)
        env[k] = _parse_dotenv_value(raw_v)
        idx[k] = i
    return env, idx


def get_env_from_host_envfile(env_file_path: str) -> Dict[str, Any]:
    """Read env from host dotenv file (mounted into container)."""
    lines = _read_text_lines(env_file_path)
    env, _ = _parse_dotenv_lines(lines)
    return {
        "ok": True,
        "compose_path": env_file_path,  # kept key name for UI compatibility
        "env_file": env_file_path,
        "service": "azuramix.env",
        "environment": env,
        "count": len(env),
        "source": "env_file",
    }


def set_env_in_host_envfile(env_file_path: str, env_updates: Dict[str, str]) -> Dict[str, Any]:
    """
    Merge-update env_file_path with env_updates.

    - Backup before write
    - Update existing KEY lines in place (preserve comments/ordering as much as possible)
    - Append new keys at the end
    - Does NOT delete keys missing from env_updates (anti-erosion)
    """
    if not os.path.exists(env_file_path):
        raise FileNotFoundError(f"env file not found: {env_file_path}")

    lines = _read_text_lines(env_file_path)
    current, key_idx = _parse_dotenv_lines(lines)

    # normalize incoming updates
    clean: Dict[str, str] = {}
    for k, v in (env_updates or {}).items():
        if k is None:
            continue
        kk = str(k).strip()
        if not kk:
            continue
        clean[kk] = "" if v is None else str(v)

    updated = 0
    added = 0

    # apply updates in place
    for k, v in clean.items():
        if k in key_idx:
            i = key_idx[k]
            # preserve line ending
            eol = "\n"
            if lines[i].endswith("\r\n"):
                eol = "\r\n"
            elif lines[i].endswith("\n"):
                eol = "\n"
            lines[i] = f"{k}={_format_dotenv_value(v)}{eol}"
            updated += 1
        else:
            # append later
            pass

    # append new keys (not present)
    for k, v in clean.items():
        if k not in key_idx:
            lines.append(f"{k}={_format_dotenv_value(v)}\n")
            added += 1

    backup = _backup_file(env_file_path)
    _write_text_lines_atomic(env_file_path, lines)

    # recompute effective env count
    lines2 = _read_text_lines(env_file_path)
    env2, _ = _parse_dotenv_lines(lines2)

    return {
        "ok": True,
        "compose_path": env_file_path,  # kept key name for UI compatibility
        "env_file": env_file_path,
        "count": len(env2),
        "updated": updated,
        "added": added,
        "backup": backup,
        "source": "env_file",
    }

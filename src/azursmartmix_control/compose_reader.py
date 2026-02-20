from __future__ import annotations

import datetime as dt
import os
from typing import Any, Dict, Tuple


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

    # unknown type
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
    """Write env_map into services[service_name].environment of the compose file.

    - Creates services/service if missing.
    - Saves backup before write.
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

    # normalize incoming values to strings
    clean: Dict[str, str] = {}
    for k, v in (env_map or {}).items():
        if k is None:
            continue
        kk = str(k).strip()
        if not kk:
            continue
        vv = "" if v is None else str(v)
        clean[kk] = vv

    # write
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

from __future__ import annotations

from .docker_log_parsing import DockerLogParsingMixin


class DockerClient(DockerLogParsingMixin):
    """Façade publique stable.

    Point d’entrée unique importable par le reste du codebase.
    Le fractionnement interne reste transparent pour les appelants.
    """

    pass

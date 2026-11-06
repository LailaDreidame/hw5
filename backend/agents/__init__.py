"""The Campus Customs agent team. Importing this package builds all five agents."""

from . import accounting, boss, customer_service, facilities, inventory  # noqa: F401  (registers agents)
from .base import REGISTRY
from .team import run_team

__all__ = ["REGISTRY", "run_team"]

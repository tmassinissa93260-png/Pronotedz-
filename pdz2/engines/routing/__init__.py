"""Routeur de stratégie de rendu — le routeur choisit, et déclare ses écarts."""

from pdz2.engines.routing.router import (
    LOCAL_CAPABILITY,
    MOTION_COMPLEXITY_ORDER,
    RenderRouter,
    RoutingOutcome,
    RoutingRejected,
)

__all__ = [
    "RenderRouter",
    "RoutingOutcome",
    "RoutingRejected",
    "LOCAL_CAPABILITY",
    "MOTION_COMPLEXITY_ORDER",
]

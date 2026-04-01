"""ToolManifest dataclass, BaseTool ABC, and ToolRegistry used by all tools."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from flask import Flask
from flask import Blueprint


@dataclass
class ToolManifest:
    """Static metadata about a tool, used for nav injection and scope-gating."""

    #: Short, URL-safe identifier (e.g. "market_browser").
    id: str
    #: Human-readable display name shown in the sidebar.
    name: str
    #: Single emoji or symbol used as the nav icon.
    icon: str
    #: One-line description shown in tooltips / future tool catalogue.
    description: str
    #: URL prefix for the tool's blueprint (e.g. "/tools/market").
    url_prefix: str
    #: ESI scopes required to use this tool; empty list = public tool.
    required_scopes: list[str] = field(default_factory=list)
    #: Lower value = higher position in the nav list.
    nav_weight: int = 50
    #: Sidebar section this tool appears in.
    #: "overview" = always visible | "tools" = logged-in | "apps" = logged-in, scope-gated
    #: "admin" = admin-only | "" = hidden from nav
    nav_section: str = "apps"


class BaseTool(ABC):
    """Abstract base that every tool must implement."""

    manifest: ToolManifest

    @abstractmethod
    def create_blueprint(self) -> Blueprint:
        """Return a configured Flask Blueprint for this tool."""
        ...


class ToolRegistry:
    """Central registry that collects tools and exposes them to Flask and templates."""

    def __init__(self) -> None:
        self._tools: list[BaseTool] = []

    def register(self, tool: BaseTool) -> None:
        self._tools.append(tool)

    def register_blueprints(self, app: Flask) -> None:
        """Register each tool's blueprint with the Flask app."""
        for tool in self._tools:
            bp     = tool.create_blueprint()
            prefix = tool.manifest.url_prefix
            # Pass url_prefix only when non-empty so that a dashboard-style
            # tool with url_prefix="" registers at the application root without
            # Flask receiving an explicit empty-string prefix argument.
            if prefix:
                app.register_blueprint(bp, url_prefix=prefix)
            else:
                app.register_blueprint(bp)

    def nav_entries(self) -> list[ToolManifest]:
        """Return manifests sorted by nav_weight (ascending)."""
        return sorted((t.manifest for t in self._tools), key=lambda m: m.nav_weight)

    def check_scopes(self, granted: list[str]) -> dict[str, bool]:
        """
        Return a dict mapping tool_id → bool indicating whether all required
        scopes for that tool are present in *granted*.
        """
        granted_set = set(granted)
        return {
            t.manifest.id: all(s in granted_set for s in t.manifest.required_scopes)
            for t in self._tools
        }

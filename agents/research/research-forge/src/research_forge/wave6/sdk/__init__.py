"""Wave 6 adapter SDK."""

from research_forge.wave6.sdk.conformance import ConformanceSuite
from research_forge.wave6.sdk.health import HealthChecker
from research_forge.wave6.sdk.manifest import AdapterCapabilityManifest
from research_forge.wave6.sdk.migration import MigrationManager, MigrationPolicy
from research_forge.wave6.sdk.protocol import PROTOCOL_VERSION
from research_forge.wave6.sdk.registry import PluginRegistry, compute_plugin_signature

__all__ = [
    "PROTOCOL_VERSION",
    "AdapterCapabilityManifest",
    "ConformanceSuite",
    "HealthChecker",
    "MigrationManager",
    "MigrationPolicy",
    "PluginRegistry",
    "compute_plugin_signature",
]

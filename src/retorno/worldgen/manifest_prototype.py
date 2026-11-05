"""Compatibility entrypoint for the frozen 4D-3e1b experimental policy.

Historical site computation is shared with production; this entrypoint always
selects the prototype version and never materializes or pins a game universe.
"""
from retorno.worldgen.manifest import (
    PROTOTYPE_VERSION as ALGORITHM_VERSION, EvidenceStatus, Assessment,
    SiteIdentity, AuthoredSite, ManifestDefinition, HistoricalSite, HistoricalEdge,
    SectorManifest, ManifestResult, SiteLookup, authored_base, lookup_site,
    query_manifest, _Session, _query_session,
)
from retorno.worldgen.manifest import define_manifest as _define
from retorno.worldgen.generator import _sample_sector_node
from retorno.runtime.data_loader import load_locations, load_worldgen_templates


def define_manifest(seed, *, templates=None, archetypes=None, authored=None,
                    algorithm_version=ALGORITHM_VERSION):
    return _define(seed, templates=templates, archetypes=archetypes,
                   authored=authored, algorithm_version=algorithm_version)

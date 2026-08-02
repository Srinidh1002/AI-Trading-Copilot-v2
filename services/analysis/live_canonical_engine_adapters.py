"""Typed aliases for the injected canonical engine bundle.

Concrete production callables are supplied by the existing canonical services;
this module deliberately has no provider, broker, or formula dependency.
"""
from services.analysis.live_canonical_evidence_engines import LiveCanonicalEvidenceEnginesV1

def build_default_live_canonical_evidence_engines(**engines) -> LiveCanonicalEvidenceEnginesV1:
    """Validate explicit canonical service callables into the exact 2H bundle."""
    return LiveCanonicalEvidenceEnginesV1(**engines)

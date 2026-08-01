"""Persistence mapping layer.

Isolates Domain objects from future persistence technologies. Snapshots are
pure, framework-free, JSON-serializable structures; the ``SnapshotMapper``
converts Domain <-> Snapshot with zero loss. No SQLAlchemy, no DB, no HTTP here.
"""

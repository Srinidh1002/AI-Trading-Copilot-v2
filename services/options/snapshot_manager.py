"""
Snapshot Manager

Stores previous option chain snapshots for comparison.
"""

from copy import deepcopy


class SnapshotManager:

    def __init__(self):
        self.previous = None
        self.current = None

    def update(self, flow):

        self.previous = self.current
        self.current = deepcopy(flow)

    def has_previous(self):

        return self.previous is not None

    def get_previous(self):

        return self.previous

    def get_current(self):

        return self.current
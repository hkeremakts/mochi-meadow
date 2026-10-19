"""Tests never touch the real journal in ~/Library: point it at a
throwaway file for the whole run."""
import os
import tempfile

os.environ["MEADOW_JOURNAL"] = os.path.join(tempfile.mkdtemp(prefix="meadow-tests-"), "journal.json")

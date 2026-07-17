"""Calypr storage — blob uploads for run artifacts (generated images, etc.)."""

from calypr_storage.blob import BlobError, put_blob

__all__ = ["put_blob", "BlobError"]

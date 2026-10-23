"""FreeFrame cloud worker package.

Kept lightweight so Modal can mount ``modal_worker`` as a normal Python package
without importing GPU/model dependencies at package import time.
"""

"""
SaveCloud.

Steam Cloud for everything.
"""

#
# The single source of truth for the version. `pyproject.toml` reads it
# from here, and a packaged build carries it in the code rather than in
# distribution metadata - which PyInstaller does not necessarily
# include, and which an AppImage has no reason to.
#

__version__ = "0.1.0b1"

"""Full scale stock analysis report generator.

The public entry points are :func:`stockanalysis.cli.main` (command line /
interactive) and :func:`stockanalysis.report.build_report` (programmatic).
"""

__version__ = "2.0.0"

from stockanalysis.config import ReportConfig

__all__ = ["ReportConfig", "__version__"]

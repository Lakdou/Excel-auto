"""Moteur d'analyse des classeurs Excel."""

from .workbook import SUPPORTED_EXTENSIONS, AnalysisError, analyze_bytes

__all__ = ["SUPPORTED_EXTENSIONS", "AnalysisError", "analyze_bytes"]

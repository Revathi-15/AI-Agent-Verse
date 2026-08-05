# backend/tools/base.py — Abstract base class every tool plugin must implement

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    name: str        # unique snake_case identifier  e.g. "sql_query"
    description: str # one-line description shown to the LLM planner
    emoji: str = "🔧" # icon shown in streaming status

    @abstractmethod
    def run(self, table: str, df_store: dict, **kwargs) -> dict:
        """
        Execute the tool.

        Args:
            table:    active table name
            df_store: dict mapping table_name → pandas DataFrame (all loaded CSVs)
            **kwargs: tool-specific parameters from the orchestrator

        Returns dict with at minimum:
            { "ok": bool, "data": any, "summary": str }
        """

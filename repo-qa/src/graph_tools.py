"""Graph tool 层（Stage1 v2.0, mock-first）。

将图能力从“注入提示”扩展到可调用工具接口：
- GRAPH_RETRIEVE(symbols)
- GRAPH_VALIDATE(sub_questions)
"""
from __future__ import annotations

from typing import Any, Dict, List


class GraphTools:
    def __init__(self, code_graph=None):
        self.code_graph = code_graph

    def graph_retrieve(self, symbols: List[str]) -> Dict[str, Any]:
        if not self.code_graph:
            return {"symbols": symbols, "results": {}, "grounded": 0}

        results: Dict[str, List[Dict[str, Any]]] = {}
        grounded = 0
        for symbol in symbols:
            hits = self.code_graph.search_symbol(symbol, limit=5)
            if hits:
                grounded += 1
            results[symbol] = [
                {
                    "qname": h.get("qname", h.get("name")),
                    "file": h.get("file"),
                    "line": h.get("line"),
                    "type": h.get("type"),
                }
                for h in hits
            ]

        return {"symbols": symbols, "results": results, "grounded": grounded}

    def graph_validate(self, sub_questions: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not sub_questions:
            return {"grounding_coverage": 0.0, "executable_entry_rate": 0.0, "details": []}

        details = []
        grounded_count = 0
        executable_count = 0

        for sq in sub_questions:
            symbols = [s for s in sq.get("symbols", []) if isinstance(s, str)]
            entries = [e for e in sq.get("entry_candidates", []) if isinstance(e, str)]

            retrieve = self.graph_retrieve(symbols)
            grounded = retrieve.get("grounded", 0) > 0
            executable = any(".py::" in e for e in entries)

            if grounded:
                grounded_count += 1
            if executable:
                executable_count += 1

            details.append(
                {
                    "subq_id": sq.get("id", "unknown"),
                    "grounded": grounded,
                    "executable_entries": executable,
                    "symbols": symbols,
                    "entry_candidates": entries,
                }
            )

        total = len(sub_questions)
        return {
            "grounding_coverage": round(grounded_count / total, 4),
            "executable_entry_rate": round(executable_count / total, 4),
            "details": details,
        }

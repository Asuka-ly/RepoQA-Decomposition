"""Graph tool 层（Stage1 v2.0, mock-first）。

将图能力从“注入提示”扩展到可调用工具接口：
- GRAPH_RETRIEVE(symbols)
- GRAPH_VALIDATE(sub_questions)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List


class GraphTools:
    def __init__(self, code_graph=None):
        self.code_graph = code_graph

    def _lexical_fallback_search(self, symbol: str, limit: int = 5) -> List[Dict[str, Any]]:
        """静态图命中不足时的词法回退检索。

        适配场景：
        - 动态代码/反射导致 AST 调用图不完备；
        - 问题里没有精确类名，只有关键词。
        """
        if not self.code_graph:
            return []

        file_contents = getattr(self.code_graph, "file_contents", {}) or {}
        token = (symbol or "").strip()
        if not token:
            return []

        pattern = re.compile(re.escape(token), re.IGNORECASE)
        hits: List[Dict[str, Any]] = []
        for rel_path, text in file_contents.items():
            if len(hits) >= limit:
                break
            if not isinstance(text, str):
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if pattern.search(line):
                    hits.append(
                        {
                            "qname": token,
                            "file": rel_path,
                            "line": i,
                            "type": "lexical_fallback",
                        }
                    )
                    break
        return hits[:limit]

    def graph_retrieve(self, symbols: List[str]) -> Dict[str, Any]:
        if not self.code_graph:
            return {"symbols": symbols, "results": {}, "grounded": 0, "retrieval_mode": "no_graph"}

        results: Dict[str, List[Dict[str, Any]]] = {}
        grounded = 0
        fallback_used = 0

        for symbol in symbols:
            hits = self.code_graph.search_symbol(symbol, limit=5)
            if not hits:
                hits = self._lexical_fallback_search(symbol, limit=5)
                if hits:
                    fallback_used += 1

            if hits:
                grounded += 1

            results[symbol] = [
                {
                    "qname": h.get("qname", h.get("name", symbol)),
                    "file": h.get("file"),
                    "line": h.get("line"),
                    "type": h.get("type", "unknown"),
                }
                for h in hits
            ]

        mode = "ast+lexical" if fallback_used > 0 else "ast_only"
        return {
            "symbols": symbols,
            "results": results,
            "grounded": grounded,
            "fallback_hits": fallback_used,
            "retrieval_mode": mode,
        }

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
                    "retrieval_mode": retrieve.get("retrieval_mode", "unknown"),
                }
            )

        total = len(sub_questions)
        return {
            "grounding_coverage": round(grounded_count / total, 4),
            "executable_entry_rate": round(executable_count / total, 4),
            "details": details,
        }

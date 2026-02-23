"""策略性问题分解器 - Code-Specific 版本（Stage 1 核心贡献）"""
import json
import re
from typing import Dict, List, Optional, Any

class StrategicDecomposer:
    """Code-Specific 分解器
    
    核心策略：
    1. 并行全分（Parallel Partition）：识别独立切面
    2. 线性截断（Linear Truncation）：只给入口点
    3. 符号锚定（Symbol Grounding）：基于代码图验证
    """
    
    def __init__(self, model, code_graph: Optional['CodeGraph'] = None):
        self.model = model
        self.code_graph = code_graph
        self.last_result: Optional[Dict] = None
    
    def decompose(self, question: str) -> Dict:
        """分解问题为独立切面
        
        Args:
            question: 原始问题
            
        Returns:
            分解结果字典
        """
        # Step 1: 提取关键符号
        symbols = self._extract_symbols(question)
        
        # Step 2: 构建图上下文（Code-Specific 核心）
        graph_context = self._build_graph_context(symbols)
        
        # Step 3: 调用 LLM 分解
        prompt = self._build_decomposition_prompt(question, graph_context)
        response = self.model.query([{"role": "user", "content": prompt}])
        
        print("\n📋 Decomposer Response:")
        print("=" * 60)
        print(response["content"])
        print("=" * 60 + "\n")
        
        # Step 4: 解析并验证
        result = self._parse_result(response["content"], question)
        result = self._normalize_result(result, question)
        self.last_result = result
        
        return result
    
    def _extract_symbols(self, question: str) -> List[str]:
        """从问题中提取可能的符号名
        
        启发式规则：
        - 驼峰命名（如 DefaultAgent, LocalEnvironment）
        - 下划线命名（如 execute_action, timeout_error）
        - Exception 结尾的词
        """
        symbols = []
        
        # 驼峰命名
        camel_case = re.findall(r'\b[A-Z][a-zA-Z]+\b', question)
        symbols.extend(camel_case)
        
        # 下划线命名（长度 >= 4）
        snake_case = re.findall(r'\b[a-z_]{4,}\b', question)
        symbols.extend(snake_case)
        
        return list(set(symbols))
    
    def _build_graph_context(self, symbols: List[str]) -> str:
        """基于代码图构建上下文（Code-Specific 核心）
        
        这是本方法相比通用分解器的关键优势：
        使用静态分析提供客观的代码结构信息
        """
        if not self.code_graph:
            return ""
        
        context_lines = ["CODE GRAPH ANALYSIS:"]
        found_any = False
        
        for symbol in symbols:
            # 在图中搜索符号
            results = self.code_graph.search_symbol(symbol, limit=2)
            
            for result in results:
                qname = result.get('qname', result['name'])
                node_id = f"{result['file']}::{qname}"
                neighbors = self.code_graph.get_neighbors(node_id)
                
                # 只输出有邻居关系的节点（更有价值）
                if neighbors and (neighbors['calls'] or neighbors['called_by']):
                    found_any = True
                    context_lines.append(f"\n- Symbol: {qname}")
                    context_lines.append(f"  Location: {result['file']}:{result['line']}")
                    context_lines.append(f"  Type: {result['type']}")
                    
                    if neighbors['calls']:
                        context_lines.append(
                            f"  → Calls: {', '.join(neighbors['calls'][:3])}"
                        )
                    if neighbors['called_by']:
                        context_lines.append(
                            f"  ← Called by: {', '.join(neighbors['called_by'][:3])}"
                        )
        
        if not found_any:
            return ""
        
        return "\n".join(context_lines)
    
    def _build_decomposition_prompt(self, question: str, graph_context: str) -> str:
        """构建分解 Prompt（Stage 1 核心设计）"""
        return f"""You are a Code-Specific Multi-hop QA Decomposition Expert.

TASK: Decompose the following code question into INDEPENDENT SUB-QUESTIONS.

PRINCIPLES:
1. PARALLEL PARTITION: Identify ALL independent aspects (different modules/classes)
   - If the question involves multiple modules, list them separately
   - Do NOT force a single reasoning chain

2. LINEAR TRUNCATION: Specify ENTRY CANDIDATES only, NOT reasoning steps
   - Format: "file.py::ClassName.method_name" or "file.py::function_name"
   - Provide 1~3 graph-grounded candidates
   - Do NOT predict what happens next - the agent will explore dynamically

3. SYMBOL GROUNDING: Use symbols from CODE GRAPH ANALYSIS
   - Prioritize symbols that appear in the graph
   - If a symbol is not found, keep it in unresolved_symbols

QUESTION:
{question}

{graph_context}

OUTPUT FORMAT (JSON only, no markdown):
{{
  "sub_questions": [
    {{
      "sub_question": "A concrete and answerable question?",
      "hypothesis": "A falsifiable expectation",
      "entry_candidates": ["exact_file.py::ExactClass.method_name"],
      "symbols": ["Symbol1", "Symbol2"],
      "required_evidence": ["definition location", "call path"],
      "exit_criterion": "What counts as done",
      "status": "open",
      "priority": 1
    }}
  ],
  "synthesis": "How to combine findings from all aspects",
  "estimated_hops": 2,
  "unresolved_symbols": []
}}

CRITICAL REQUIREMENTS:
- sub_question MUST be explicit question sentence
- Entry candidates MUST be PRECISE (Class.method level, not just Class)
- Use symbols from CODE GRAPH ANALYSIS above whenever possible
- DO NOT predict reasoning steps, ONLY entry points
- Output ONLY valid JSON, no extra text
"""

    def _normalize_result(self, result: Dict[str, Any], question: str) -> Dict[str, Any]:
        """将 LLM 输出标准化为可用于后续 RL 的结构。

        - 保持对旧字段 aspects 的向后兼容。
        - 统一产出 sub_questions，包含显式可更新状态字段。
        """
        raw_items = result.get("sub_questions")
        if not isinstance(raw_items, list):
            raw_items = result.get("aspects", [])

        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(raw_items, 1):
            if not isinstance(item, dict):
                continue

            entry_candidates = item.get("entry_candidates")
            if not isinstance(entry_candidates, list) or not entry_candidates:
                legacy_entry = item.get("entry_point", "unknown")
                entry_candidates = [legacy_entry]

            sub_question = item.get("sub_question") or item.get("description")
            if not sub_question:
                sub_question = f"What is the role of aspect {idx} for this question?"
            if "?" not in sub_question:
                sub_question = sub_question.rstrip(".") + "?"

            required_evidence = item.get("required_evidence")
            if not isinstance(required_evidence, list) or len(required_evidence) < 2:
                required_evidence = ["definition location", "call path"]

            normalized_item = {
                "id": item.get("id", f"SQ{idx}"),
                "sub_question": sub_question,
                "hypothesis": item.get("hypothesis", "To be validated from code evidence"),
                "entry_candidates": entry_candidates[:3],
                "symbols": item.get("symbols", []),
                "required_evidence": required_evidence,
                "exit_criterion": item.get(
                    "exit_criterion",
                    "At least 2 grounded evidence items with file path and line references"
                ),
                "status": item.get("status", "open"),
                "priority": item.get("priority", idx),
                "evidence_found": [],
                "progress": 0.0,
                "attempts": 0,
            }
            normalized.append(normalized_item)

        if not normalized:
            fallback = self._create_fallback(question)
            return self._normalize_result(fallback, question)

        result["sub_questions"] = sorted(normalized, key=lambda x: x.get("priority", 999))
        # 兼容旧 prompt 逻辑
        result["aspects"] = [
            {
                "description": sq["sub_question"],
                "entry_point": sq["entry_candidates"][0] if sq["entry_candidates"] else "unknown",
                "symbols": sq.get("symbols", []),
                "priority": sq.get("priority", 99),
            }
            for sq in result["sub_questions"]
        ]
        result.setdefault("unresolved_symbols", [])
        result.setdefault("synthesis", "Synthesize all validated sub-question answers")
        result.setdefault("estimated_hops", max(1, len(result["sub_questions"])))
        return result
    
    def _parse_result(self, content: str, question: str) -> Dict:
        """解析 LLM 返回的 JSON 结果"""
        try:
            # 清理 markdown 代码块
            content = re.sub(r'^```json\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'^```\s*', '', content, flags=re.MULTILINE)
            content = re.sub(r'\s*```$', '', content)
            content = content.strip()
            
            # 提取 JSON
            match = re.search(r'\{.*\}', content, re.DOTALL)
            if match:
                result = json.loads(match.group())
                
                # 验证必需字段（兼容 sub_questions / aspects）
                if 'sub_questions' in result and isinstance(result['sub_questions'], list):
                    if len(result['sub_questions']) > 0:
                        print(f"✓ Decomposition successful: {len(result['sub_questions'])} sub-questions")
                        return result
                if 'aspects' in result and isinstance(result['aspects'], list):
                    if len(result['aspects']) > 0:
                        print(f"✓ Decomposition successful: {len(result['aspects'])} aspects")
                        return result
        
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON parse error: {e}")
        except Exception as e:
            print(f"⚠️  Unexpected error: {e}")
        
        # 返回 fallback
        print("⚠️  Using fallback decomposition")
        return self._create_fallback(question)
    
    def _create_fallback(self, question: str) -> Dict:
        """创建 fallback 分解结果"""
        return {
            "sub_questions": [
                {
                    "id": "SQ1",
                    "sub_question": f"How can we answer: {question[:60]}?",
                    "hypothesis": "Need direct code evidence before concluding",
                    "entry_candidates": ["unknown"],
                    "symbols": self._extract_symbols(question),
                    "required_evidence": ["definition location", "call path"],
                    "exit_criterion": "At least 2 grounded evidence items with line refs",
                    "status": "open",
                    "priority": 1,
                }
            ],
            "synthesis": "Answer based on code exploration",
            "estimated_hops": 1,
            "unresolved_symbols": [],
        }

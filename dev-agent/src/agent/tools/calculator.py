"""Example calculator tool for Phase 1 demonstration."""

import ast
import operator
from typing import Any

from agent.tools.base import BaseTool, ToolParameter, ToolResult


class CalculatorTool(BaseTool):
    """Simple calculator tool for mathematical operations.

    Supports basic arithmetic operations: +, -, *, /, **, %.
    """

    # Allowed operators
    OPERATORS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    @property
    def name(self) -> str:
        """Tool name."""
        return "calculator"

    @property
    def description(self) -> str:
        """Tool description."""
        return (
            "Evaluates mathematical expressions. "
            "Supports +, -, *, /, **, %. Example: '2 + 3 * 4'"
        )

    @property
    def parameters(self) -> list[ToolParameter]:
        """Tool parameters."""
        return [
            ToolParameter(
                name="expression",
                type="string",
                description="Mathematical expression to evaluate",
                required=True,
            )
        ]

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute calculator operation.

        Args:
            expression: Mathematical expression string

        Returns:
            Calculation result
        """
        expression = kwargs.get("expression", "")

        if not expression:
            return ToolResult(
                success=False,
                output=None,
                error="No expression provided",
            )

        try:
            # Parse and evaluate safely
            result = self._evaluate_expr(expression)

            return ToolResult(
                success=True,
                output=result,
                metadata={"expression": expression},
            )

        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Calculation error: {str(e)}",
            )

    def _evaluate_expr(self, expr: str) -> float:
        """Safely evaluate mathematical expression.

        Args:
            expr: Expression string

        Returns:
            Evaluation result

        Raises:
            ValueError: If expression is invalid or unsafe
        """
        try:
            node = ast.parse(expr, mode="eval")
        except SyntaxError as e:
            raise ValueError(f"Invalid expression syntax: {e}")

        return self._eval_node(node.body)

    def _eval_node(self, node: ast.AST) -> float:
        """Recursively evaluate AST node.

        Args:
            node: AST node to evaluate

        Returns:
            Evaluation result

        Raises:
            ValueError: If node type is not allowed
        """
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return float(node.value)
            raise ValueError(f"Unsupported constant type: {type(node.value)}")

        elif isinstance(node, ast.BinOp):
            left = self._eval_node(node.left)
            right = self._eval_node(node.right)
            op_type = type(node.op)

            if op_type not in self.OPERATORS:
                raise ValueError(f"Unsupported operator: {op_type.__name__}")

            return self.OPERATORS[op_type](left, right)

        elif isinstance(node, ast.UnaryOp):
            operand = self._eval_node(node.operand)
            op_type = type(node.op)

            if op_type not in self.OPERATORS:
                raise ValueError(f"Unsupported unary operator: {op_type.__name__}")

            return self.OPERATORS[op_type](operand)

        else:
            raise ValueError(f"Unsupported expression type: {type(node).__name__}")


def register_calculator_tool() -> None:
    """Register calculator tool with global registry."""
    from agent.tools.base import get_tool_registry

    registry = get_tool_registry()
    registry.register(CalculatorTool())

"""aec-mcp：统一 AEC MCP 引擎层。

公开 API：
- ``units``      统一 mm 单位解析（支持 "3.6m" 字符串）
- ``errors``     统一错误码 E_UNIT / E_GEOM / E_NOT_FOUND / E_CONSTRAINT / E_ENGINE_DOWN …
- ``plan``       建模 DSL（Plan/Step + 校验）
- ``compiler``   DSL → 引擎调用序列（纯函数）
- ``transaction``preview / commit / rollback 编排
- ``engines``    revit / acad / sw 适配器注册表
"""

from .errors import AecError, ErrorCode
from .plan import Plan, Step, load_plan, validate_plan
from .transaction import Transaction

__version__ = "0.1.0"

__all__ = ["AecError", "ErrorCode", "Plan", "Step", "Transaction", "load_plan", "validate_plan"]

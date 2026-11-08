from enum import StrEnum


class ToolCategory(StrEnum):
    TRANSACTIONS = "transactions"
    ANALYSIS = "analysis"
    BUDGETS = "budgets"
    CATEGORIES = "categories"


TOOL_CATEGORIES: dict[str, ToolCategory] = {
    "propose_transaction": ToolCategory.TRANSACTIONS,
    "search_transactions": ToolCategory.TRANSACTIONS,
    "get_summary": ToolCategory.ANALYSIS,
    "get_breakdown_by_category": ToolCategory.ANALYSIS,
    "compare_periods": ToolCategory.ANALYSIS,
    "simulate_purchase": ToolCategory.ANALYSIS,
    "get_budget_status": ToolCategory.BUDGETS,
    "propose_budget": ToolCategory.BUDGETS,
    "list_categories": ToolCategory.CATEGORIES,
}

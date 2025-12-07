from . import _AWS


class _Cost(_AWS):
    _type = "cost"
    _icon_dir = "resource_images/aws/cost"


class Budgets(_Cost):
    _icon = "budgets.png"


class CostAndUsageReport(_Cost):
    _icon = "cost-and-usage-report.png"


class CostExplorer(_Cost):
    _icon = "cost-explorer.png"


class ReservedInstanceReporting(_Cost):
    _icon = "reserved-instance-reporting.png"


class SavingsPlans(_Cost):
    _icon = "savings-plans.png"


# Aliases

# Terraform aliases
aws_budgets_budget = Budgets
aws_cur_report_definition = CostAndUsageReport
aws_ce_cost_category = CostExplorer

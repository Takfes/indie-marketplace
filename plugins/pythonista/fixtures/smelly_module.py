"""Deliberately smelly module for exercising python-scan's analyzers,
python-quality-tools, and the judgment skills (python-review, python-refactor,
python-patterns, python-document, python-workflow) that build on their evidence.

Every category below maps to one python-scan analyzer:
  - find_code_smells:      magic numbers, bare except, god class, long param list
  - find_coupling_issues:  Feature Envy, Message Chain
  - find_dead_code:        unused import, unused variable, unreachable code, unused function
  - find_duplicates:       two near-identical functions
  - find_overengineering:  single-implementation "strategy" interface, thin wrapper
  - find_unpythonic:       range(len(...)), == True, manual string concat in a loop
  - check_documentation:   most of this has no docstring or type hints, on purpose
  - analyze_multi_metrics: process_order's deep nesting drives up complexity
"""

import json  # unused import -- find_dead_code / ruff F401
import os


def unused_helper():
    return 42  # never called -- find_dead_code


class OrderProcessor:
    # God class: validation, pricing, persistence, and notification all in one.
    def __init__(self, db, mailer, logger, config, cache, formatter, retries):
        self.db = db
        self.mailer = mailer
        self.logger = logger
        self.config = config
        self.cache = cache
        self.formatter = formatter
        self.retries = retries

    def process_order(self, order):
        if order:
            if order.get("items"):
                for i in range(len(order["items"])):  # unpythonic: range(len(...))
                    item = order["items"][i]
                    if item.get("qty"):
                        if item["qty"] > 0:
                            if item.get("price"):
                                if item["price"] > 0:
                                    total = item["qty"] * item["price"] * 1.0825  # magic number
                                    unused_total = total  # unused variable
        try:
            self.db.save(order)
        except:  # bare except -- find_code_smells / ruff E722
            pass
        return True

    def validate(self, order):
        # Feature Envy: reaches deep into order.customer.address instead of asking order
        zip_code = order.customer.address.zip
        return zip_code is not None

    def notify(self, order):
        # Message Chain
        return self.db.session.connection.execute("SELECT 1")

    def build_receipt(self, order):
        lines = ""
        for i in range(len(order["items"])):  # unpythonic again
            lines += str(order["items"][i]) + "\n"  # manual concat instead of join
        return lines

    def is_valid(self, order):
        return order.get("valid") == True  # unpythonic: == True -- ruff E712


class PricingStrategy:
    # Single-implementation interface -- find_overengineering
    def calculate(self, order):
        raise NotImplementedError


class StandardPricingStrategy(PricingStrategy):
    def calculate(self, order):
        return sum(i["price"] for i in order["items"])


def apply_pricing(order):
    # Thin wrapper -- find_overengineering
    return StandardPricingStrategy().calculate(order)


def compute_total_v1(items):
    total = 0
    for item in items:
        total += item["price"] * item["qty"]
    return total


def compute_total_v2(items):
    # near-duplicate of compute_total_v1 -- find_duplicates
    total = 0
    for item in items:
        total += item["price"] * item["qty"]
    return total


def unreachable_example():
    return 1
    print("never runs")  # unreachable code -- find_dead_code

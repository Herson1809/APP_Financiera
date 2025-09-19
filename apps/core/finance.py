import math
from dataclasses import dataclass
from typing import List

def pmt(rate_per_period: float, number_of_payments: int, present_value: float, future_value: float = 0.0, when: int = 0) -> float:
    """Excel-like PMT. when=0 (end), 1 (begin)"""
    if rate_per_period == 0:
        return -(present_value + future_value) / number_of_payments
    r = rate_per_period
    pvif = (1 + r) ** number_of_payments
    payment = -r * (present_value * pvif + future_value) / ((1 + r * when) * (pvif - 1))
    return payment

@dataclass
class AmortRow:
    period: int
    installment: float
    interest: float
    principal: float
    balance: float

def build_amortization(principal: float, annual_rate: float, months: int, when: int = 0) -> List[AmortRow]:
    r = annual_rate / 12.0
    pay = pmt(r, months, principal, 0.0, when)
    bal = principal
    rows = []
    for t in range(1, months + 1):
        interest = bal * r
        principal_part = pay - interest
        bal = bal + interest + principal_part  # pay is negative, principal_part negative -> reduce balance
        rows.append(AmortRow(period=t, installment=pay, interest=interest, principal=principal_part, balance=bal))
    return rows

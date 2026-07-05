"""Hidden grader for the GEN task. Imports evaluate() from solution.py in cwd."""
import math
import pytest
from solution import evaluate


def test_basic_precedence():
    assert evaluate("2+3*4") == 14


def test_parens():
    assert evaluate("(2+3)*4") == 20


def test_right_assoc_power():
    assert evaluate("2**3**2") == 512


def test_unary_minus_vs_power():
    assert evaluate("-2**2") == -4


def test_paren_unary_power():
    assert evaluate("(-2)**2") == 4


def test_negative_exponent():
    assert evaluate("2**-1") == 0.5


def test_division_float():
    assert evaluate("7/2") == 3.5


def test_sub_div_precedence():
    assert evaluate("6-4/2") == 4


def test_whitespace():
    assert evaluate("  1 +\t2 ") == 3


def test_decimals():
    assert math.isclose(evaluate("0.5*4.4"), 2.2)


def test_nested_unary():
    assert evaluate("-(-3)") == 3


def test_malformed_empty():
    with pytest.raises(ValueError):
        evaluate("")


def test_malformed_trailing_op():
    with pytest.raises(ValueError):
        evaluate("1+")


def test_malformed_unbalanced():
    with pytest.raises(ValueError):
        evaluate("(1+2")


def test_malformed_chars():
    with pytest.raises(ValueError):
        evaluate("a+b")


def test_zero_division():
    with pytest.raises(ZeroDivisionError):
        evaluate("1/0")

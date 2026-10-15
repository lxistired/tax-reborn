"""Owned finite coefficient model for positive whole tax-table midpoints.

The divisor set2/25/50 terminates before native long-division remainder code.
Only selected nonnegative/exponent0 operands and successful allocations are
eligible. This does not implement arbitrary native fixed-point arithmetic.
"""
from dataclasses import dataclass

MAX_VALUE = 10**9
SCALE_GUARD = 0x147ae147ae147af
COEFFICIENT_GUARD = 0xccccccccccccccd
APPEND_GUARD = 0xccccccccccccccc


@dataclass(frozen=True)
class Fixed:
    coefficient: int
    exponent: int


def divide_terminating_whole(numerator, denominator):
    if type(numerator) is not int or not 0 <= numerator <= MAX_VALUE or type(denominator) is not int or denominator not in (2, 25, 50):
        raise ValueError('Selected nonnegative whole input and denominator2/25/50 required')
    if numerator == 0: return Fixed(0, 0), {'zero_early_return': True, 'remaining_fractional_division': False}
    n, d, exponent = numerator, denominator, 0
    while d % 10 == 0 and exponent < 18:
        d //= 10; exponent += 1
    scaled = 0
    if n < COEFFICIENT_GUARD and exponent < 18:
        while True:
            previous, old_exponent = n, exponent
            n *= 10; exponent += 1; scaled += 1
            if old_exponent > 16 or previous >= SCALE_GUARD: break
    quotient, remainder = divmod(n, d)
    if remainder != 0 or exponent > 18 or quotient >= 2**63:
        raise ValueError('Unclosed remainder extension, multiprecision division or overflow refused')
    return Fixed(quotient, exponent), {'scaled_steps': scaled, 'normalized_divisor': d,
        'scaled_numerator': n, 'remainder': remainder, 'remaining_fractional_division': False}


def floor_zero(value):
    if not isinstance(value, Fixed) or not 0 <= value.exponent <= 18 or not 0 <= value.coefficient < 2**63:
        raise ValueError('Finite nonnegative private temporary required')
    return Fixed(value.coefficient // 10**value.exponent, 0)


def add_whole_and_half(whole, half):
    if type(whole) is not int or not 0 <= whole <= MAX_VALUE or not isinstance(half, Fixed) or not 0 <= half.exponent <= 18 or not 0 < half.coefficient < 2**63:
        raise ValueError('Selected whole base and positive native half-width required')
    power = 10**half.exponent
    # Current profile supplies exactly12.5or25, represented with the actual
    # unnormalized exponent produced by native division.
    if half.coefficient * 2 not in (25 * power, 50 * power):
        raise ValueError('Only source half-width12.5/25 allowed')
    quotient, remainder = divmod(half.coefficient, power)
    coefficient, exponent, remaining = quotient + whole, 0, half.exponent
    digits = 0
    while coefficient < COEFFICIENT_GUARD and remaining:
        digit, rest = divmod(remainder, 10**(remaining - 1))
        if coefficient == APPEND_GUARD and digit >= 7:
            raise ValueError('Unclosed native significant-digit rounding guard')
        coefficient = coefficient * 10 + digit
        remainder = rest; exponent += 1; remaining -= 1; digits += 1
        if coefficient > APPEND_GUARD or remaining == 0: break
    threshold = 1 if remaining == 0 else 5 * 10**(remaining - 1)
    rounded = coefficient + int(remainder >= threshold)
    if remainder != 0 or rounded >= 2**63:
        raise ValueError('Only exact nonnegative mixed-exponent Add branch allowed')
    return Fixed(rounded, exponent), {'appended_digits': digits, 'unconsumed_exponent_digits': remaining,
        'unconsumed_remainder': remainder, 'native_final_rounding_changes_value': False}


def ceil_zero(value):
    if not isinstance(value, Fixed) or not 0 <= value.exponent <= 18 or not 0 <= value.coefficient < 2**63:
        raise ValueError('Finite nonnegative private result required')
    quotient, remainder = divmod(value.coefficient, 10**value.exponent)
    return Fixed(quotient + int(remainder != 0), 0)


def midpoint_whole(value, width):
    if type(value) is not int or not 0 <= value <= MAX_VALUE or type(width) is not int or width not in (25, 50):
        raise ValueError('Selected nonnegative exact whole tax input and width25/50 required')
    ratio, division = divide_terminating_whole(value, width)
    floored = floor_zero(ratio)
    # Native Floor mutates its private this object. Native Multiply then uses
    # that floored quotient; its exact product fits signed64 here. Native boost
    # integer multiply/format/allocation success is the normal-path boundary.
    base = floored.coefficient * width
    half, halved = divide_terminating_whole(width, 2)
    added, addition = add_whole_and_half(base, half)
    result = ceil_zero(added)
    return result.coefficient, {'ratio': ratio, 'floor_mutates_private_quotient': floored,
        'exact_small_product': base, 'half': half, 'before_ceil': added,
        'ceil_mutates_private_result': result, 'division': division, 'width_division': halved,
        'mixed_exponent_Add': addition, 'FullMath_precision0_native_kind': 10,
        'native_boost_integer_multiply_and_allocator_success_supplied': True,
        'original_native_execution': 0}

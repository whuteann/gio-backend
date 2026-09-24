"""Numerology + colour-breakdown — pure functions of `birthdate`.

Note: this is a best-effort standard-numerology implementation, not a byte-
for-byte port of the frontend's `lifePathNumber`/`birthdayNumber`/
`talentNumber` (that source wasn't available while writing this). Same
concept and same "deterministic from birthdate" contract; exact numbers may
differ from what the frontend currently shows for a given birthdate.
"""

from app.services.content import COLOUR_ORDER
from app.services.scoring import colour_key_from_seed, seeded_hash

MASTER_NUMBERS = {11, 22, 33}


def _digit_sum(n: int) -> int:
    return sum(int(c) for c in str(n))


def _reduce(n: int) -> int:
    while n > 9 and n not in MASTER_NUMBERS:
        n = _digit_sum(n)
    return n


def life_path_number(birthdate: str) -> int:
    digits_only = "".join(c for c in birthdate if c.isdigit())
    return _reduce(_digit_sum(int(digits_only)))


def birthday_number(birthdate: str) -> int:
    day = int(birthdate.split("-")[2])
    return _reduce(day)


def talent_number(birthdate: str) -> int:
    return _reduce(life_path_number(birthdate) + birthday_number(birthdate))


def colour_affinity_scores(birthdate: str) -> dict:
    dominant = colour_key_from_seed(birthdate)
    scores = []
    for key in COLOUR_ORDER:
        if key == dominant:
            score = 88 + (seeded_hash(f"{birthdate}:{key}:dominant") % 10)
        else:
            score = 40 + (seeded_hash(f"{birthdate}:{key}") % 40)
        scores.append({"colour_key": key, "score": score})
    return {"dominant_colour_key": dominant, "scores": scores}


# --- Core Personality generation (real numerology) ---------------------------
# Richer than the simplified functions above — ported from sample-logic.py's
# methodology (see docs/behaviour_log_0001.md) for app/services/ai_personality.py
# to hand the AI as fixed, pre-computed facts. Deliberately separate from
# life_path_number/birthday_number/talent_number above, which stay as-is for
# the existing /personality/numerology and /personality/colour-breakdown
# endpoints — not touched by this pass.

def _reduce_to_single_digit(n: int, preserve_masters: bool = True) -> int:
    while n > 9:
        if preserve_masters and n in MASTER_NUMBERS:
            return n
        n = _digit_sum(n)
    return n


def calculate_birthday_number(birthdate: str) -> int:
    """Day-of-month, reduced to a single digit, master numbers preserved."""
    day = int(birthdate.split("-")[2])
    return _reduce_to_single_digit(day)


def calculate_life_path_number(birthdate: str) -> int:
    """Year/month/day reduced separately, then summed and reduced again —
    not the same as summing every digit at once (life_path_number above)."""
    year, month, day = (int(p) for p in birthdate.split("-"))
    year_reduced = _reduce_to_single_digit(year, preserve_masters=False)
    month_reduced = _reduce_to_single_digit(month, preserve_masters=False)
    day_reduced = _reduce_to_single_digit(day, preserve_masters=False)
    return _reduce_to_single_digit(year_reduced + month_reduced + day_reduced)


def calculate_talent_number(birthdate: str) -> str:
    """"XX/N" compound string (e.g. "38/2") — sum of all 8 date digits as
    XX, further reduced to N. A compound value, hence the String column."""
    digits_only = birthdate.replace("-", "")
    compound = _digit_sum(int(digits_only))
    reduced = compound
    while reduced > 9:
        reduced = _digit_sum(reduced)
    return f"{compound:02d}/{reduced}"


# Digit-pair -> colour buckets, replacing sample-logic.py's Wood/Fire/Earth/
# Metal/Water mapping with Gio's 5 colours — confirmed mapping (each pairing
# matches the colour's existing static personality in content.py::COLOURS):
# Forest<->Wood(1,2), Scarlet<->Fire(3,4), Russet<->Earth(5,6),
# Gold<->Metal(7,8), Ocean<->Water(9,0).
_COLOUR_DIGIT_PAIRS = {
    "forest": (1, 2),
    "scarlet": (3, 4),
    "russet": (5, 6),
    "gold": (7, 8),
    "ocean": (9, 0),
}


def calculate_colour_weights(
    birthdate: str, birthday_number: int, life_path_number: int, talent_number: str
) -> dict[str, int]:
    """Digit-frequency weighting across the 5 Gio colours — a direct port of
    sample-logic.py's _build_count_digits/_freq_map/_element_weights, just
    bucketed by colour instead of Chinese element."""
    year, month, day = birthdate.split("-")
    talent_xx = talent_number.split("/")[0]

    digits: list[int] = []
    digits.extend(int(d) for d in year + month.zfill(2) + day.zfill(2))
    digits.extend(int(d) for d in str(birthday_number))
    digits.extend(int(d) for d in str(life_path_number))
    digits.extend(int(d) for d in talent_xx.zfill(2))

    freq = {i: 0 for i in range(10)}
    for d in digits:
        if 0 <= d <= 9:
            freq[d] += 1

    total = len(digits)
    weights: dict[str, int] = {}
    for colour, (a, b) in _COLOUR_DIGIT_PAIRS.items():
        count = freq[a] + freq[b]
        weight = round(30 * count / total) if total else 0
        weights[colour] = max(0, min(30, weight))
    return weights

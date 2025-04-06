# File: drf_auto_generator/test_codegen.py

import logging
from typing import Dict, Any
from datetime import timezone
from faker import Faker  # Import Faker


logger = logging.getLogger(__name__)
fake = Faker()  # Initialize faker instance


def _get_faker_value(
    field_type: str, options: Dict[str, Any], unique: bool = False
) -> str:
    """Generate a plausible fake value based on Django field type and options."""
    # Use repr() to get string representation suitable for templates
    max_len = options.get("max_length")

    # Prioritize unique if requested (simple counter approach for now)
    # TODO: Improve unique generation (e.g., using faker.unique)
    if unique:
        unique_suffix = fake.unique.random_int(min=1000, max=9999)
    else:
        unique_suffix = ""  # No suffix needed normally

    # Map field types to Faker methods
    if field_type in ["EmailField"]:
        return repr(fake.unique.email() if unique else fake.email())
    elif field_type in ["URLField"]:
        return repr(fake.unique.url() if unique else fake.url())
    elif field_type in ["SlugField"]:
        # Generate slug from words, ensuring uniqueness if needed
        slug_base = fake.slug(number_of_words=3)
        return repr(f"{slug_base}-{unique_suffix}" if unique else slug_base)[
            : max_len or 50
        ]  # Limit slug length
    elif field_type in ["CharField"]:
        # Generate reasonably short text, add suffix if unique needed
        if max_len and max_len <= 15:
            base_str = fake.word()
        else:
            base_str = fake.sentence(nb_words=4)
        unique_str = f"{base_str} {unique_suffix}".strip()
        return repr(unique_str[:max_len] if max_len else unique_str)
    elif field_type in ["TextField"]:
        return repr(
            fake.paragraph(nb_sentences=2)
        )  # Keep text relatively short for tests
    elif field_type in [
        "IntegerField",
        "PositiveIntegerField",
        "SmallIntegerField",
        "BigIntegerField",
    ]:
        min_val = 1 if "Positive" in field_type else -1000
        max_val = 10000
        return repr(fake.random_int(min=min_val, max=max_val))
    elif field_type in ["FloatField", "DecimalField"]:
        # Generate float, template might need Decimal() wrapper for DecimalField
        # Use right_digits and left_digits based on options if available
        r_digits = options.get("decimal_places", 2)
        l_digits = options.get("max_digits", 5) - r_digits
        if l_digits <= 0:
            l_digits = 3
        val = fake.pyfloat(left_digits=l_digits, right_digits=r_digits, positive=True)
        # For DecimalField, wrap in Decimal() in the template later if needed
        return repr(val)  # Return as float representation for now
    elif field_type in ["BooleanField"]:
        return repr(fake.boolean())
    elif field_type in ["DateField"]:
        return repr(fake.date())  # Returns string like 'YYYY-MM-DD'
    elif field_type in ["DateTimeField"]:
        # Generate timezone-aware datetime string in ISO format
        dt_aware = fake.date_time(tzinfo=timezone.utc)
        return repr(dt_aware.isoformat())
    elif field_type in ["TimeField"]:
        return repr(fake.time())  # Returns string like 'HH:MM:SS'
    elif field_type in ["UUIDField"]:
        return repr(str(fake.uuid4()))  # Generate UUID string
    elif field_type in ["JSONField"]:
        # Generate simple JSON structure
        return repr(fake.json(data_columns={"key1": "pystr", "key2": "pyint"}))
    else:
        # Fallback for unknown types
        return repr(f"fake_{field_type.lower()}{unique_suffix}")


def _generate_invalid_value(field_type: str) -> str:
    """Generate a value of an intentionally incorrect type."""
    if field_type in [
        "CharField",
        "TextField",
        "EmailField",
        "URLField",
        "SlugField",
        "DateField",
        "DateTimeField",
        "TimeField",
        "UUIDField",
    ]:
        return repr(12345)  # Number instead of string
    elif field_type in [
        "IntegerField",
        "PositiveIntegerField",
        "SmallIntegerField",
        "BigIntegerField",
        "FloatField",
        "DecimalField",
    ]:
        return repr("not_a_number")  # String instead of number
    elif field_type in ["BooleanField"]:
        return repr("not_a_bool")
    elif field_type in ["JSONField"]:
        return repr("this is not json")
    else:
        return repr(None)  # Use None as generic invalid

import json
import os
from datetime import datetime
from pathlib import Path


# ============================================================
# GEMINI PRICING
# ============================================================
#
# These are configurable through environment variables.
#
# If Google's pricing changes, you only need to update the
# values here or in your .env file.
#
# Values are USD per 1 MILLION tokens.
#
# ============================================================

INPUT_PRICE_PER_MILLION = float(
    os.getenv("GEMINI_INPUT_PRICE_PER_MILLION", "0.75")
)

OUTPUT_PRICE_PER_MILLION = float(
    os.getenv("GEMINI_OUTPUT_PRICE_PER_MILLION", "3.75")
)

CACHED_INPUT_PRICE_PER_MILLION = float(
    os.getenv("GEMINI_CACHED_INPUT_PRICE_PER_MILLION", "0")
)


USAGE_FILE = Path(__file__).resolve().parent / "gemini_usage.json"


# ============================================================
# SAFE INTEGER
# ============================================================

def safe_int(value):
    """
    Convert a value to int safely.
    """

    if value is None:
        return 0

    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ============================================================
# EXTRACT USAGE
# ============================================================

def extract_usage(response):
    """
    Extract token usage from a Gemini API response.

    Returns a normal Python dictionary so the rest of QuantIQ
    doesn't depend directly on Gemini's usage object.
    """

    usage = getattr(response, "usage_metadata", None)

    if usage is None:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "cached_tokens": 0,
            "thinking_tokens": 0,
        }

    input_tokens = safe_int(
        getattr(usage, "prompt_token_count", None)
    )

    output_tokens = safe_int(
        getattr(usage, "candidates_token_count", None)
    )

    total_tokens = safe_int(
        getattr(usage, "total_token_count", None)
    )

    cached_tokens = safe_int(
        getattr(usage, "cached_content_token_count", None)
    )

    thinking_tokens = safe_int(
        getattr(usage, "thoughts_token_count", None)
    )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "cached_tokens": cached_tokens,
        "thinking_tokens": thinking_tokens,
    }


# ============================================================
# CALCULATE COST
# ============================================================

def calculate_cost(usage):
    """
    Calculate estimated Gemini API cost in USD.

    Pricing is configurable above.
    """

    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)
    cached_tokens = usage.get("cached_tokens", 0)

    normal_input_tokens = max(
        input_tokens - cached_tokens,
        0
    )

    normal_input_cost = (
        normal_input_tokens / 1_000_000
    ) * INPUT_PRICE_PER_MILLION

    cached_input_cost = (
        cached_tokens / 1_000_000
    ) * CACHED_INPUT_PRICE_PER_MILLION

    output_cost = (
        output_tokens / 1_000_000
    ) * OUTPUT_PRICE_PER_MILLION

    total_cost = (
        normal_input_cost
        + cached_input_cost
        + output_cost
    )

    return {
        "input_cost_usd": normal_input_cost,
        "cached_input_cost_usd": cached_input_cost,
        "output_cost_usd": output_cost,
        "total_cost_usd": total_cost,
    }


# ============================================================
# LOAD USAGE HISTORY
# ============================================================

def load_usage_history():
    """
    Load cumulative usage from gemini_usage.json.
    """

    if not USAGE_FILE.exists():
        return {
            "total_requests": 0,
            "planner_requests": 0,
            "answer_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cached_tokens": 0,
            "total_thinking_tokens": 0,
            "total_cost_usd": 0.0,
            "planner_cost_usd": 0.0,
            "answer_cost_usd": 0.0,
        }

    try:
        with open(
            USAGE_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            data = json.load(file)

        return data

    except Exception:
        return {
            "total_requests": 0,
            "planner_requests": 0,
            "answer_requests": 0,
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_tokens": 0,
            "total_cached_tokens": 0,
            "total_thinking_tokens": 0,
            "total_cost_usd": 0.0,
            "planner_cost_usd": 0.0,
            "answer_cost_usd": 0.0,
        }


# ============================================================
# SAVE USAGE HISTORY
# ============================================================

def save_usage_history(data):
    """
    Save cumulative usage.
    """

    try:
        with open(
            USAGE_FILE,
            "w",
            encoding="utf-8"
        ) as file:
            json.dump(
                data,
                file,
                indent=2
            )

    except Exception as error:
        print(
            f"[Gemini Usage] Could not save usage: {error}"
        )


# ============================================================
# RECORD USAGE
# ============================================================

def record_usage(
    response,
    call_type="unknown"
):
    """
    Extract, calculate, print and persist Gemini usage.

    call_type:
        planner
        answer
        unknown
    """

    usage = extract_usage(response)

    cost = calculate_cost(usage)

    history = load_usage_history()

    history["total_requests"] += 1

    if call_type == "planner":
        history["planner_requests"] += 1

    elif call_type == "answer":
        history["answer_requests"] += 1

    history["total_input_tokens"] += usage["input_tokens"]

    history["total_output_tokens"] += usage["output_tokens"]

    history["total_tokens"] += usage["total_tokens"]

    history["total_cached_tokens"] += usage["cached_tokens"]

    history["total_thinking_tokens"] += usage["thinking_tokens"]

    history["total_cost_usd"] += cost["total_cost_usd"]

    if call_type == "planner":
        history["planner_cost_usd"] += cost["total_cost_usd"]

    elif call_type == "answer":
        history["answer_cost_usd"] += cost["total_cost_usd"]

    history["last_updated"] = datetime.now().isoformat()

    save_usage_history(history)

    # ========================================================
    # TERMINAL OUTPUT
    # ========================================================

    title = call_type.upper()

    print()
    print("=" * 60)
    print(f"GEMINI {title} USAGE")
    print("=" * 60)

    print(
        f"Input tokens      : {usage['input_tokens']:,}"
    )

    print(
        f"Output tokens     : {usage['output_tokens']:,}"
    )

    print(
        f"Total tokens      : {usage['total_tokens']:,}"
    )

    print(
        f"Cached tokens     : {usage['cached_tokens']:,}"
    )

    print(
        f"Thinking tokens   : {usage['thinking_tokens']:,}"
    )

    print("-" * 60)

    print(
        f"Input cost        : "
        f"${cost['input_cost_usd']:.8f}"
    )

    print(
        f"Cached input cost : "
        f"${cost['cached_input_cost_usd']:.8f}"
    )

    print(
        f"Output cost       : "
        f"${cost['output_cost_usd']:.8f}"
    )

    print(
        f"Call cost         : "
        f"${cost['total_cost_usd']:.8f}"
    )

    print("-" * 60)

    print(
        f"All-time requests : "
        f"{history['total_requests']:,}"
    )

    print(
        f"All-time tokens   : "
        f"{history['total_tokens']:,}"
    )

    print(
        f"All-time cost     : "
        f"${history['total_cost_usd']:.8f}"
    )

    print("=" * 60)
    print()

    return {
        "usage": usage,
        "cost": cost,
        "history": history,
    }


# ============================================================
# GET CURRENT SUMMARY
# ============================================================

def get_usage_summary():
    """
    Return cumulative usage summary.
    """

    history = load_usage_history()

    return {
        "total_requests": history["total_requests"],
        "planner_requests": history["planner_requests"],
        "answer_requests": history["answer_requests"],
        "total_input_tokens": history["total_input_tokens"],
        "total_output_tokens": history["total_output_tokens"],
        "total_tokens": history["total_tokens"],
        "total_cached_tokens": history["total_cached_tokens"],
        "total_thinking_tokens": history["total_thinking_tokens"],
        "total_cost_usd": history["total_cost_usd"],
        "planner_cost_usd": history["planner_cost_usd"],
        "answer_cost_usd": history["answer_cost_usd"],
    }


# ============================================================
# MAIN TEST
# ============================================================

if __name__ == "__main__":

    summary = get_usage_summary()

    print()
    print("=" * 60)
    print("QUANTIQ GEMINI USAGE SUMMARY")
    print("=" * 60)

    print(
        f"Total requests     : "
        f"{summary['total_requests']:,}"
    )

    print(
        f"Planner requests   : "
        f"{summary['planner_requests']:,}"
    )

    print(
        f"Answer requests    : "
        f"{summary['answer_requests']:,}"
    )

    print(
        f"Input tokens       : "
        f"{summary['total_input_tokens']:,}"
    )

    print(
        f"Output tokens      : "
        f"{summary['total_output_tokens']:,}"
    )

    print(
        f"Total tokens       : "
        f"{summary['total_tokens']:,}"
    )

    print(
        f"Cached tokens      : "
        f"{summary['total_cached_tokens']:,}"
    )

    print(
        f"Thinking tokens    : "
        f"{summary['total_thinking_tokens']:,}"
    )

    print(
        f"Total estimated    : "
        f"${summary['total_cost_usd']:.8f}"
    )

    print(
        f"Planner cost       : "
        f"${summary['planner_cost_usd']:.8f}"
    )

    print(
        f"Answer cost        : "
        f"${summary['answer_cost_usd']:.8f}"
    )

    print("=" * 60)
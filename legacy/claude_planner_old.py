import os
import json
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()


MODEL = "claude-sonnet-4-6"

client = Anthropic(
    api_key=os.getenv("ANTHROPIC_API_KEY")
)


PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "analyses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "intent": {
                        "type": "string"
                    },
                    "table": {
                        "type": "string"
                    },
                    "metric_column": {
                        "type": "string"
                    },
                    "aggregation": {
                        "type": "string"
                    },
                    "group_by": {
                        "type": "array",
                        "items": {
                            "type": "string"
                        }
                    },
                    "filters": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "column": {
                                    "type": "string"
                                },
                                "operator": {
                                    "type": "string"
                                },
                                "value": {
                                    "type": "string"
                                }
                            },
                            "required": [
                                "column",
                                "operator",
                                "value"
                            ],
                            "additionalProperties": False
                        }
                    },
                    "sort_column": {
                        "type": "string"
                    },
                    "sort_direction": {
                        "type": "string"
                    },
                    "limit": {
                        "type": "integer"
                    },
                    "date_column": {
                        "type": "string"
                    }
                },
                "required": [
                    "intent",
                    "table",
                    "metric_column",
                    "aggregation",
                    "group_by",
                    "filters",
                    "sort_column",
                    "sort_direction",
                    "limit",
                    "date_column"
                ],
                "additionalProperties": False
            }
        }
    },
    "required": [
        "analyses"
    ],
    "additionalProperties": False
}


SYSTEM_PROMPT = """
You are the reasoning engine for QuantIQ, an AI data analyst.

Your job is to understand a user's natural-language question about an
uploaded dataset and convert it into one or more analytical plans.

IMPORTANT:

1. You must use ONLY columns and tables that exist in the supplied schema.

2. Never invent a column.

3. Never assume a dataset is a particular business domain.

4. Understand natural language semantically.

5. "Highest", "lowest", "top", "bottom", "most", and "least" usually
   represent ranking operations.

6. "Rate", "percentage", "ratio", and similar language represent a
   proportion rather than a raw count.

7. "Last", "latest", "most recent" means the most recent record based
   on an appropriate date/time column.

8. "First", "earliest" means the earliest record based on an appropriate
   date/time column.

9. If the user asks multiple analytical questions, create multiple
   analysis objects.

10. Do not fabricate results. You are only creating the analytical plan.

11. If a question asks for attrition rate, for example, identify the
    relevant attrition field and the population needed to calculate
    the rate. Do not simply return the number of attrition records.

12. If a numeric column is clearly a measure, choose an appropriate
    aggregation based on the user's wording.

13. If the user asks for a record rather than an aggregate, use the
    appropriate date column and return the relevant record.

14. The output must contain only the requested structured plan.
"""


def create_plan(question: str, schema_context: str) -> dict:

    if not os.getenv("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set."
        )

    user_prompt = f"""
DATASET SCHEMA
--------------
{schema_context}

USER QUESTION
-------------
{question}

Create the analytical plan required to answer the user's question.
"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=3000,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": user_prompt
            }
        ],
        output_config={
            "format": {
                "type": "json_schema",
                "schema": PLANNER_SCHEMA
            }
        }
    )

    text = response.content[0].text

    return json.loads(text)
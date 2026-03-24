from app.prompts import SYSTEM_PROMPT


def build_system_prompt(context: dict) -> str:
    if not context:
        return SYSTEM_PROMPT
    
    context_block = "\n\n## Current Session Context\n"
    for key, value in context.items():
        context_block += f"- {key}: {value}\n"

    return SYSTEM_PROMPT + context_block

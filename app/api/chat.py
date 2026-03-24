import json
import openai
import redis.asyncio as redis

from sqlalchemy.ext.asyncio import AsyncSession

from app.entities.service_entities.session import SessionData
from app.utils.prompt import build_system_prompt
from app.services import DiagnosticsService, EmailService, SchedulingService, VisionService
from app.settings import LLM_MODEL, OPENAI_API_KEY, REDIS_URL

openai_client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
_redis = redis.from_url(REDIS_URL, decode_responses=True)

# Tool schemas
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "diagnose_appliance",
            "description": "RAG-powered step-by-step diagnostic guidance for a home appliance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appliance_type": {"type": "string", "description": "e.g. washer, fridge, dryer"},
                    "symptoms":       {"type": "string", "description": "e.g. leaking, not cooling"},
                },
                "required": ["appliance_type", "symptoms"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_available_technicians",
            "description": "Finds available technicians in a zip code for a given appliance type.",
            "parameters": {
                "type": "object",
                "properties": {
                    "zip_code":       {"type": "string"},
                    "appliance_type": {"type": "string"},
                },
                "required": ["zip_code", "appliance_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Books a technician appointment slot for the customer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id":     {"type": "string"},
                    "slot_id":        {"type": "string", "description": "The exact slot_id UUID string returned by find_available_technicians. Do not guess or invent this value."},
                    "technician_id":  {"type": "string", "description": "The exact technician_id UUID string returned by find_available_technicians. Do not guess or invent this value."},
                    "customer_name":  {"type": "string"},
                    "customer_phone": {"type": "string"},
                    "appliance_type": {"type": "string"},
                    "symptoms":       {"type": "string"},
                },
                "required": [
                    "session_id", "slot_id", "technician_id",
                    "customer_name", "customer_phone", "appliance_type", "symptoms",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_image_upload_email",
            "description": "Emails the customer a photo upload link so they can send a picture of their appliance.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_email": {"type": "string"},
                    "customer_name":  {"type": "string"},
                    "session_id":     {"type": "string"},
                    "appliance_type": {"type": "string"},
                },
                "required": ["customer_email", "customer_name", "session_id", "appliance_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_appliance_image",
            "description": "Analyzes an uploaded appliance photo using GPT-4o vision.",
            "parameters": {
                "type": "object",
                "properties": {
                    "object_key":     {"type": "string"},
                    "appliance_type": {"type": "string"},
                },
                "required": ["object_key", "appliance_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_call",
            "description": (
                "End the phone call. Call this tool after delivering the final farewell message "
                "when the conversation is fully complete — e.g. after confirming a booking, "
                "resolving the issue, or when the customer says goodbye."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "farewell_message": {
                        "type": "string",
                        "description": "A brief, warm closing message to read to the customer before hanging up.",
                    },
                },
                "required": ["farewell_message"],
            },
        },
    },
]


# Tool dispatcher
async def dispatch_tool(
    tool_name: str,
    tool_input: dict,
    session_id: str,
    db: AsyncSession,
) -> str:
    if tool_name == "diagnose_appliance":
        result = await DiagnosticsService(db).diagnose(**tool_input)

    elif tool_name == "find_available_technicians":
        result = await SchedulingService(db).find_available_technicians(**tool_input)

    elif tool_name == "book_appointment":
        tool_input.pop("session_id", None)
        result = await SchedulingService(db).book_appointment(
            session_id=session_id, call_sid=session_id, **tool_input
        )

    elif tool_name == "send_image_upload_email":
        result = await EmailService().send_image_upload_email(**tool_input)

    elif tool_name == "analyze_appliance_image":
        result = await VisionService().analyze_appliance_image(**tool_input)

    elif tool_name == "end_call":
        result = {"status": "ending_call"}

    else:
        result = {"error": f"Unknown tool: {tool_name}"}

    return json.dumps(result)


# Agentic loop
async def run_agent(
    session_id: str,
    user_text: str,
    session_data: SessionData,
    db: AsyncSession,
) -> tuple[str, bool]:
    # Check if customer uploaded a photo since the last turn
    pending_image_key = f"image_ready:{session_id}"
    object_key = await _redis.get(pending_image_key)
    if object_key:
        await _redis.delete(pending_image_key)
        appliance_type = session_data.context.get("appliance_type", "appliance")
        # Inject a synthetic system message so the LLM knows to analyze it
        user_text = (
            f"[System: The customer just uploaded a photo of their {appliance_type}. "
            f"object_key={object_key}. "
            f"Call analyze_appliance_image with this object_key and provide enhanced diagnosis.] "
            + user_text
        )

    system_prompt = build_system_prompt(session_data.context)

    messages = (
        [{"role": "system", "content": system_prompt}]
        + session_data.history
        + [{"role": "user", "content": user_text}]
    )

    should_end_call = False

    while True:
        response = await openai_client.chat.completions.create(
            model=LLM_MODEL,
            tools=TOOLS,
            tool_choice="auto",
            messages=messages,
        )

        message = response.choices[0].message

        # Tool calls
        if message.tool_calls:
            messages.append(message)
            for tool_call in message.tool_calls:
                tool_input  = json.loads(tool_call.function.arguments)
                if tool_call.function.name == "end_call":
                    should_end_call = True
                    # Use the farewell message as the final reply
                    farewell = tool_input.get("farewell_message", "")
                    tool_result = json.dumps({"status": "ending_call"})
                    messages.append({
                        "role":         "tool",
                        "tool_call_id": tool_call.id,
                        "content":      tool_result,
                    })
                    session_data.history.append({"role": "user",      "content": user_text})
                    session_data.history.append({"role": "assistant", "content": farewell})
                    return farewell, True
                tool_result = await dispatch_tool(
                    tool_call.function.name, tool_input, session_id, db
                )
                messages.append({
                    "role":         "tool",
                    "tool_call_id": tool_call.id,
                    "content":      tool_result,
                })
            continue

        # Final reply
        final_reply = message.content or ""

        session_data.history.append({"role": "user",      "content": user_text})
        session_data.history.append({"role": "assistant", "content": final_reply})

        return final_reply, should_end_call

import asyncio
from cmd import PROMPT
import logging
from pyexpat import model
import pinecone
import openai
from openai import AsyncOpenAI, RateLimitError
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Union
import time
import json
from server.ratelimiter import get_ratelimiter

rate_limiter = get_ratelimiter()

# Hypothetical config singleton
from server.configmanager import config

logger = logging.getLogger(__name__)

#####################
# Setup Keys & Pinecone
#####################
# Retrieve Pinecone key from config (instead of os.getenv)
PINECONE_KEY = config.get_or_error("PINECONE_API_KEY")
from pinecone import Pinecone

pc = Pinecone(api_key=PINECONE_KEY)

INDEX_NAME = config.get("INDEX_NAME", "mauibuildingcode")
index = pc.Index(INDEX_NAME)

#####################
# Create the FastAPI App
#####################
app = FastAPI(
    title="Maui Building Code Assistant (FastAPI)",
    description=(
        "A FastAPI service that uses Pinecone + oai.responses with gpt-4.1-mini, "
        "maintaining conversation history."
    ),
    version="2.0.0",
)

#####################
# Prompt / System Directives
#####################
SYSTEM_PROMPT = """You are an expert in Maui County building code, helping Maui tradespeople with building code questions.
Always reference actual building code when possible, speak in light pidgin.

Use these steps:
1) Provide a thorough, nuanced answer as a local Maui expert.
2) Minimize disclaimers or AI references.
3) Format your response in markdown for readability.
4) Ask if the user needs further clarification.
"""


#####################
# Request Models
#####################
class ConversationRequest(BaseModel):
    """
    The incoming request includes:
      - messages: A list of dicts with 'role' and 'content' keys
    """

    messages: List[dict]


class FeedbackRequest(BaseModel):
    feedback: str
    conversation: List[List[Union[str, None]]]


#####################
# Utility Functions
#####################
async def get_embedding(text: str) -> List[float]:
    """
    Obtain embeddings for the given text using OpenAI's embedding model.
    """
    text = text.replace("\n", " ")
    # For embeddings, we use the "text-embedding-ada-002" model
    client = AsyncOpenAI(api_key=config.get_or_error("OPENAI_API_KEY"))
    response = await client.embeddings.create(
        model="text-embedding-ada-002", input=[text]
    )
    return response.data[0].embedding


async def find_similar_texts(latest_query: str, top_k: int = None):
    """
    Query Pinecone for the user’s latest question to find relevant references.
    Uses the config pinecone_top_k if provided, otherwise default to 3.
    """
    if not top_k:
        top_k = config.get("pinecone_top_k", 3)
    query_vector = await get_embedding(latest_query)
    search_results = index.query(
        vector=query_vector, top_k=top_k, include_values=False, include_metadata=True
    )
    ids = [match["id"] for match in search_results["matches"]]
    return ids


def build_message_list(
    conversation: List[List[Union[str, None]]], references: str
) -> List[dict]:
    """
    Construct the messages list for multi-turn conversation context.
    Each item in conversation is [user_msg, assistant_msg].
    - If assistant_msg is None, it's the current user query waiting for a response.
    """
    messages = []
    # 1. System instructions
    messages.append({"role": "system", "content": SYSTEM_PROMPT})
    # 2. Any references from Pinecone
    messages.append(
        {
            "role": "system",
            "content": f"Base your responses on the following references: {references}",
        }
    )
    # 3. Add all user/assistant pairs
    for user_msg, assistant_msg in conversation:
        if user_msg:
            messages.append({"role": "user", "content": user_msg})
        if assistant_msg:
            messages.append({"role": "assistant", "content": assistant_msg})
    return messages


async def generate_response(messages: List[dict]) -> str:
    """
    Calls the 'oai.responses' or chat completion API with the desired model (gpt-4.1-mini).
    We handle potential rate-limiting via multiple attempts if configured (MAX_ATTEMPTS).
    """
    # We'll read from config
    openai_key = config.get_or_error("OPENAI_API_KEY")
    model_name = config.get("model_name", "gpt-4.1-mini")
    max_tokens = config.get("max_tokens", 500)
    temperature = config.get("temperature", 0.7)

    # If you have a rate limiter or multiple attempts, set them up:
    MAX_ATTEMPTS = config.get("MAX_ATTEMPTS", 3)

    # Whether to use 'responses' or standard chat completions
    use_responses_api = config.get("use_responses_api", True)

    oai = AsyncOpenAI(api_key=openai_key)
    timer_start_time = time.time()
    formatted_output = None
    developer_prompt = [
        {
            "role": "developer",
            "content": "Be precise and concise, use Maui building code references.",
        },
    ]
    # Combine developer instructions with the user messages
    sequence = developer_prompt + messages

    for attempt in range(MAX_ATTEMPTS):
        wait_time = await rate_limiter.get_limit("openai_requests")
        if wait_time > 0:
            await asyncio.sleep(wait_time)
        try:
            oai = AsyncOpenAI(api_key=config.get_or_error("OPENAI_API_KEY"))

            response = await oai.responses.create(
                model=model_name,
                input=sequence,
                temperature=temperature,
            )
            try:

                formatted_output = json.loads(response.output_text)

                return formatted_output
            except json.JSONDecodeError as e:
                logger.error(
                    "OAI request failed with JSONDecodeError: %s\nRaw output:\n%s",
                    e,
                    response.output_text,
                )
                return response.output_text
            break
        except RateLimitError as e:
            if hasattr(e, "response") and e.response.status_code == 429:
                await rate_limiter.limit("openai_requests", e.response)
            else:
                await rate_limiter.limit("openai_requests")

    if not formatted_output:
        logger.warning("formatted output failed... ")
        return "whoops, please stand by while we figure this out."

    timer_end_time = time.time()
    logger.info(
        json.dumps(
            {
                "event": "aoi_request",
                "latency": round(timer_end_time - timer_start_time, 3),
                "model": model_name,
            }
        )
    )
    input_tokens = response.usage.input_tokens
    output_tokens = response.usage.output_tokens
    return "Apologies, I'm encountering errors at the moment. Please try again later."


#####################
# Routes
#####################
@app.post("/api")
async def handle_conversation(data: ConversationRequest):
    """
    Handles multi-turn conversation by receiving the entire conversation array.
    1) The last user message is the new query if assistant == None.
    2) We find Pinecone references, build a message list (including prior conversation),
       call the model for a new assistant message.
    3) Return JSON with the new assistant response.
    """

    messages = data.messages
    if not messages:
        return {"answer": "No messages found."}

    # Find the last user message
    latest_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            latest_user_message = msg.get("content", "")
            break
    if not latest_user_message:
        return {"answer": "No user message found."}

    # 1) Pinecone references
    references_ids = await find_similar_texts(latest_user_message)
    references_str = (
        ", ".join(references_ids) if references_ids else "No references found."
    )

    # 2) Construct the full prompt sequence
    prompt_sequence = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": f"References: {references_str}"},
        *messages,
    ]
    # 3) Generate response
    answer = await generate_response(prompt_sequence)

    return {"answer": answer}


@app.post("/feedback")
async def handle_feedback(data: FeedbackRequest):
    """
    Receives user feedback (e.g. thumbs up/down) plus the conversation history.
    You can log, store, or handle the feedback however you like.
    """
    vote_role = data.feedback
    conversation = data.conversation
    logger.info(f"Feedback Received: {vote_role} | Conversation: {conversation}")
    return {"message": "Feedback received", "status": "ok"}

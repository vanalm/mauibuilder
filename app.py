import asyncio
import logging
import time
import json
from typing import List, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from openai import AsyncOpenAI, RateLimitError
from server.ratelimiter import get_ratelimiter
from server.configmanager import config
from pinecone import Pinecone

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

rate_limiter = get_ratelimiter()

#####################
# Setup Keys & Pinecone
#####################
# Retrieve Pinecone key from config (instead of os.getenv)
PINECONE_KEY = config.get_or_error("PINECONE_API_KEY")
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["http://localhost:7861"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
    logger.debug(
        f"[get_embedding] Received text for embedding: {text[:60]}..."
    )  # Truncate for logs
    text = text.replace("\n", " ")
    client = AsyncOpenAI(api_key=config.get_or_error("OPENAI_API_KEY"))
    response = await client.embeddings.create(
        model="text-embedding-ada-002", input=[text]
    )
    embedding = response.data[0].embedding
    logger.debug(f"[get_embedding] Embedding length: {len(embedding)}")
    return embedding

    """
    Query Pinecone for the user’s latest question to find relevant references.
    Uses the config pinecone_top_k if provided, otherwise defaults to 3.
    Applies a score threshold to filter out low-relevance results.
    """
    if not top_k:
        top_k = config.get("pinecone_top_k", 3)
    MIN_SCORE_THRESHOLD = config.get("MIN_SCORE_THRESHOLD", 0.3)


async def find_similar_texts(latest_query: str, top_k: int = None):
    if not top_k:
        top_k = config.get("pinecone_top_k", 3)
    MIN_SCORE_THRESHOLD = config.get("MIN_SCORE_THRESHOLD", 0.8)

    logger.debug(f"[find_similar_texts] Query: {latest_query}")
    logger.debug(
        f"[find_similar_texts] top_k: {top_k}, MIN_SCORE_THRESHOLD: {MIN_SCORE_THRESHOLD}"
    )

    query_vector = await get_embedding(latest_query)

    # Run the Pinecone query
    search_results = index.query(
        vector=query_vector, top_k=top_k, include_values=False, include_metadata=True
    )

    # Log the response properly
    if hasattr(search_results, "to_dict"):
        raw_dict = search_results.to_dict()
        logger.debug(
            f"[find_similar_texts] Pinecone raw response (dict): {json.dumps(raw_dict, indent=2)}"
        )
    else:
        logger.debug(
            f"[find_similar_texts] Pinecone raw response (as-is): {search_results}"
        )

    # Filter matches by a score threshold
    filtered_matches = []
    # If search_results is a dict, use search_results.get("matches", [])
    # If it's a QueryResponse, you might need raw_dict["matches"]
    # Adjust based on actual structure.
    matches = (
        search_results.get("matches")
        if isinstance(search_results, dict)
        else search_results.matches
    )

    for match in matches or []:
        score = match.get("score", 0)
        if score >= MIN_SCORE_THRESHOLD:
            filtered_matches.append(
                {
                    "id": match["id"],
                    "score": match["score"],
                    "metadata": match.get("metadata", {}),
                }
            )
        else:
            logger.debug(
                f"[find_similar_texts] Excluding match with score={score:.2f} (below threshold)"
            )

    logger.debug(
        f"[find_similar_texts] Number of filtered matches: {len(filtered_matches)}"
    )
    return filtered_matches


def build_reference_block(references: List[dict]) -> str:
    """
    Turns a list of references into a readable block for the system prompt or assistant.
    Includes snippet trimming to keep token usage in check.
    """
    logger.debug(
        f"[build_reference_block] Building reference block for {len(references)} references"
    )
    REPO_URL = config.get("repo_url", "https://github.com/username/repo/blob/main/")
    MAX_SNIPPET_LEN = config.get("MAX_SNIPPET_LEN", 300)

    if not references:
        logger.debug("[build_reference_block] No references found above threshold.")
        return "No high-confidence references found."

    lines = []
    for idx, ref in enumerate(references, start=1):
        meta = ref["metadata"]
        filename = meta.get("filename", "")
        start_line = meta.get("start_line")
        end_line = meta.get("end_line", start_line)
        link = f"{REPO_URL}{filename}"

        # Add line anchors if available
        if start_line:
            link += f"#L{start_line}"
            if end_line and end_line != start_line:
                link += f"-L{end_line}"

        # Snippet trimming
        snippet = meta.get("text", "").strip().replace("\n", " ")
        if len(snippet) > MAX_SNIPPET_LEN:
            snippet = snippet[:MAX_SNIPPET_LEN] + "..."

        score_str = f"(score={ref['score']:.2f})"
        lines.append(f'[{idx}] "{snippet}" {score_str} ({link})')

    references_block = "\n".join(lines)
    logger.debug(f"[build_reference_block] Final reference block:\n{references_block}")
    return references_block


async def generate_response(messages: List[dict]) -> str:
    """
    Calls the 'oai.responses' or chat completion API with the desired model (gpt-4.1-mini).
    We handle potential rate-limiting via multiple attempts if configured (MAX_ATTEMPTS).
    """
    logger.debug("[generate_response] Invoked with messages:")
    for m in messages:
        logger.debug(
            f"  Role: {m['role']}, Content (truncated): {m['content'][:80]}..."
        )

    openai_key = config.get_or_error("OPENAI_API_KEY")
    model_name = config.get("model_name", "gpt-4.1-mini")
    max_tokens = config.get("max_tokens", 500)
    temperature = config.get("temperature", 0.7)
    MAX_ATTEMPTS = config.get("MAX_ATTEMPTS", 3)
    use_responses_api = config.get("use_responses_api", True)

    developer_prompt = [
        {
            "role": "developer",
            "content": "Be precise and concise, use Maui building code references.",
        }
    ]
    sequence = developer_prompt + messages

    logger.debug("[generate_response] Combined developer + user messages:")
    for i, s in enumerate(sequence):
        logger.debug(f"  [{i}] {s}")

    oai = AsyncOpenAI(api_key=openai_key)
    timer_start_time = time.time()

    response = None
    for attempt in range(MAX_ATTEMPTS):
        wait_time = await rate_limiter.get_limit("openai_requests")
        if wait_time > 0:
            logger.debug(f"[generate_response] Rate-limiter wait time: {wait_time}s")
            await asyncio.sleep(wait_time)

        try:
            logger.debug(
                "[generate_response] Sending request to oai.responses.create()"
            )
            response = await oai.responses.create(
                model=model_name, input=sequence, temperature=temperature
            )
            break
        except RateLimitError as e:
            logger.warning(
                f"[generate_response] RateLimitError encountered on attempt {attempt+1}"
            )
            if hasattr(e, "response") and e.response.status_code == 429:
                await rate_limiter.limit("openai_requests", e.response)
            else:
                await rate_limiter.limit("openai_requests")

    if response is None:
        logger.error("[generate_response] No valid response after all attempts.")
        return "Sorry, we could not process this request at the moment."

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

    # Log usage if the API provides it
    if hasattr(response, "usage"):
        input_tokens = getattr(response.usage, "input_tokens", None)
        output_tokens = getattr(response.usage, "output_tokens", None)
        logger.info(
            f"[generate_response] Usage - input tokens: {input_tokens}, output tokens: {output_tokens}"
        )
    else:
        logger.debug("[generate_response] No usage info returned from the API.")

    logger.debug(
        f"[generate_response] Received response text (truncated): {response.output_text[:300]}..."
    )
    return response.output_text


#####################
# Routes
#####################
@app.post("/api")
async def handle_conversation(data: ConversationRequest):
    """
    Handles multi-turn conversation by receiving the entire conversation array.
    1) Find the last user message as the new query.
    2) Query Pinecone for references (filtered by threshold).
    3) Construct prompt (system + references + conversation).
    4) Get model response and return JSON with answer.
    """
    logger.debug("[handle_conversation] Received request with messages:")
    for i, msg in enumerate(data.messages):
        logger.debug(f"  [{i}] Role: {msg['role']}, Content: {msg['content']!r}")

    messages = data.messages
    if not messages:
        logger.debug("[handle_conversation] No messages found in request.")
        return {"answer": "No messages found."}

    # Find the last user message
    latest_user_message = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            latest_user_message = msg.get("content", "")
            break

    if not latest_user_message:
        logger.debug("[handle_conversation] No user message found in conversation.")
        return {"answer": "No user message found."}

    logger.debug(f"[handle_conversation] Latest user message: {latest_user_message!r}")

    # 1) Pinecone references
    references = await find_similar_texts(latest_user_message)
    logger.debug(f"[handle_conversation] references: {references}")

    references_block = build_reference_block(references)
    logger.debug(f"[handle_conversation] references_block: {references_block}")

    # 2) Construct the full prompt sequence
    prompt_sequence = [
        {"role": "system", "content": SYSTEM_PROMPT},
        # Put references in an 'assistant' role so it's seen as context
        {
            "role": "assistant",
            "content": f"Relevant Maui code references:\n\n{references_block}",
        },
        *messages,
    ]
    logger.debug("[handle_conversation] Final prompt sequence ready for generation.")

    # 3) Generate response
    answer = await generate_response(prompt_sequence)
    logger.debug(f"[handle_conversation] Final answer from model: {answer}")

    return {"answer": answer}


@app.post("/feedback")
async def handle_feedback(data: FeedbackRequest):
    """
    Receives user feedback (e.g. thumbs up/down) plus the conversation history.
    You can log, store, or handle the feedback however you like.
    """
    vote_role = data.feedback
    conversation = data.conversation
    logger.info(
        f"[handle_feedback] Feedback Received: {vote_role} | Conversation: {conversation}"
    )
    return {"message": "Feedback received", "status": "ok"}

import argparse
import uvicorn
import os
import sys
import logging
import dotenv

print("DEBUG: __file__=", __file__)  # see which file Python thinks is __main__
dotenv.load_dotenv()
print("DEBUG: .env load => PINECONE_API_KEY =", os.getenv("PINECONE_API_KEY"))

dotenv.load_dotenv()
from server.configmanager import config
from server.database_connect import get_db_session
from server.app import app


logger = logging.getLogger(__name__)


def check_required_env_vars(required_vars):
    """
    Checks that all required environment variables exist.
    If any are missing, exit with a message listing them.
    """
    logger.info(f"Checking required environment variables: {required_vars}")
    missing = [var for var in required_vars if os.getenv(var) is None]
    if missing:
        sys.exit(f"Error: Missing required environment variables: {', '.join(missing)}")


def initialize_logger():
    log_file = "server/logs/server.log"

    # Ensure the logs directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    logger = logging.getLogger()  # Root logger
    # Set debug or info level based on config
    if config.get("ENVIRONMENT") == "development":
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.INFO)

    # Remove existing handlers to avoid duplicates
    while logger.hasHandlers():
        logger.removeHandler(logger.handlers[0])

    # File Handler
    file_handler = logging.FileHandler(log_file, mode="a")  # Append
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Console Handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    # Attach handlers
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)


def main():
    # Variables required by app.py (or other modules) at runtime:
    required_env_vars = [
        "PINECONE_API_KEY",
        "OPENAI_API_KEY",
    ]
    check_required_env_vars(required_env_vars)

    parser = argparse.ArgumentParser(
        description="Start the Maui Building Code Assistant server."
    )

    parser.add_argument(
        "--environment",
        type=str,
        default=config.get("ENVIRONMENT") or "development",
        help="Environment (development or production).",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=config.get("host") or "0.0.0.0",
        help="Server host IP.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.get("port") or 8000,
        help="Server port.",
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        default=config.get("reload") or False,
        help="Enable auto-reload (useful in development).",
    )
    parser.add_argument(
        "--ssl_certfile",
        type=str,
        default=config.get("ssl_certfile") or "",
        help="Path to SSL certificate file.",
    )
    parser.add_argument(
        "--ssl_keyfile",
        type=str,
        default=config.get("ssl_keyfile") or "",
        help="Path to SSL key file.",
    )
    parser.add_argument(
        "--timeout_keep_alive",
        type=int,
        default=config.get("timeout_keep_alive") or 5,
        help="Keep-alive timeout (seconds) for server connections.",
    )
    parser.add_argument(
        "--index_name",
        type=str,
        default=config.get("INDEX_NAME") or "mauibuildingcode",
        help="Name of the Pinecone index for building code references.",
    )
    parser.add_argument(
        "--pinecone_top_k",
        type=int,
        default=config.get("pinecone_top_k") or 3,
        help="Number of relevant documents to retrieve from Pinecone.",
    )
    parser.add_argument(
        "--model_name",
        type=str,
        default=config.get("model_name") or "gpt-4.1-mini",
        help="Name of the LLM model to use for completions.",
    )
    parser.add_argument(
        "--max_tokens",
        type=int,
        default=config.get("max_tokens") or 500,
        help="Maximum tokens for each model response.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=config.get("temperature") or 0.7,
        help="Temperature setting for text generation calls.",
    )

    args = parser.parse_args()

    # Overwrite config values in memory with parser arguments
    config.set_temp("ENVIRONMENT", args.environment)
    config.set_temp("host", args.host)
    config.set_temp("port", args.port)
    config.set_temp("reload", args.reload)
    config.set_temp("ssl_certfile", args.ssl_certfile)
    config.set_temp("ssl_keyfile", args.ssl_keyfile)
    config.set_temp("timeout_keep_alive", args.timeout_keep_alive)
    config.set_temp("INDEX_NAME", args.index_name)
    config.set_temp("pinecone_top_k", args.pinecone_top_k)
    config.set_temp("model_name", args.model_name)
    config.set_temp("max_tokens", args.max_tokens)
    config.set_temp("temperature", args.temperature)

    initialize_logger()

    logger.info(
        f"Starting server on {config.get('host')}:{config.get('port')} "
        f"with environment={config.get('ENVIRONMENT')}"
    )

    uvicorn.run(
        app,
        host=config.get_or_error("host"),
        port=config.get_or_error("port"),
        reload=config.get("reload"),
        ssl_certfile=config.get("ssl_certfile"),
        ssl_keyfile=config.get("ssl_keyfile"),
        timeout_keep_alive=config.get("timeout_keep_alive"),
    )


if __name__ == "__main__":
    main()

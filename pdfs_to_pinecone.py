#!/usr/bin/env python3

import os
import sys
import logging
import argparse
from tkinter.filedialog import Open

from httpx import Client
import pdfplumber
from openai import OpenAI
from pinecone import Pinecone, ServerlessSpec
from typing import List
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENV = os.getenv("PINECONE_ENV", "us-west-2")
INDEX_NAME = os.getenv("INDEX_NAME", "mauibuildingcode")
SOURCE_DOCS_PATH = os.getenv("SOURCE_DOCS_PATH", "./source_docs")

client = OpenAI(api_key=OPENAI_API_KEY)

# Initialize Pinecone client
pc = Pinecone(api_key=PINECONE_API_KEY, environment=PINECONE_ENV)
# Parse environment string into region and cloud for serverless spec
parts = PINECONE_ENV.split("-")
region = parts[0]
cloud = parts[1] if len(parts) > 1 else "aws"
spec = ServerlessSpec(cloud=cloud, region=region)
# Create index if it doesn't exist
if INDEX_NAME not in pc.list_indexes().names():
    pc.create_index(name=INDEX_NAME, dimension=1536, metric="cosine", spec=spec)
# Reference the index
index = pc.Index(INDEX_NAME)


def chunk_text(text: str, chunk_size=600, overlap=50) -> List[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
    return chunks


def create_embedding(text: str) -> List[float]:
    text = text.replace("\n", " ")
    response = client.embeddings.create(model="text-embedding-ada-002", input=text)
    return response.data[0].embedding


def process_pdf_file(pdf_path: str):
    file_id = os.path.basename(pdf_path)
    logger.info(f"Processing: {file_id}")
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            text = page.extract_text()
            if not text or not text.strip():
                continue
            for i, chunk in enumerate(chunk_text(text, 600, 50)):
                embedding = create_embedding(chunk)
                metadata = {
                    "filename": file_id,
                    "page_number": page_num,
                    "chunk_index": i,
                    "text": chunk,
                }
                doc_id = f"{file_id}_p{page_num}_c{i}"
                index.upsert([(doc_id, embedding, metadata)])
                logger.debug(f"Upserted: {doc_id}")


def main():
    parser = argparse.ArgumentParser(description="Ingest PDFs into Pinecone.")
    parser.add_argument(
        "--folder", type=str, help="Path to a folder containing PDFs to process."
    )
    parser.add_argument(
        "--file", type=str, help="Path to a single PDF file to process."
    )
    args = parser.parse_args()

    if args.folder and args.file:
        parser.error("Cannot use --folder and --file together.")
    elif not args.folder and not args.file:
        parser.error("Specify either --folder <folder path> or --file <file path>.")

    if args.folder:
        if not os.path.isdir(args.folder):
            logger.error(f"Directory not found: {args.folder}")
            sys.exit(1)
        pdf_files = [f for f in os.listdir(args.folder) if f.lower().endswith(".pdf")]
        if not pdf_files:
            logger.info("No PDFs found.")
            return
        for pdf_file in tqdm(pdf_files, desc="Processing PDFs"):
            process_pdf_file(os.path.join(args.folder, pdf_file))
    else:
        if not os.path.isfile(args.file):
            logger.error(f"File not found: {args.file}")
            sys.exit(1)
        process_pdf_file(args.file)

    logger.info("Ingestion complete.")


if __name__ == "__main__":
    main()

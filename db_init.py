import openai
from openai import OpenAI
import fitz  # PyMuPDF
import os
from pinecone import Pinecone, ServerlessSpec
import numpy as np

OPENAI_KEY = os.getenv('OPENAI_KEY')
PINECONE_KEY = os.getenv('PINECONE_KEY')

from openai import OpenAI
client = OpenAI(api_key=OPENAI_KEY)


# Initialize Pinecone with the Pinecone class
pc = Pinecone(api_key=PINECONE_KEY)

index_name = "mauibuildingcode"
dimension = 1536  # Adjust based on the model's output

# Check if the index exists and create it if it doesn't
if index_name not in pc.list_indexes().names():
    pc.create_index(
        name=index_name,
        dimension=dimension,
        metric="cosine",
        spec=ServerlessSpec(
            cloud='aws',  # Or your cloud provider
            region='us-west-2'  # Or your preferred region
        )
    )

# Reference your index
index = pc.Index(name=index_name)

def extract_text_from_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def load_pdfs():
    pdf_texts = []
    for pdf_file in os.listdir('.'):
        if pdf_file.endswith(".pdf"):
            pdf_text = extract_text_from_pdf(pdf_file)
            pdf_texts.append((pdf_file, pdf_text))
    return pdf_texts

def get_embedding(text, model="text-embedding-3-small"):
   text = text.replace("\n", " ")
   return client.embeddings.create(input = [text], model=model).data[0].embedding




def insert_into_pinecone(pdf_texts):
    items_to_insert = []
    for pdf_name, text in pdf_texts:
        vector = get_embedding(text[:min(len(text), 4096)])  # Adjust based on the model limits
        if vector:  # Ensure vector is not None
            items_to_insert.append((pdf_name, vector))

    # Correct the upsert call
    if items_to_insert:
        index.upsert(vectors=items_to_insert)


if __name__ == "__main__":
    print('setting up index!')
    try:
        pdf_texts = load_pdfs()
        insert_into_pinecone(pdf_texts)
        print("Indexing complete!")
    except openai.APIConnectionError as e:
        print(f"Connection error: {e}")
        print("Details:", e.args)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print("Details:", e.args)



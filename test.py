import os
import openai
from openai import OpenAI
from pinecone import Pinecone

# Load API keys from environment variables
OPENAI_KEY = os.getenv('OPENAI_API_KEY')
PINECONE_KEY = os.getenv('PINECONE_API_KEY')

# Initialize OpenAI and Pinecone clients
pc = Pinecone(api_key=PINECONE_KEY)
client = OpenAI(api_key=OPENAI_KEY)
# Reference  Pinecone index
index_name = "mauibuildingcode"
index = pc.Index(name=index_name)

def get_embedding(text, model="text-embedding-3-small"):
   text = text.replace("\n", " ")
   return client.embeddings.create(input = [text], model=model).data[0].embedding

def find_similar_texts(user_message, top_k=3):
    """
    Perform a similarity search in the Pinecone index for the given user message.
    """
    query_vector = get_embedding(user_message)
    search_results = index.query(vector=query_vector, top_k=top_k, include_values=True)
    ids = [match["id"] for match in search_results["matches"]]
    return ids

def generate_response(similar_texts_ids, user_message):
    """
    Generate a response using OpenAI based on the IDs of similar texts.
    """
    # For simplicity, let's just pass the user message to OpenAI's GPT model
    # Fetch the texts by IDs and use them to give context to the query
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  
        messages=[
            {"role": "system", "content": "you are an assistant helping maui tradespeople with building code questions."},
            {"role": "system", "content": f"base your responses on the follwoing information: {similar_texts_ids}"},
            {"role": "user", "content": user_message}
        ],

        max_tokens=150
    )
    return response.choices[0].message
    # return response['choices'][0]['message']['content']


if __name__ == "__main__":
    user_message = "Do I have to caulk a toilet to the bathroom floor"
    similar_texts_ids = find_similar_texts(user_message)
    response = generate_response(similar_texts_ids, user_message)
    print("AI Response:", response)

from flask import Flask, request, render_template_string
import os
import openai
from pinecone import Pinecone
from openai import OpenAI

# Load API keys from environment variables
OPENAI_KEY = os.getenv('OPENAI_KEY')
PINECONE_KEY = os.getenv('PINECONE_KEY')

# Initialize OpenAI and Pinecone clients
pc = Pinecone(api_key=PINECONE_KEY)
client = OpenAI(api_key=OPENAI_KEY)

# Reference your Pinecone index
index_name = "mauibuildingcode"
index = pc.Index(name=index_name)

app = Flask(__name__)

HTML_TEMPLATE = """
<!doctype html>
<html>
<head><title>Building Code Chatbot</title></head>
<body>
  <h2>Building Code Chatbot</h2>
  <form method="post">
    <label for="message">Enter your question:</label><br>
    <input type="text" id="message" name="message" style="width:300px;"><br><br>
    <input type="submit" value="Submit">
  </form>
  {% if response %}
    <h3>Response:</h3>
    <p>{{ response }}</p>
  {% endif %}
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def chat():
    response = ""
    if request.method == 'POST':
        user_message = request.form['message']
        similar_texts_ids = find_similar_texts(user_message)
        response = generate_response(similar_texts_ids, user_message)
    return render_template_string(HTML_TEMPLATE, response=response)

def get_embedding(text, model="text-embedding-3-small"):
    text = text.replace("\n", " ")
    return client.embeddings.create(input=[text], model=model).data[0].embedding

def find_similar_texts(user_message, top_k=3):
    query_vector = get_embedding(user_message)
    search_results = index.query(vector=query_vector, top_k=top_k, include_values=True)
    ids = [match["id"] for match in search_results["matches"]]
    return ids

def generate_response(similar_texts_ids, user_message):
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are an assistant helping Maui tradespeople with building code questions."},
            {"role": "system", "content": f"Base your responses on the following information: {similar_texts_ids}"},
            {"role": "user", "content": user_message},
        ],
        max_tokens=150
    )
    return response.choices[0].message.content
    # response['choices'][0]['message']


if __name__ == '__main__':
    app.run(debug=True)

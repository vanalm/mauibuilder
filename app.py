from flask import Flask, request, render_template_string, jsonify
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
MANUAL = """You are an exper maui county building code assistant helping Maui tradespeople with building code questions. always use references to actual building code provided to answer questions, speak in light pigeon.

The user may indicate their desired VERBOSITY of your response as follows: V=1: extremely terse V=2: concise V=3: detailed (default) V=4: comprehensive V=5: exhaustive and nuanced detail with comprehensive depth and breadth. If not indicated, assume V=1: terse.

Once the user has sent a message, adopt the role of a building code expert, qualified to provide a authoritative, nuanced answer, then proceed step-by-step to respond:

1. Provide your authoritative, and nuanced answer as a local maui expert; prefix with relevant emoji and embed GOOGLE SEARCH HYPERLINKS around key terms as they naturally occur in the text, q=extended search query. Omit disclaimers, apologies, and AI self-references.  Provide unbiased, holistic guidance and analysis. Go step by step for complex answers. Do not elide code. IMPORTANT: USE ONLY GOOGLE SEARCH HYPERLINKS, no other domains are allowed. Example: 🚙 Car shopping can be stressful. 

2. Format your response using markdown for excellent readability on the fly. Users will likely be on a jobsite while reading.

3. Ask if any further clarification is necessary.
"""
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

@app.route('/chat', methods=['GET', 'POST'])
def chat():
    response = ""
    if request.method == 'POST':
        user_message = request.form['message']
        similar_texts_ids = find_similar_texts(user_message)
        response = generate_response(similar_texts_ids, user_message)
    return render_template_string(HTML_TEMPLATE, response=response)

@app.route('/api', methods=['POST', 'GET'])
def chat_api():
    if request.method == 'POST':
        data = request.get_json()  # Get data sent as JSON
        user_message = data['query']  # Extract the query from the data
        
        # Use the existing logic to process the query
        similar_texts_ids = find_similar_texts(user_message)
        response_text = generate_response(similar_texts_ids, user_message)
        
        # Return the response in JSON format
        return jsonify({"answer": response_text})    
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
            {"role": "system", "content": MANUAL
},
            {"role": "system", "content": f"Base your responses on the following information: {similar_texts_ids}"},
            {"role": "user", "content": user_message},
        ],
        max_tokens=500
    )
    return response.choices[0].message.content
    # response['choices'][0]['message']


if __name__ == '__main__':
    app.run(debug=True)

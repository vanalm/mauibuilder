import gradio as gr
import requests

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
API_URL = "http://127.0.0.1:8000/api"  # FastAPI endpoint
FEEDBACK_URL = "http://127.0.0.1:8000/feedback"  # Optional feedback endpoint


def clear_history():
    # Reset both the conversation state and the displayed chat
    return [], []


def display_history(history):
    """
    Convert a list of {role, content} messages into the [[user, assistant], ...] format
    expected by gr.Chatbot.
    """
    pairs = []
    for i, msg in enumerate(history):
        if msg["role"] == "user":
            # Look for the next assistant message
            if i + 1 < len(history) and history[i + 1]["role"] == "assistant":
                pairs.append([msg["content"], history[i + 1]["content"]])
            else:
                pairs.append([msg["content"], None])
    return pairs


# ------------------------------------------------------------------
# CUSTOM CSS
# ------------------------------------------------------------------
CUSTOM_CSS = """
/* Title banner */
#top_banner {
  text-align: center;
  font-size: 1.75rem;
  font-weight: bold;
  color: #0b3d78;
  margin-bottom: 20px;
}

/* Chatbot container: max-width for mobile friendliness */
#chatbot_box {
  margin: 0 auto;
  max-width: 600px;
  position: relative; /* so we can position children absolutely */
}

/* Footer styling */
#footer_text {
  text-align: center;
  color: #666;
  margin-top: 30px;
}

/* Input container styling */
#input_container {
  display: flex;
  justify-content: center;
  align-items: center;
  max-width: 600px;
  margin: 0 auto;
}

/* User text input */
#user_input {
  flex: 1;
  border: 1px solid #ccc;
  border-right: none;
  border-radius: 4px 0 0 4px;
  padding: 8px;
  font-size: 1rem;
  outline: none;
}

/* Send button to the right of the textbox */
#send_button {
  border: 1px solid #ccc;
  border-left: none;
  border-radius: 0 4px 4px 0;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 1rem;
  background-color: #ccc; /* default grey */
  color: #333;
  transition: background-color 0.2s, color 0.2s;
}

/* Dynamic button color if user_input has text */
#user_input:not(:placeholder-shown) + button#send_button {
  background-color: #fff;
  color: #0b3d78;
  border-color: #0b3d78;
}
#user_input:not(:placeholder-shown) + button#send_button:hover {
  background-color: #0b3d78;
  color: #fff;
}

/* The floating feedback widget in the lower-left corner of the chatbot box */
#feedback_floating_left {
  position: absolute;
  bottom: 20px;
  left: 20px;
  display: flex;
  flex-direction: row;
  gap: 1rem;
  z-index: 9999; /* On top of other elements */
}

/* Style for feedback widget buttons */
#feedback_floating_left .feedback-btn {
  font-size: 1.3rem;
  border: none;
  background-color: #fff;
  cursor: pointer;
  box-shadow: 0 1px 4px rgba(0,0,0,0.2);
  border-radius: 8px;
  padding: 0.25rem 0.5rem;
  transition: background-color 0.2s;
}
#feedback_floating_left .feedback-btn:hover {
  background-color: #f0f0f0;
}

/* Hide or style the feedback status message if desired */
#feedback_status {
  display: none;
}
"""


# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------
async def query_api(conversation):
    """
    Sends the entire conversation array to the FastAPI endpoint.
    The server expects a JSON payload of the form:
      { "messages": [ [user_msg, assistant_msg], [...], ... ] }
    """
    try:
        response = requests.post(API_URL, json={"messages": conversation})
        data = response.json()
        return data.get("answer", "No response found.")
    except Exception as e:
        return f"Error contacting API\nResponse: {response}\nError: {e}"


async def send_vote_feedback(vote_type, conversation_history):
    """
    Sends a simple 'thumbs up' or 'thumbs down' vote to the FastAPI /feedback endpoint.
    """
    payload = {"feedback": vote_type, "conversation": conversation_history}
    try:
        r = requests.post(FEEDBACK_URL, json=payload)
        return (
            "Thank you for your feedback!"
            if r.status_code == 200
            else f"Error: {r.status_code}"
        )
    except Exception as e:
        return f"Error submitting feedback: {e}"


async def user_submit(user_message, history):
    """
    Adds the user's message to the conversation history and clears the input.
    Each entry in 'history' is [user_msg, assistant_msg].
    For the new user message, assistant_msg is None (waiting for the bot).
    """
    if not user_message.strip():
        return "", history
    new_history = history + [{"role": "user", "content": user_message}]
    return "", new_history


async def bot_reply(history):
    """
    The last user message is at history[-1][0].
    We pass the entire history to the server for context.
    The server returns an answer, which we append as the assistant's response.
    """
    bot_response = await query_api(history)
    # Append assistant reply
    return history + [{"role": "assistant", "content": bot_response}]


# ------------------------------------------------------------------
# BUILD THE GRADIO INTERFACE
# ------------------------------------------------------------------
with gr.Blocks(title="Maui Building Code Assistant", css=CUSTOM_CSS) as demo:
    # Header
    gr.Markdown("# Maui Building Code Assistant", elem_id="top_banner")

    # Store conversation state
    conversation_history = gr.State([])

    # Main chatbot display
    chatbot = gr.Chatbot(
        label="Conversation", elem_id="chatbot_box", height=400, type="messages"
    )

    # Row with user textbox + send button
    with gr.Row(elem_id="input_container"):
        user_input = gr.Textbox(
            show_label=False,
            placeholder="Ask your question here...",
            container=False,
            elem_id="user_input",
            lines=2,  # allow multiple lines
        )
        submit_btn = gr.Button(
            "↑",
            variant="primary",
            elem_id="send_button",
        )
        trash_btn = gr.Button("🗑️", elem_id="trash_button")

    # Chain user input -> update state -> bot reply -> update chat display
    submit_btn.click(
        fn=user_submit,
        inputs=[user_input, conversation_history],
        outputs=[user_input, conversation_history],
    ).then(
        fn=bot_reply,
        inputs=[conversation_history],
        outputs=[conversation_history],
    ).then(
        fn=lambda history: history,
        inputs=[conversation_history],
        outputs=[chatbot],
    )

    user_input.submit(
        fn=user_submit,
        inputs=[user_input, conversation_history],
        outputs=[user_input, conversation_history],
    ).then(
        fn=bot_reply,
        inputs=[conversation_history],
        outputs=[conversation_history],
    ).then(
        fn=lambda history: history,
        inputs=[conversation_history],
        outputs=[chatbot],
    )

    trash_btn.click(
        fn=clear_history,
        inputs=[],  # no inputs
        outputs=[conversation_history, chatbot],
    )

    # Example feedback widget (currently commented out)
    # with gr.Group(elem_id="feedback_floating_left"):
    #     thumbs_up = gr.Button("👍", elem_classes="feedback-btn")
    #     thumbs_down = gr.Button("👎", elem_classes="feedback-btn")
    #     feedback_status = gr.Textbox(
    #         label="Feedback Status", interactive=False, elem_id="feedback_status"
    #     )
    #
    #     thumbs_up.click(
    #         fn=lambda hist: await send_vote_feedback("up", hist),
    #         inputs=conversation_history,
    #         outputs=feedback_status,
    #     )
    #     thumbs_down.click(
    #         fn=lambda hist: await send_vote_feedback("down", hist),
    #         inputs=conversation_history,
    #         outputs=feedback_status,
    #     )

    # Footer
    gr.Markdown(
        "#### Powered by Gradio + FastAPI + OpenAI + Pinecone", elem_id="footer_text"
    )
    gr.HTML(
        """<script>
        (function() {
          const wrapper = document.getElementById("user_input");
          const textarea = wrapper.querySelector("textarea");
          const sendBtn = document.getElementById("send_button");
          textarea.addEventListener("keydown", function(e) {
            if (e.key === "Enter" && !e.metaKey) {
              const start = this.selectionStart;
              const end = this.selectionEnd;
              this.value = this.value.slice(0, start) + "\\n" + this.value.slice(end);
              this.selectionStart = this.selectionEnd = start + 1;
              e.preventDefault();
            } else if (e.key === "Enter" && e.metaKey) {
              sendBtn.click();
              e.preventDefault();
            }
          });
        })();
        </script>"""
    )

# Run Gradio
if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7861, share=True)

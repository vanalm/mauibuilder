import time
import gradio as gr
import requests

# ------------------------------------------------------------------
# CONFIGURATION
# ------------------------------------------------------------------
API_URL = "http://127.0.0.1:8000/api"  # FastAPI endpoint
FEEDBACK_URL = "http://127.0.0.1:8000/feedback"  # Optional feedback endpoint


def clear_history():
    """Reset both the conversation state and the displayed chat."""
    return [], []


def display_history(history):
    """
    Convert a list of {role, content} dicts into the [[user, assistant], ...]
    format expected by gr.Chatbot.
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
  position: relative;
  resize: both;   /* allow both horizontal and vertical resize */
  overflow: auto;
}

/* Enlarge user and assistant avatars */
#chatbot_box .chatbot-message-user .avatar img,
#chatbot_box .chatbot-message-assistant .avatar img {
  width: 48px !important;
  height: 48px !important;
}

/* Make example row match the same max-width as the chatbot */
#example_row {
  max-width: 600px;
  margin: 0 auto;
  margin-top: 16px;
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
  flex-direction: column;
  gap: 12px;
  max-width: 600px;
  margin: 20px auto 0;
  align-items: stretch;
}

/* Make input box span full width */
#user_input textarea {
  width: 100% !important;
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

#send_button {
  width: 80px !important;
  height: 40px !important;
  border-radius: 20px !important;
  align-self: center !important;
  background-color: #007aff !important;
  color: white !important;
  border: none !important;
  box-shadow: 0 1px 3px rgba(0,0,0,0.2) !important;
  font-size: 1rem !important;
}
#send_button:hover {
  background-color: #005bb5 !important;
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

/* Loading spinner for the input area */
#input_spinner {
  display: none;
  width: 32px;
  height: 32px;
  border: 4px solid #ccc;
  border-top: 4px solid #007aff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto;
}

/* Spin animation keyframes */
@keyframes spin {
  0%   { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
"""


# ------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------
async def query_api(conversation):
    """
    Sends the entire conversation array to the FastAPI endpoint.
    Expects a JSON payload: { "messages": [ {role, content}, ... ] }
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
    If the user typed something valid, add it to conversation as role=user.
    Return updated history, with the user_input box cleared.
    """
    if not user_message.strip():
        return "", history  # do nothing if whitespace only
    new_history = history + [{"role": "user", "content": user_message}]
    return "", new_history


async def bot_reply(history):
    """
    Calls the server to get the assistant's response, appends it to conversation.
    """
    import time

    time.sleep(2)
    if not history or history[-1]["role"] != "user":
        return history  # no new user message
    bot_response = await query_api(history)
    return history + [{"role": "assistant", "content": bot_response}]


def delayed_hide_spinner(_):
    """
    Final function in the chain that returns JS to hide the spinner
    AFTER a short delay. This solves timing issues with immediate partial replies.
    """
    # Wait half a second to make sure the assistant message is fully rendered
    # before hiding spinner
    return """<script>
          console.log("delayed_hide_spinner() called - about to wait 500 ms");
          setTimeout(() => {

            document.getElementById('input_spinner').style.display = 'none';
        }, 500);
          console.log("500 ms up...");
    </script>"""


# ------------------------------------------------------------------
# BUILD THE GRADIO INTERFACE
# ------------------------------------------------------------------
with gr.Blocks(title="Maui Building Code Assistant", css=CUSTOM_CSS) as demo:
    # Header
    gr.Markdown("# Maui Building Code Assistant", elem_id="top_banner")

    # Conversation state
    conversation_history = gr.State([])

    # Main chatbot
    chatbot = gr.Chatbot(
        label="Conversation",
        elem_id="chatbot_box",
        height=400,
        type="messages",
        feedback_options=["thumbs_up", "thumbs_down"],
        show_copy_button=True,
        show_share_button=True,
        resizable=True,
        allow_file_downloads=True,
        avatar_images=(
            "server/assets/user_avatar.png",
            "server/assets/assistant_avatar.png",
        ),
    )

    # Input row: text + send button
    with gr.Row(elem_id="input_container"):
        user_input = gr.Textbox(
            show_label=False,
            placeholder="Ask your question here...",
            container=False,
            elem_id="user_input",
            lines=2,
        )
        submit_btn = gr.Button(
            "↑",
            variant="primary",
            scale=1,
            elem_id="send_button",
        )

    # Spinner below
    spinner_html = gr.HTML(
        "<div id='input_spinner'></div>", elem_id="spinner_container", visible=True
    )

    # Example prompts
    with gr.Row(elem_id="example_row"):
        examples = gr.Examples(
            examples=[
                "What is the maximum height for a building in Maui?",
                "Can I build a fence without a permit?",
                "What are the requirements for a swimming pool?",
                "How do I apply for a building permit?",
                "What is the process for getting a variance?",
                "Are there any restrictions on building materials?",
                "What is the setback requirement for a new home?",
                "Can I build a deck without a permit?",
                "What are the zoning regulations for my property?",
                "How do I find a licensed contractor in Maui?",
                "What is the process for getting a certificate of occupancy?",
                "Are there any special requirements for building near the ocean?",
                "What are the fire safety requirements for new construction?",
                "Can I build a guest house on my property?",
                "What are the requirements for installing solar panels?",
            ],
            inputs=[user_input],
            label="Try one of these…",
        )

    # 1) On Send button click:
    submit_chain = (
        submit_btn.click(
            fn=user_submit,
            inputs=[user_input, conversation_history],
            outputs=[user_input, conversation_history],
        )
        .then(
            fn=lambda h: h,
            inputs=[conversation_history],
            outputs=[chatbot],
        )
        .then(
            fn=bot_reply,
            inputs=[conversation_history],
            outputs=[conversation_history],
            show_progress=True,
        )
        .then(
            fn=lambda h: h,
            inputs=[conversation_history],
            outputs=[chatbot],
        )
        .then(
            fn=delayed_hide_spinner,
            inputs=[conversation_history],
            outputs=[spinner_html],
        )
    )

    # 2) On Enter in Textbox:
    user_input.submit(
        fn=user_submit,
        inputs=[user_input, conversation_history],
        outputs=[user_input, conversation_history],
    ).then(
        fn=lambda h: h,
        inputs=[conversation_history],
        outputs=[chatbot],
    ).then(
        fn=bot_reply,
        inputs=[conversation_history],
        outputs=[conversation_history],
        show_progress=True,
    ).then(
        fn=lambda h: h,
        inputs=[conversation_history],
        outputs=[chatbot],
    ).then(
        fn=delayed_hide_spinner,
        inputs=[conversation_history],
        outputs=[spinner_html],
    )

    # Footer
    gr.Markdown(
        "#### Powered by Gradio + FastAPI + OpenAI + Pinecone", elem_id="footer_text"
    )

    # JS snippet for enabling/disabling send button & showing spinner
    gr.HTML(
        """<script>
document.addEventListener("DOMContentLoaded", () => {
  const sendBtn = document.getElementById("send_button");
  // Initially disable the send button
  sendBtn.disabled = true;

  const spinner = document.getElementById("input_spinner");
  const userInput = document.querySelector("#user_input textarea");

  // Enable/disable send button based on non-empty input
  function updateSendButton() {
    sendBtn.disabled = (userInput.value.trim() === "");
  }
  userInput.addEventListener("input", updateSendButton);
  updateSendButton();

  // Show spinner if user typed something
  function showSpinner() {
    console.log("showSpinner() called");
    spinner.style.display = 'block';
  }

  // Send button: show spinner if input isn't empty
  sendBtn.addEventListener("click", () => {
    if (userInput.value.trim() !== "") {
      console.log("Send button clicked");
      console.log("Calling showSpinner()");
      showSpinner();
    }
  });

  // Ctrl+Enter also triggers the chain
  userInput.addEventListener("keydown", (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
      if (userInput.value.trim() !== "") {
        console.log("Ctrl+Enter pressed");
        console.log("Calling showSpinner()");
        showSpinner();
      }
    }
  });
});
</script>"""
    )

# Run Gradio
if __name__ == "__main__":
    # demo.launch(server_name="0.0.0.0", server_port=7861, share=True)
    demo.launch(server_name="127.0.0.1", server_port=7861, share=False)

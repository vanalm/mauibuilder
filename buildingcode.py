from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.network.urlrequest import UrlRequest
from kivy.uix.scrollview import ScrollView
import json
from kivy.metrics import dp
from kivy.graphics import Color, Rectangle
from kivy.core.window import Window, Keyboard  # Import Window and Keyboard


class CustomTextInput(TextInput):
    def __init__(self, submit_callback, **kwargs):
        super(CustomTextInput, self).__init__(**kwargs)
        self.submit_callback = submit_callback
        self.multiline = True  # Ensure that TextInput is multiline
        self.bind(on_keyboard=self.on_keyboard_event)

    def on_keyboard_event(self, instance, keyboard, keycode, text, modifiers):
        # Check for command + enter (keycode 13 is 'enter')
        if keycode == 13 and "meta" in modifiers:
            self.submit_callback()
            return True  # Return True to indicate that the key event was consumed
        return False  # Return False to let the event propagate if not handled


class QueryInterface(BoxLayout):
    def __init__(self, **kwargs):
        super(QueryInterface, self).__init__(**kwargs)
        self.orientation = "vertical"
        self.padding = dp(10)
        self.spacing = dp(10)

        self.scroll_view = ScrollView(size_hint=(1, None), size=(0, dp(200)))
        with self.scroll_view.canvas.before:
            Color(1, 1, 1, 1)
            self.rect = Rectangle(pos=self.scroll_view.pos, size=self.scroll_view.size)
        self.scroll_view.bind(
            size=lambda *args: setattr(self.rect, "size", self.scroll_view.size)
        )
        self.scroll_view.bind(
            pos=lambda *args: setattr(self.rect, "pos", self.scroll_view.pos)
        )

        self.response_label = Label(
            text="Your response will appear here",
            color=(0, 0, 0, 1),
            size_hint_y=None,
            markup=True,
        )
        self.response_label.bind(
            width=lambda *x: self.response_label.setter("text_size")(
                self.response_label, (self.response_label.width, None)
            )
        )
        self.response_label.bind(texture_size=self.response_label.setter("size"))

        self.scroll_view.add_widget(self.response_label)
        self.add_widget(self.scroll_view)

        # Use the custom text input which listens for cmd+enter
        self.query_input = CustomTextInput(
            submit_callback=self.submit_query,
            hint_text="What are we working on?",
            size_hint_y=None,
            height=dp(150),
            background_color=(1, 1, 1, 1),
        )
        self.query_input.bind(minimum_height=self.query_input.setter("height"))
        self.add_widget(self.query_input)

        self.submit_button = Button(text="Submit", size_hint_y=None, height=dp(50))
        self.submit_button.bind(on_press=self.submit_query)
        self.add_widget(self.submit_button)

    def submit_query(self, *args):
        query = self.query_input.text.strip()
        if query:
            self.response_label.text = "Sending query..."
            req = UrlRequest(
                "http://127.0.0.1:5000/api",
                on_success=self.display_response,
                req_body=json.dumps({"query": query}),
                req_headers={
                    "Content-type": "application/json",
                    "Accept": "text/plain",
                },
            )

    def display_response(self, req, result):
        self.response_label.text = f"Response: {result['answer']}"


class QueryApp(App):
    def build(self):
        return QueryInterface()


if __name__ == "__main__":
    QueryApp().run()

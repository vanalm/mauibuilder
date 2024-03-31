from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Rectangle, Ellipse, Color

class MyWidget(Widget):
    def __init__(self, **kwargs):
        super(MyWidget, self).__init__(**kwargs)
        with self.canvas:
            Color(1, 0, 0, 1)  # Red color
            self.rect = Rectangle(pos=(100, 400), size=(500, 100))
            Color(0, 1, 0, 1)  # Green color
            self.ellipse = Ellipse(pos=(400, 100), size=(200, 100))

class MyApp(App):
    def build(self):
        return MyWidget()

if __name__ == '__main__':
    MyApp().run()

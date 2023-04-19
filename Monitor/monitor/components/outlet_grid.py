from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.properties import DictProperty
from kivy.clock import Clock


class OutletGrid(GridLayout):
    outlets = DictProperty({})

    def __init__(self, **kwargs):
        super(OutletGrid, self).__init__(**kwargs)

    def get_wattage(self, outlet):
        return self.outlets[outlet]['wattage']

    def on_outlets(self, instance, value):
        Clock.schedule_once(self.update_buttons)
        
    def update_buttons(self, *args, **kwargs):
        self.clear_widgets()
        for outlet in self.outlets:
            new_button = Button(text=f'{outlet}\n{self.get_wattage(outlet)} W', on_press=self.callback)
            self.add_widget(new_button)

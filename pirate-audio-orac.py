from ptoled import PTOLEDDisplay
from ptbuttons import PTUpButton, PTDownButton, PTCancelButton, PTSelectButton
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from pythonosc.udp_client import SimpleUDPClient

from functools import partial
import json
import netifaces as ni
import os
import random
import signal
import sys

class Logger():
    def log(self, source, log_text):
        print("[%s] %s" % (source, log_text))

logger = Logger()
def get_logger():
    return logger

class Rack:
    rack_slot_order = None
    rack_module_map = None
    current_preset = None
    rack_resource_list = None
    rack_id = None
    midi_learn = False
    modulation_learn = False

    def __init__(self):
        self.reset()

    def reset(self):
        self.rack_slot_order = "a1 a2 a3 b1 b2 b3 b4 c1 c2 c3 p1 p2 m1 m2 m3 s1 s2".split(" ")
        self.rack_module_map = {}
        self.rack_resource_list = { "module": [], "preset": [] }

    def set_id(self, rack_id):
        self.rack_id = rack_id

    def set_module(self, slot_id, module):
        self.rack_module_map[slot_id] = module

    def set_current_preset(self, preset):
        self.current_preset = preset

    def set_midi_learn(self, midi_learn):
        self.midi_learn = midi_learn

    def set_modulation_learn(self, modulation_learn):
        self.modulation_learn = modulation_learn

    def add_resource_item(self, res_type, res):
        if res_type == "moduleorder":
            self.rack_slot_order = res.split(" ")
        elif res_type in self.rack_resource_list and res not in self.rack_resource_list[res_type]:
            self.rack_resource_list[res_type].append(res)

    def get_id(self):
        return self.rack_id

    def get_resource_list(self, res_type):
        if res_type in self.rack_resource_list:
            return self.rack_resource_list[res_type]
        return None

    def get_slot_len(self):
        return len(self.rack_slot_order)

    def get_slot_id(self, slot_index):
        if slot_index < len(self.rack_slot_order):
            return self.rack_slot_order[slot_index]
        return None

    def get_slot_module(self, slot_id):
        if slot_id in self.rack_module_map:
            return self.rack_module_map[slot_id]
        return None

    def get_current_preset(self):
        return self.current_preset

    def get_midi_learn(self):
        return self.midi_learn

    def get_modulation_learn(self):
        return self.modulation_learn

    def to_obj(self):
        return {
                "slot_order": self.rack_slot_order,
                "module_map": { k: v.to_obj() for k, v in self.rack_module_map.items() }
                }

class Module:
    # /Kontrol/module ssss "127.0.0.1:6001" "a1" "Brds Mono" "synth/brdsmono"
    module_label = ""
    module_id = ""
    module_page_list = None
    module_param_map = None

    def __init__(self, module_label, module_id):
        self.module_label = module_label
        self.module_id = module_id
        self.module_page_list = []
        self.module_param_map = {}

    def add_page(self, page):
        self.module_page_list.append(page)

    def add_param(self, param):
        self.module_param_map[param.get_id()] = param

    def get_id(self):
        return self.module_id

    def get_label(self):
        return self.module_label
    
    def get_page_len(self):
        return len(self.module_page_list)

    def get_page(self, page_index):
        if page_index < len(self.module_page_list):
            return self.module_page_list[page_index]
        return None

    def get_param(self, param_id):
        if param_id in self.module_param_map:
            return self.module_param_map[param_id]
        return None

    def to_obj(self):
        return {
                "module_label": self.module_label,
                "module_id": self.module_id,
                "page_list": [ p.to_obj() for p in self.module_page_list ],
                "param_map": { k: v.to_obj() for k, v in self.module_param_map.items() }
                }

class ModulePage:
    # /Kontrol/page ssssssss "127.0.0.1:6001" "a1" "pg_osc" "Oscillator" "o_shape" "o_colour" "o_timbre" "o_transpose"
    page_id = ""
    page_label = ""
    page_param_order = None

    def __init__(self, page_id, page_label, page_param_order):
        self.page_id = page_id
        self.page_label = page_label
        self.page_param_order = page_param_order

    def get_id(self):
        return self.page_id

    def get_label(self):
        return self.page_label

    def get_param_len(self):
        return len(self.page_param_order)

    def get_param_id(self, page_param_index):
        if page_param_index < len(self.page_param_order):
            return self.page_param_order[page_param_index]
        return None

    def to_obj(self):
        return {
                "page_id": self.page_id,
                "page_label": self.page_label,
                "param_order": self.page_param_order
                }

PARAM_TYPE_FORMAT_STRING = {
        "pct": "%.2f%%",
        "freq": "%.0fHz",
        "time": "%.0fms",
        "pitch": "%.0fst",
        "int": "%.0f"
}

PARAM_TYPE_OFFSET_LEVEL = {
        "pct": [1, 5, 10, 20],
        "freq": [1, 10, 100, 1000],
        "time": [1, 10, 50, 100],
        "pitch": [1, 2, 4, 8],
        "bool": [1, 1, 1, 1],
        "int": [1, 2, 4, 8],
        "pan": [0.01, 0.05, 0.1, 0.2]
}

class ModuleParam:
    # /Kontrol/param sssssfff "127.0.0.1:6001" "a1" "pct" "o_colour" "Colour" 0.000000 100.000000 50.000000
    # type: pct / freq / time / pitch / int / bool / pan
    param_type = "pct"
    param_id = ""
    param_label = ""
    param_min = 0.0
    param_max = 100.0
    param_default = 50.0
    param_current = 50.0

    def __init__(self, param_type, param_id, param_label, param_range, param_default):
        self.param_type = param_type
        self.param_id = param_id
        self.param_label = param_label
        if param_type != "bool":
            self.param_min = param_range[0]
            self.param_max = param_range[1]
        else:
            self.param_min = 0.0
            self.param_max = 1.0
        self.param_default = param_default
        self.param_current = param_default
    
    def get_type(self):
        return self.param_type

    def get_id(self):
        return self.param_id

    def get_label(self):
        return self.param_label

    def get_min(self):
        return self.param_min

    def get_max(self):
        return self.param_max

    def get_default(self):
        return self.param_default

    def get_current(self):
        return self.param_current

    def get_current_str(self):
        # type: pct / freq / time / pitch / int / bool / pan
        if self.param_type == "bool":
            return "ON" if self.param_current == 1.0 else "OFF"
        elif self.param_type == "pan":
            if self.param_current == 0.5:
                return "C"
            elif self.param_current < 0.5:
                return "L %.0f" % (200 * (0.5 - self.param_current))
            else:
                return "%.0f R" % (200 * (self.param_current - 0.5))
        else:
            fmt = "(%.2f)"
            if self.param_type in PARAM_TYPE_FORMAT_STRING:
                fmt = PARAM_TYPE_FORMAT_STRING[self.param_type]
            return fmt % self.param_current

    def get_current_pct(self):
        return 100.0 * (self.param_current - self.param_min) / (self.param_max - self.param_min)

    def get_offset_delta(self, offset_level):
        return PARAM_TYPE_OFFSET_LEVEL[self.param_type][offset_level]

    def set_current(self, value):
        self.param_current = value

    def decrease_current(self, offset_level):
        self.param_current -= self.get_offset_delta(offset_level)
        if self.param_current < self.param_min:
            self.param_current = self.param_min

    def increase_current(self, offset_level):
        self.param_current += self.get_offset_delta(offset_level)
        if self.param_current > self.param_max:
            self.param_current = self.param_max

    def to_obj(self):
        return {
                "param_type": self.param_type,
                "param_id": self.param_id,
                "param_label": self.param_label,
                "param_min": self.param_min,
                "param_max": self.param_max,
                "param_default": self.param_default,
                "param_current": self.param_current
                }

rack = Rack()

def get_rack():
    return rack

def get_rack_id():
    return get_rack().get_id()

class RackViewState:
    slot_index = 0
    page_index = 0

    def reset(self):
        self.slot_index = 0
        self.page_index = 0

    def get_active_slot_id(self):
        return get_rack().get_slot_id(self.slot_index)

    def get_active_slot_module(self):
        return get_rack().get_slot_module(self.get_active_slot_id())

    def get_active_slot_module_page(self):
        if self.get_active_slot_module() is None:
            return None
        return self.get_active_slot_module().get_page(self.page_index)

    def get_active_slot_module_page_param(self, page_param_index):
        if self.get_active_slot_module_page() is None:
            return None
        param_id = self.get_active_slot_module_page().get_param_id(page_param_index)
        if param_id is None:
            return None
        return self.get_active_slot_module().get_param(param_id)

rack_view_state = RackViewState()

def get_rack_view_state():
    return rack_view_state

class OscClient:
    MEC_SERVER_IP = "127.0.0.1"
    MEC_SERVER_PORT = 6000
    OSC_SERVER_IP = "127.0.0.1"
    OSC_SERVER_PORT = 9001

    dispatcher = None
    osc_server = None
    osc_client = None

    def __init__(self):
        self.init_dispatcher()
        self.osc_server = BlockingOSCUDPServer((self.OSC_SERVER_IP, self.OSC_SERVER_PORT), self.dispatcher)

        self.osc_client = SimpleUDPClient(self.MEC_SERVER_IP, self.MEC_SERVER_PORT)
        self.send_ping(0)

    def log(self, log_text):
        get_logger().log("OscClient", log_text)
        pass

    def handle_osc_publish(self, address, *args):
        # /Kontrol/publishStart i 1
        # /Kontrol/publishRackFinished s "127.0.0.1:6001"
        self.log("%s %s" % (address, str(args)))
        address_path = address.split("/")
        if address_path[-1] == "publishStart":
            #get_controller().disable_update()
            pass
        elif address_path[-1] == "publishRackFinished":
            #get_controller().enable_update()
            pass

    def handle_osc_module(self, address, *args):
        # /Kontrol/module ssss "127.0.0.1:6001" "a1" "Brds Mono" "synth/brdsmono"
        self.log("%s %s" % (address, str(args)))
        get_rack().set_module(args[1], Module(args[2], args[3]))
        get_controller().schedule_update()

    def handle_osc_page(self, address, *args):
        # /Kontrol/page ssssssss "127.0.0.1:6001" "a1" "pg_osc" "Oscillator" "o_shape" "o_colour" "o_timbre" "o_transpose"
        self.log("%s %s" % (address, str(args)))
        get_rack().get_slot_module(args[1]).add_page(ModulePage(args[2], args[3], args[4:]))
        get_controller().schedule_update()

    def handle_osc_param(self, address, *args):
        # /Kontrol/param sssssfff "127.0.0.1:6001" "a1" "pct" "o_colour" "Colour" 0.000000 100.000000 50.000000
        # type: pct / freq / time / pitch / int / bool / pan
        self.log("%s %s" % (address, str(args)))
        get_rack().get_slot_module(args[1]).add_param(ModuleParam(args[2], args[3], args[4], args[5:-1], args[-1]))
        get_controller().schedule_update()

    def handle_osc_changed(self, address, *args):
        # /Kontrol/changed sssf "127.0.0.1:6001" "s1" "r-chout-l-pan-3" 0.000000
        self.log("%s %s" % (address, str(args)))
        get_rack().get_slot_module(args[1]).get_param(args[2]).set_current(args[3])
        get_controller().schedule_update()

    def handle_osc_loadPreset(self, address, *args):
        # /Kontrol/loadPreset ss "127.0.0.1:6001" "demo2"
        self.log("%s %s" % (address, str(args)))
        get_rack().set_current_preset(args[1])
        get_controller().schedule_update()

    def handle_osc_loadModule(self, address, *args):
        # /Kontrol/loadModule sss "127.0.0.1:6001" "p2" "utility/empty"
        self.log("%s %s" % (address, str(args)))
        get_controller().schedule_update()

    def handle_osc_resource(self, address, *args):
        # /Kontrol/resource sss "127.0.0.1:6001" "module" "utility/t3dosc"
        # /Kontrol/resource sss "127.0.0.1:6001" "preset" "Init"
        # /Kontrol/resource sss "127.0.0.1:6001" "moduleorder" "a1 a2 a3 b1 b2 b3 b4 c1 c2 c3 p1 p2 m1 m2 m3 s1 s2"
        self.log("%s %s" % (address, str(args)))
        get_rack().add_resource_item(args[1], args[2])
        get_controller().schedule_update()

    def handle_osc_midiLearn(self, address, *args):
        # /Kontrol/midiLearn T/F
        self.log("%s %s" % (address, str(args)))
        get_rack().set_midi_learn(args[0])

    def handle_osc_modLearn(self, address, *args):
        # /Kontrol/modLearn T/F
        self.log("%s %s" % (address, str(args)))
        get_rack().set_modulation_learn(args[0])

    def handle_osc_rack(self, address, *args):
        # /Kontrol/rack ssi "127.0.0.1:6001" "127.0.0.1" 6001
        self.log("%s %s" % (address, str(args)))
        get_rack().set_id(args[0])
        get_rack().reset()
        get_rack_view_state().reset()
        get_view_manager().reset_all_view_state()

    def handle_osc_ping(self, address, *args):
        # /Kontrol/ping ii 6000 0
        self.log("%s %s" % (address, str(args)))
        self.send_ping(5)

    def handle_osc_default(self, address, *args):
        self.log("osc_default: %s %s" % (address, str(args)))

    def init_dispatcher(self):
        self.dispatcher = Dispatcher()
        self.dispatcher.map("/Kontrol/publish*", self.handle_osc_publish)
        self.dispatcher.map("/Kontrol/module", self.handle_osc_module)
        self.dispatcher.map("/Kontrol/page", self.handle_osc_page)
        self.dispatcher.map("/Kontrol/param", self.handle_osc_param)
        self.dispatcher.map("/Kontrol/changed", self.handle_osc_changed)
        self.dispatcher.map("/Kontrol/loadPreset", self.handle_osc_loadPreset)
        self.dispatcher.map("/Kontrol/loadModule", self.handle_osc_loadModule)
        self.dispatcher.map("/Kontrol/resource", self.handle_osc_resource)
        self.dispatcher.map("/Kontrol/midiLearn", self.handle_osc_midiLearn)
        self.dispatcher.map("/Kontrol/modLearn", self.handle_osc_modLearn)
        self.dispatcher.map("/Kontrol/rack", self.handle_osc_rack)
        self.dispatcher.map("/Kontrol/ping", self.handle_osc_ping)
        self.dispatcher.set_default_handler(self.handle_osc_default)

    def start_loop(self):
        self.osc_server.serve_forever()

    def send_ping(self, keepalive_seconds):
        # /Kontrol/ping ii 6000 0
        # keepalive_seconds 0 means get current metadata, should be sent only when connection started
        self.osc_client.send_message("/Kontrol/ping", [self.OSC_SERVER_PORT, keepalive_seconds])

    def send_changed(self, slot_id, param_id, value):
        # /Kontrol/changed sssf "127.0.0.1:6001" "s1" "r-chout-l-pan-3" 0.000000
        self.log("send_changed: %s %s %s %f" % (get_rack_id(), slot_id, param_id, value))
        self.osc_client.send_message("/Kontrol/changed", [get_rack_id(), slot_id, param_id, value])

    def send_loadModule(self, slot_id, module_id):
        self.log("send_loadModule: %s %s %s" % (get_rack_id(), slot_id, module_id))
        self.osc_client.send_message("/Kontrol/loadModule", [get_rack_id(), slot_id, module_id])
       
    def send_loadPreset(self, preset_name):
        self.log("send_loadPreset: %s %s" % (get_rack_id(), preset_name))
        self.osc_client.send_message("/Kontrol/loadPreset", [get_rack_id(), preset_name])
        get_rack().set_current_preset(preset_name) # MEC_BUG

    def send_savePreset(self, preset_name):
        self.log("send_savePreset: %s %s" % (get_rack_id(), preset_name))
        self.osc_client.send_message("/Kontrol/savePreset", [get_rack_id(), preset_name])
        get_rack().set_current_preset(preset_name) # MEC_BUG

    def send_midiLearn(self, mode):
        self.log("send_midiLearn: %s" % str(bool(mode)))
        self.osc_client.send_message("/Kontrol/midiLearn", [bool(mode)])
        get_rack().set_midi_learn(bool(mode)) # MEC_BUG

    def send_modulationLearn(self, mode):
        self.log("send_modulationLearn: %s" % str(bool(mode)))
        self.osc_client.send_message("/Kontrol/modulationLearn", [bool(mode)])
        get_rack().set_mod_learn(bool(mode)) # MEC_BUG

osc_client = OscClient()

def get_osc_client():
    return osc_client

class Rect:
    x = 0
    y = 0
    w = 0
    h = 0

    def __init__(self, x, y, w, h):
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def to_tuple(self):
        return (self.x, self.y, self.x + self.w, self.y + self.h)

class Color:
    r = 0
    g = 0
    b = 0

    def __init__(self, r, g, b):
        self.r = r
        self.g = g
        self.b = b

    def to_tuple(self):
        return (self.r, self.g, self.b)

    def get_inversion(self):
        return Color(255 - self.r, 255 - self.g, 255 - self.b)

    def is_filled_for_mono(self):
        return True if (self.r + self.g + self.b) >= 128 * 3 else False

Color_BLACK = Color(0, 0, 0)
Color_WHITE = Color(255, 255, 255)
Color_RED = Color(255, 0, 0)
Color_YELLOW = Color(255, 255, 0)
Color_LIGHTGRAY = Color(192, 192, 192)
Color_GRAY = Color(128, 128, 128)
Color_DARKGRAY = Color(64, 64, 64)

def get_rand_color(max_brightness):
    return Color(
            int(random.random() * max_brightness),
            int(random.random() * max_brightness),
            int(random.random() * max_brightness)
            )

ALIGN_LEFT = 0
ALIGN_CENTER = 1
ALIGN_RIGHT = 2

class Screen:
    disp = None
    canvas = None
    font = None
    condensed_font = None
    disp_rect = None

    def __init__(self):
        self.disp = PTOLEDDisplay()
        self.disp.set_max_fps(10)
        self.disp.reset()
        self.canvas = self.disp.canvas
        self.font = "/usr/share/fonts/truetype/freefont/FreeMonoBold.ttf"
        self.condensed_font = "/usr/share/fonts/truetype/freefont/FreeMono.ttf"
        self.font_size = 10
        self.disp_rect = Rect(0, 0, 128, 64)

    def clear(self):
        self.canvas.clear()

    def get_row_count(self):
        return 6

    def get_row_height(self):
        return 8

    def get_row_rect(self, row_index):
        return Rect(0, self.get_row_height() + row_index * self.get_row_height(), self.disp_rect.w, self.get_row_height())

    def draw_text_in_rect(self, text, rect, color, alignment=ALIGN_CENTER, font=None):
        if font is None:
            font = self.font
        self.canvas.set_font(font, self.font_size)
        size_x, size_y = self.canvas.textsize(text, 0)

        if alignment == ALIGN_CENTER:
            text_x = rect.x + (rect.w - size_x) // 2
        elif alignment == ALIGN_LEFT:
            text_x = rect.x
        elif alignment == ALIGN_RIGHT:
            text_x = rect.x + (rect.w - size_x)
        text_y = rect.y + (rect.h - size_y) // 2
        self.canvas.text((text_x, text_y), text, fill=color.is_filled_for_mono())

    def draw_rect(self, rect, color):
        self.canvas.rectangle(rect.to_tuple(), fill=color.is_filled_for_mono())

    def draw_bar(self, pct, rect, fg_color, bg_color):
        self.draw_rect(rect, bg_color)
        bar_rect = Rect(rect.x, rect.y, int(rect.w * pct / 100.0), rect.h)
        self.draw_rect(bar_rect, fg_color)

    def update(self):
        self.disp.draw()

screen = Screen()

def get_screen():
    return screen

class BaseField:
    row_index = 0
    row_rect = None
    is_focused = False
    perform_hint = "--------"

    def __init__(self, row_index):
        self.row_index = row_index
        self.row_rect = get_screen().get_row_rect(self.row_index)
        self.is_focused = False

    def log(self, log_text):
        get_logger().log(self.__class__.__name__, log_text)
        pass

    def render(self):
        self.log("render")
        get_screen().draw_rect(self.row_rect, Color_BLACK)

    def draw_arrows(self):
        color = Color_DARKGRAY if self.is_focused else Color_LIGHTGRAY
        get_screen().draw_text_in_rect("<", self.row_rect, color, alignment=ALIGN_LEFT)
        get_screen().draw_text_in_rect(">", self.row_rect, color, alignment=ALIGN_RIGHT)

    def set_focused(self, is_focused):
        self.is_focused = is_focused

    def get_perform_hint(self):
        return self.perform_hint

    def perform_decrease(self, offset_level):
        pass

    def perform_increase(self, offset_level):
        pass

class ItemSelectField(BaseField):
    perform_hint = "MOVE CURSOR"
    item_select_view = None

    def __init__(self, row_index, res_select_view):
        super().__init__(row_index)
        self.item_select_view = res_select_view

    def render(self):
        get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)
        view_offset = self.item_select_view.view_offset
        item_len = self.item_select_view.get_item_len()
        text = ""
        if self.row_index < item_len - view_offset:
            text = self.item_select_view.get_item(view_offset + self.row_index)
        self.log("render item_len=%d view_offset=%d row_index=%d text=%s" % (item_len, view_offset, self.row_index, text))
        get_screen().draw_text_in_rect(text, self.row_rect, Color_BLACK if self.is_focused else Color_WHITE, font=get_screen().condensed_font)

    def select_item(self):
        self.item_select_view.item_selected(self.row_index)

    def perform_decrease(self, offset_level):
        self.select_item()

    def perform_increase(self, offset_level):
        self.select_item()

class MenuModuleField(BaseField):
    perform_hint = "SELECT MODULE"
    def render(self):
        get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)
        module_label = "Empty"
        active_slot_module = get_rack_view_state().get_active_slot_module()
        if active_slot_module is not None:
            module_label = active_slot_module.get_label()
        text_color = Color_BLACK if self.is_focused else Color_WHITE
        label_font = get_screen().condensed_font
        label_text = "Module (%s)" % get_rack_view_state().get_active_slot_id()
        get_screen().draw_text_in_rect(label_text, self.row_rect, text_color, alignment=ALIGN_LEFT, font=label_font)
        value_font = None # get_screen().condensed_font
        value_text = "[ %s ]" % module_label
        get_screen().draw_text_in_rect(value_text, self.row_rect, text_color, alignment=ALIGN_RIGHT, font=value_font)

    def on_item_selected(self, selected_item_index):
        res_type = "module"
        selected_item = get_rack().get_resource_list(res_type)[selected_item_index]
        get_osc_client().send_loadModule(get_rack_view_state().get_active_slot_id(), selected_item)
        get_view_manager().pop_modal_view()

    def open_item_select_view(self):
        current_item = None
        active_slot_module = get_rack_view_state().get_active_slot_module()
        if active_slot_module is not None:
            current_item = active_slot_module.get_id()
        if current_item is None:
            return
        item_select_view = ItemSelectView(get_rack().get_resource_list("module"), current_item, self.on_item_selected)
        get_view_manager().push_modal_view(item_select_view)

    def perform_decrease(self, offset_level):
        self.open_item_select_view()

    def perform_increase(self, offset_level):
        self.open_item_select_view()

class MenuPresetField(BaseField):
    perform_hint = "SELECT PRESET"
    item_select_view_prepend_item_list = [ "(Save Preset)", "(New Preset)" ]

    def render(self):
        get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)
        preset_name = "(N/A)"
        current_preset = get_rack().get_current_preset()
        if current_preset is not None:
            preset_name = current_preset
        text_color = Color_BLACK if self.is_focused else Color_WHITE
        font = None # get_screen().condensed_font
        label_text = "Preset"
        get_screen().draw_text_in_rect(label_text, self.row_rect, text_color, alignment=ALIGN_LEFT, font=font)
        value_text = "[ %s ]" % preset_name
        get_screen().draw_text_in_rect(value_text, self.row_rect, text_color, alignment=ALIGN_RIGHT, font=font)

    def on_item_selected(self, selected_item_index):
        if selected_item_index == -2:
            get_osc_client().send_savePreset(get_rack().get_current_preset())
        elif selected_item_index == -1:
            get_osc_client().send_savePreset("new-%d" % len(get_rack().get_resource_list("preset")))
        else:
            selected_item = get_rack().get_resource_list("preset")[selected_item_index]
            get_osc_client().send_loadPreset(selected_item)
        get_view_manager().pop_modal_view()

    def open_item_select_view(self):
        current_item = get_rack().get_current_preset()
        if current_item is None:
            return
        item_select_view = ItemSelectView(get_rack().get_resource_list("preset"), current_item, self.on_item_selected, self.item_select_view_prepend_item_list)
        get_view_manager().push_modal_view(item_select_view)

    def perform_decrease(self, offset_level):
        self.open_item_select_view()

    def perform_increase(self, offset_level):
        self.open_item_select_view()

class MenuToggleField(BaseField):
    perform_hint = "TOGGLE"
    toggle_label = ""
    value_getter = None
    value_setter = None

    def __init__(self, row_index, toggle_label, value_getter, value_setter):
        super().__init__(row_index)
        self.toggle_label = toggle_label
        self.value_getter = value_getter
        self.value_setter = value_setter

    def render(self):
        get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)
        text_color = Color_BLACK if self.is_focused else Color_WHITE
        label_text = self.toggle_label
        get_screen().draw_text_in_rect(label_text, self.row_rect, text_color, alignment=ALIGN_LEFT)
        value_text = "[%s]" % ("x" if self.value_getter() else " ")
        get_screen().draw_text_in_rect(value_text, self.row_rect, text_color, alignment=ALIGN_RIGHT)

    def toggle_option(self):
        value_to_set = not self.value_getter()
        self.value_setter(value_to_set)

    def perform_decrease(self, offset_level):
        self.toggle_option()

    def perform_increase(self, offset_level):
        self.toggle_option()


class MenuSaveSettingsField(BaseField):
    perform_hint = "EXECUTE"
    show_saved = False

    def render(self):
        get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)
        text = "SAVED!" if self.show_saved else "[ Save Settings ]"
        get_screen().draw_text_in_rect(text, self.row_rect, Color_BLACK if self.is_focused else Color_WHITE)

    def restore_field(self):
        self.show_saved = False

    def perform_save_settings(self):
        self.show_saved = True
        get_controller().set_update_callback(self.restore_field)

    def perform_decrease(self, offset_level):
        self.perform_save_settings()

    def perform_increase(self, offset_level):
        self.perform_save_settings()

class DeviceShutdownField(BaseField):
    perform_hint = "EXECUTE"
    show_confirm = False

    def render(self):
        # FIXME(wangpy): place unset of show_confirm to a better place
        if not self.is_focused:
            self.show_confirm = False
        get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)
        text = "PRESS B TO CONFIRM" if self.show_confirm else "[ Shutdown ]"
        get_screen().draw_text_in_rect(text, self.row_rect, Color_BLACK if self.is_focused else Color_WHITE)

    def confirm_shutdown(self, is_decrease_button_pressed):
        self.log("confirm_shutdown show_confirm=%d decrease_pressed=%d" % (self.show_confirm, is_decrease_button_pressed))
        if self.show_confirm:
            if is_decrease_button_pressed:
                os.system("/usr/bin/sudo /usr/sbin/shutdown -h now")
            else:
                self.show_confirm = False
        else:
            self.show_confirm = True

    def perform_decrease(self, offset_level):
        self.confirm_shutdown(True)

    def perform_increase(self, offset_level):
        self.confirm_shutdown(False)

class DeviceNetworkIpField(BaseField):
    interface_id = None

    def __init__(self, row_index, interface_id):
        super().__init__(row_index)
        self.interface_id = interface_id

    def render(self):
        label = "%s IP:" % self.interface_id
        network_ip = "N/A"
        network_interface = ni.ifaddresses(self.interface_id)
        if network_interface is not None and ni.AF_INET in network_interface:
            network_ip = network_interface[ni.AF_INET][0]['addr']

        bg_color = Color_WHITE if self.is_focused else Color_BLACK
        get_screen().draw_rect(self.row_rect, bg_color)

        text_color = bg_color.get_inversion()
        font = get_screen().condensed_font
        get_screen().draw_text_in_rect(label, self.row_rect, text_color, alignment=ALIGN_LEFT, font=font)
        get_screen().draw_text_in_rect(network_ip, self.row_rect, text_color, alignment=ALIGN_RIGHT, font=font)


class StaticTextField(BaseField):
    center_text = None
    left_text = None
    right_text = None
    text_color = None
    bg_color = None
    font = None
    is_rand_color = False

    def __init__(self, row_index, center_text,
            left_text=None, right_text=None, text_color=None, bg_color=None, font=None, is_rand_color=False):
        super().__init__(row_index)
        self.center_text = center_text
        self.left_text = left_text
        self.right_text = right_text
        self.text_color = text_color
        self.bg_color = bg_color
        self.font = font
        self.is_rand_color = is_rand_color

    def render(self):
        bg_color = Color_WHITE if self.is_focused else Color_BLACK
        if self.is_rand_color:
            bg_color = get_rand_color(64)
        if self.bg_color is not None:
            bg_color = self.bg_color
        get_screen().draw_rect(self.row_rect, bg_color)

        text_color = bg_color.get_inversion()
        if self.text_color is not None:
            text_color = self.text_color
        font = get_screen().font
        if self.font is not None:
            font = self.font
        center_text = self.center_text
        if callable(center_text):
            center_text = self.center_text()
        get_screen().draw_text_in_rect(center_text, self.row_rect, text_color, font=font)

        if self.left_text is not None:
            get_screen().draw_text_in_rect(self.left_text, self.row_rect, text_color, alignment=ALIGN_LEFT, font=font)
        if self.right_text is not None:
            get_screen().draw_text_in_rect(self.right_text, self.row_rect, text_color, alignment=ALIGN_RIGHT, font=font)

class RackSlotField(BaseField):
    perform_hint = "SWITCH SLOT"

    def __init__(self, row_index):
        super().__init__(row_index)

    def render(self):
        get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)
        slot_label = "Empty"
        slot_module = get_rack_view_state().get_active_slot_module()
        if slot_module is not None:
            slot_label = slot_module.get_label()
        text = "%s: %s" % (get_rack_view_state().get_active_slot_id(), slot_label)
        self.log("render text="+text)
        get_screen().draw_text_in_rect(text, self.row_rect, Color_BLACK if self.is_focused else Color_WHITE)
        self.draw_arrows()

    def perform_decrease(self, offset_level):
        slot_len = get_rack().get_slot_len()
        get_rack_view_state().slot_index = (get_rack_view_state().slot_index + slot_len - 1) % slot_len

    def perform_increase(self, offset_level):
        slot_len = get_rack().get_slot_len()
        get_rack_view_state().slot_index = (get_rack_view_state().slot_index + 1) % slot_len

class RackSlotPageField(BaseField):
    perform_hint = "SWITCH PAGE"
    def __init__(self, row_index):
        super().__init__(row_index)

    def render(self):
        get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)
        page_label = "-"
        active_page = get_rack_view_state().get_active_slot_module_page()
        if active_page is not None:
            page_label = active_page.get_label()
        text = page_label
        self.log("render module=%s text=%s" % (get_rack_view_state().get_active_slot_id(), text))
        get_screen().draw_text_in_rect(text, self.row_rect, Color_BLACK if self.is_focused else Color_WHITE)
        self.draw_arrows()

    def perform_decrease(self, offset_level):
        page_len = get_rack_view_state().get_active_slot_module().get_page_len()
        get_rack_view_state().page_index = (get_rack_view_state().page_index + page_len - 1) % page_len

    def perform_increase(self, offset_level):
        page_len = get_rack_view_state().get_active_slot_module().get_page_len()
        get_rack_view_state().page_index = (get_rack_view_state().page_index + 1) % page_len

class RackSlotPageParamField(BaseField):
    perform_hint = "TWEAK"
    page_param_index = 0

    def __init__(self, row_index, page_param_index):
        super().__init__(row_index)
        self.page_param_index = page_param_index

    def render(self):
        module_param = get_rack_view_state().get_active_slot_module_page_param(self.page_param_index)
        if module_param is not None:
            fg_color = Color_YELLOW if self.is_focused else Color_RED
            bg_color = Color_LIGHTGRAY if self.is_focused else Color_BLACK
            get_screen().draw_bar(module_param.get_current_pct(), self.row_rect, fg_color, bg_color)
            label = module_param.get_label()
            value = module_param.get_current_str()
            self.log("render label=%s, value=%s" % (label, value))
            color = Color_BLACK if self.is_focused else Color_WHITE
            get_screen().draw_text_in_rect("%s" % label, self.row_rect, color, alignment=ALIGN_LEFT)
            get_screen().draw_text_in_rect("%s" % value, self.row_rect, color, alignment=ALIGN_RIGHT)
        else:
            self.log("render None")
            get_screen().draw_rect(self.row_rect, Color_WHITE if self.is_focused else Color_BLACK)

    def perform_decrease(self, offset_level):
        module_param = get_rack_view_state().get_active_slot_module_page_param(self.page_param_index)
        if module_param is not None:
            module_param.decrease_current(offset_level)
            slot_id = get_rack_view_state().get_active_slot_id()
            get_osc_client().send_changed(slot_id, module_param.get_id(), module_param.get_current())

    def perform_increase(self, offset_level):
        module_param = get_rack_view_state().get_active_slot_module_page_param(self.page_param_index)
        if module_param is not None:
            module_param.increase_current(offset_level)
            slot_id = get_rack_view_state().get_active_slot_id()
            get_osc_client().send_changed(slot_id, module_param.get_id(), module_param.get_current())

class BaseView:
    field_list = None
    active_field_index = 0
    header_field = None
    footer_field = None
    header_text = "MOVE (^+v: MENU)"

    def __init__(self):
        self.field_list = []
        for i in range(get_screen().get_row_count()):
            self.field_list.append(self.create_field_for_row(i))
        self.field_list[self.active_field_index].set_focused(True)
        self.header_field = StaticTextField(-1, self.get_header_text, "^", "x", font=get_screen().condensed_font, is_rand_color=True)
        self.footer_field = StaticTextField(6, self.get_footer_text, "v", "o", font=get_screen().condensed_font, is_rand_color=True)

    def reset_view_state(self):
        self.set_active_field_index(0)

    def log(self, log_text):
        get_logger().log(self.__class__.__name__, log_text)

    def create_field_for_row(self, row_index):
        return BaseField(row_index)

    def get_header_text(self):
        return self.header_text

    def get_footer_text(self):
        return self.get_active_field().get_perform_hint()

    def get_row_count(self):
        return get_screen().get_row_count()

    def get_row_field(self, row_index):
        if row_index < self.get_row_count():
            return self.field_list[row_index]
        return None

    def get_active_field(self):
        return self.field_list[self.active_field_index]

    def set_active_field_index(self, active_field_index):
        self.get_active_field().set_focused(False)
        self.active_field_index = active_field_index
        self.get_active_field().set_focused(True)

    def render(self):
        self.log("render")
        get_screen().clear()
        for i in range(get_screen().get_row_count()):
            self.field_list[i].render()
        self.render_header_and_footer()
        get_screen().update()

    def render_header_and_footer(self):
        self.header_field.render()
        self.footer_field.render()

    def move_cursor_to_previous(self):
        self.active_field_index = (self.active_field_index + self.get_row_count() - 1) % self.get_row_count()

    def move_cursor_to_next(self):
        self.active_field_index = (self.active_field_index + 1) % self.get_row_count()

    def perform_previous(self):
        self.get_active_field().set_focused(False)
        self.move_cursor_to_previous()
        self.get_active_field().set_focused(True)

    def perform_next(self):
        self.get_active_field().set_focused(False)
        self.move_cursor_to_next()
        self.get_active_field().set_focused(True)

    def perform_decrease(self, offset_level=0):
        self.get_active_field().perform_decrease(offset_level)

    def perform_increase(self, offset_level=0):
        self.get_active_field().perform_increase(offset_level)

class RackSlotPageParamView(BaseView):
    def create_field_for_row(self, row_index):
        if row_index == 0:
            return RackSlotField(row_index)
        elif row_index == 1:
            return RackSlotPageField(row_index)
        else:
            return RackSlotPageParamField(row_index, row_index-2)

    def get_row_count(self):
        param_len = 0
        active_page = get_rack_view_state().get_active_slot_module_page()
        if active_page is not None:
            param_len = active_page.get_param_len()
        return 2 + param_len

class MenuView(BaseView):
    def create_field_for_row(self, row_index):
        if row_index == 0:
            return StaticTextField(row_index, "===== MENU =====")
        if row_index == 1:
            return MenuModuleField(row_index)
        elif row_index == 2:
            return MenuPresetField(row_index)
        elif row_index == 3:
            return MenuToggleField(row_index, "Midi Learn", get_rack().get_midi_learn, get_osc_client().send_midiLearn)
        elif row_index == 4:
            return MenuToggleField(row_index, "Mod Learn", get_rack().get_modulation_learn, get_osc_client().send_modulationLearn)
        elif row_index == 5:
            return MenuSaveSettingsField(row_index)
        else:
            return BaseField(row_index)

    def get_row_count(self):
        return 6

class DeviceView(BaseView):
    row_text = ["==== Device ====", "", "", "", "Pirate Audio ORAC Controller", "by wangpy"]

    def create_field_for_row(self, row_index):
        if row_index == 1:
            return DeviceNetworkIpField(row_index, "eth0")
        elif row_index == 2:
            return DeviceNetworkIpField(row_index, "wlan0")
        elif row_index == 3:
            return DeviceShutdownField(row_index)
        else:
            font = None if row_index == 0 else get_screen().condensed_font
            text_color = None if row_index == 0 else Color_GRAY
            return StaticTextField(row_index, self.row_text[row_index], font=font, text_color=text_color)

    def get_row_count(self):
        return 6

class ItemSelectView(BaseView):
    header_text = "SELECT (^+v: EXIT)"
    prepend_item_list = None
    item_list = None
    item_selected_callback = None
    view_offset = 0

    def __init__(self, item_list, current_item, item_selected_callback, prepend_item_list=None):
        super().__init__()
        self.item_list = item_list
        if prepend_item_list is not None:
            self.prepend_item_list = prepend_item_list
        if current_item in self.item_list:
            current_item_index = self.item_list.index(current_item)
            self.set_focused_item(current_item_index)
        self.item_selected_callback = item_selected_callback

    def create_field_for_row(self, row_index):
        return ItemSelectField(row_index, self)

    def get_row_count(self):
        item_len = self.get_item_len()
        return 6 if item_len > 6 else item_len

    def move_cursor_to_previous(self):
        if self.active_field_index > 0:
            self.active_field_index -= 1
        elif self.view_offset > 0:
            self.view_offset -= 1

    def move_cursor_to_next(self):
        row_count = self.get_row_count()
        item_len = self.get_item_len()
        if self.active_field_index < row_count - 1:
            self.active_field_index += 1
        elif self.view_offset < item_len - row_count:
            self.view_offset += 1

    def get_prepend_item_len(self):
        if self.prepend_item_list is not None:
            return len(self.prepend_item_list)
        return 0

    def get_item_len(self):
        item_len = self.get_prepend_item_len()
        if self.item_list is not None:
            item_len += len(self.item_list)
        return item_len
    
    def get_item(self, item_index):
        prepend_item_len = self.get_prepend_item_len()
        if item_index < prepend_item_len:
            return self.prepend_item_list[item_index]
        elif item_index < self.get_item_len():
            return self.item_list[item_index - prepend_item_len]
        return None

    def set_focused_item(self, item_index):
        active_field_index = item_index + self.get_prepend_item_len()
        row_count = self.get_row_count()
        if item_index >= row_count:
            active_field_index = row_count - 1
            self.view_offset = item_index - (row_count - 1)
        self.set_active_field_index(active_field_index)

    def item_selected(self, selected_row_index):
        selected_item_index = self.view_offset + selected_row_index - self.get_prepend_item_len()
        self.item_selected_callback(selected_item_index)

    def perform_previous(self):
        super().perform_decrease()

    def perform_next(self):
        super().perform_increase()

    def perform_decrease(self, offset_level=0):
        super().perform_previous()

    def perform_increase(self, offset_level=0):
        super().perform_next()

class ViewManager:
    view_list = None
    active_view_index = 0
    modal_view_stack = []

    def __init__(self):
        self.view_list = []
        self.view_list.append(RackSlotPageParamView())
        self.view_list.append(MenuView())
        self.view_list.append(DeviceView())

    def log(self, log_text):
        get_logger().log("ViewManager", log_text)

    def reset_all_view_state(self):
        for view in self.modal_view_stack:
            view.reset_view_state()
        for view in self.view_list:
            view.reset_view_state()

    def get_active_view(self):
        if self.has_active_modal_view():
            return self.modal_view_stack[-1]
        return self.view_list[self.active_view_index]

    def pop_or_toggle_active_view(self):
        if self.has_active_modal_view():
            popped_view = self.modal_view_stack.pop()
            self.log("pop modal view %s" % popped_view.__class__.__name__)
        else:
            self.active_view_index = (self.active_view_index + 1) % len(self.view_list)
            self.log("pop_or_toggle_active_view active_view_index=%d" % self.active_view_index)

    def has_active_modal_view(self):
        return len(self.modal_view_stack) > 0

    def push_modal_view(self, view):
        self.modal_view_stack.append(view)

    def pop_modal_view(self):
        if self.has_active_modal_view():
            self.pop_or_toggle_active_view()

view_manager = ViewManager()
def get_view_manager():
    return view_manager

def get_active_view():
    return get_view_manager().get_active_view()

class Controller:
    buttons = None
    BUTTONS = range(4)
    LABELS = ['^', 'v', 'x', 'o']
    pressed_button = 0
    pressed_counter = 0
    disable_update_count = 0
    consume_button_up_counter = 0
    update_callback = None

    def __init__(self):
        self.buttons = [ PTUpButton(), PTDownButton(), PTCancelButton(), PTSelectButton() ]
        for i in range(len(self.buttons)):
            button = self.buttons[i]
            button.when_pressed = partial(self.handle_button, i)
            button.when_released = partial(self.handle_button, i)
        signal.signal(signal.SIGHUP, self.sigalrm_handler)
        signal.signal(signal.SIGINT, self.sigint_handler)
        signal.signal(signal.SIGTERM, self.sigint_handler)
        signal.signal(signal.SIGALRM, self.sigalrm_handler)

    def log(self, log_text):
        get_logger().log("Controller", log_text)

    def handle_button(self, pin):
        state = 0 if self.buttons[pin].is_pressed else 1
        if state == 0: # FALLING
            self.handle_button_down(pin)
        else: # RISING
            self.handle_button_up(pin)

    def handle_button_down(self, pin):
        if (self.pressed_button == 0 and pin == 1 or
            self.pressed_button == 1 and pin == 0):
            self.run_update_callback()
            get_view_manager().pop_or_toggle_active_view()
            self.update_screen()
            self.consume_button_up_counter = 2
            return

        if self.pressed_button == pin:
            self.pressed_counter += 1
        else:
            self.pressed_button = pin
            self.pressed_counter = 1
        offset_level = self.pressed_counter // 10

        label = self.LABELS[self.BUTTONS.index(pin)]
        self.log("button_down pin=%d button=%s counter=%d" % (pin, label, self.pressed_counter))
        if label == 'x':
            self.run_update_callback()
            get_active_view().perform_decrease(offset_level)
            self.update_screen()
        elif label == 'o':
            self.run_update_callback()
            get_active_view().perform_increase(offset_level)
            self.update_screen()
        else:
            return

        if self.pressed_counter > 1:
            self.set_update_timer(0.1)
        else:
            self.set_update_timer(0.3)

    def handle_button_up(self, pin):
        if self.pressed_button == pin:
            self.pressed_button = 0
            self.pressed_counter = 0
            self.set_update_timer(0)

        if self.consume_button_up_counter > 0:
            self.consume_button_up_counter -= 1
            return

        label = self.LABELS[self.BUTTONS.index(pin)]
        self.log("button_up pin=%d button=%s counter=%d" % (pin, label, self.pressed_counter))
        if label == '^':
            self.run_update_callback()
            get_active_view().perform_previous()
            self.update_screen()
        elif label == 'v':
            self.run_update_callback()
            get_active_view().perform_next()
            self.update_screen()

    def sigint_handler(self, signum, frame):
        get_screen().clear()
        get_screen().update()
        sys.exit(0)

    def sigalrm_handler(self, signum, frame):
        self.log("SIGALRM")
        #self.log("Rack: " + json.dumps(get_rack().to_obj(), indent=4))
        self.run_update_callback()
        if self.pressed_button > 0:
            self.handle_button(self.pressed_button)

    def set_update_callback(self, cb):
        self.update_callback = cb

    def run_update_callback(self):
        if self.update_callback is not None:
            self.update_callback()
            self.update_callback = None

    def update_screen(self):
        get_active_view().render()
        
    def disable_update(self):
        self.disable_update_count += 1
        self.enable_or_disable_update_timer()

    def enable_update(self):
        if self.disable_update_count == 0:
            return
        self.disable_update_count -= 1
        self.enable_or_disable_update_timer()

    def schedule_update(self):
        self.set_update_callback(self.update_screen)
        self.enable_or_disable_update_timer()

    def enable_or_disable_update_timer(self):
        if self.disable_update_count == 0:
            self.set_update_timer(0.1)
        else:
            self.set_update_timer(0)

    def set_update_timer(self, timer):
        signal.setitimer(signal.ITIMER_REAL, timer)

controller = Controller()

def get_controller():
    return controller


def main():
    get_controller().update_screen()
    get_osc_client().start_loop()

main()

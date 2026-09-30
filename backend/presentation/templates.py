"""
Visual style presets: colors and fonts per presentation style.
Keeps ppt_generator.py free of hard-coded styling decisions.
"""
from pptx.util import Pt
from pptx.dml.color import RGBColor


STYLE_PRESETS = {
    "Academic": {
        "font_name": "Georgia",
        "title_color": RGBColor(0x1B, 0x2A, 0x4A),
        "accent_color": RGBColor(0x8B, 0x1E, 0x1E),
        "body_color": RGBColor(0x22, 0x22, 0x22),
        "background": RGBColor(0xFF, 0xFF, 0xFF),
        "title_size": Pt(34),
        "body_size": Pt(20),
    },
    "Professional": {
        "font_name": "Calibri",
        "title_color": RGBColor(0x0F, 0x2C, 0x54),
        "accent_color": RGBColor(0x1F, 0x77, 0xB4),
        "body_color": RGBColor(0x2E, 0x2E, 0x2E),
        "background": RGBColor(0xFF, 0xFF, 0xFF),
        "title_size": Pt(34),
        "body_size": Pt(20),
    },
    "Simple": {
        "font_name": "Verdana",
        "title_color": RGBColor(0x22, 0x66, 0x33),
        "accent_color": RGBColor(0x4C, 0xAF, 0x50),
        "body_color": RGBColor(0x33, 0x33, 0x33),
        "background": RGBColor(0xFF, 0xFF, 0xFF),
        "title_size": Pt(32),
        "body_size": Pt(20),
    },
    "Technical": {
        "font_name": "Consolas",
        "title_color": RGBColor(0x0A, 0x0A, 0x0A),
        "accent_color": RGBColor(0x00, 0x7A, 0xCC),
        "body_color": RGBColor(0x1A, 0x1A, 0x1A),
        "background": RGBColor(0xF5, 0xF5, 0xF5),
        "title_size": Pt(30),
        "body_size": Pt(18),
    },
    "Minimal": {
        "font_name": "Helvetica",
        "title_color": RGBColor(0x11, 0x11, 0x11),
        "accent_color": RGBColor(0x88, 0x88, 0x88),
        "body_color": RGBColor(0x33, 0x33, 0x33),
        "background": RGBColor(0xFF, 0xFF, 0xFF),
        "title_size": Pt(36),
        "body_size": Pt(20),
    },
}

DEFAULT_STYLE = STYLE_PRESETS["Professional"]


def get_style(style_name: str) -> dict:
    return STYLE_PRESETS.get(style_name, DEFAULT_STYLE)

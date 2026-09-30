"""
Reusable, style-aware slide-building functions for python-pptx.
Each function takes the Presentation object plus content and returns the
created slide. Nothing here is slide-specific/hard-coded - the caller
supplies all text.
"""
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor

BLANK_LAYOUT_INDEX = 6  # standard "Blank" layout in the default python-pptx template

SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)


def _blank_slide(prs):
    layout = prs.slide_layouts[BLANK_LAYOUT_INDEX]
    return prs.slides.add_slide(layout)


def _set_background(slide, color: RGBColor):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_textbox(slide, left, top, width, height):
    box = slide.shapes.add_textbox(left, top, width, height)
    box.text_frame.word_wrap = True
    return box


def _style_run(run, font_name, size, color, bold=False, italic=False):
    run.font.name = font_name
    run.font.size = size
    run.font.color.rgb = color
    run.font.bold = bold
    run.font.italic = italic


def add_slide_number(slide, number: int, total: int, style: dict):
    box = _add_textbox(slide, SLIDE_WIDTH - Inches(1.6), SLIDE_HEIGHT - Inches(0.5),
                        Inches(1.3), Inches(0.4))
    p = box.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    run = p.add_run()
    run.text = f"{number} / {total}"
    _style_run(run, style["font_name"], Pt(11), style["accent_color"])


def add_accent_bar(slide, style: dict, top=Inches(0), height=Inches(0.12)):
    from pptx.enum.shapes import MSO_SHAPE
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, top, SLIDE_WIDTH, height)
    bar.fill.solid()
    bar.fill.fore_color.rgb = style["accent_color"]
    bar.line.fill.background()
    bar.shadow.inherit = False


def create_title_slide(prs, title: str, subtitle: str, style: dict, number: int, total: int):
    slide = _blank_slide(prs)
    _set_background(slide, style["background"])
    add_accent_bar(slide, style, top=Inches(3.55), height=Inches(0.08))

    title_box = _add_textbox(slide, Inches(1), Inches(2.6), Inches(11.3), Inches(1.6))
    title_box.text_frame.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = title_box.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = title
    _style_run(run, style["font_name"], Pt(40), style["title_color"], bold=True)

    if subtitle:
        sub_box = _add_textbox(slide, Inches(1.5), Inches(3.9), Inches(10.3), Inches(1.0))
        p2 = sub_box.text_frame.paragraphs[0]
        p2.alignment = PP_ALIGN.CENTER
        run2 = p2.add_run()
        run2.text = subtitle
        _style_run(run2, style["font_name"], Pt(18), style["body_color"], italic=True)

    add_slide_number(slide, number, total, style)
    return slide


def _add_title_header(slide, title: str, style: dict):
    box = _add_textbox(slide, Inches(0.7), Inches(0.4), Inches(11.9), Inches(1.0))
    p = box.text_frame.paragraphs[0]
    run = p.add_run()
    run.text = title
    _style_run(run, style["font_name"], style["title_size"], style["title_color"], bold=True)
    add_accent_bar(slide, style, top=Inches(1.3), height=Inches(0.05))


def _add_bullets(text_frame, bullets, style, size=None):
    size = size or style["body_size"]
    text_frame.word_wrap = True
    for i, bullet in enumerate(bullets):
        p = text_frame.paragraphs[0] if i == 0 else text_frame.add_paragraph()
        p.level = 0
        run = p.add_run()
        run.text = f"•  {bullet}"
        _style_run(run, style["font_name"], size, style["body_color"])
        p.space_after = Pt(14)


def create_content_slide(prs, title: str, bullets: list, style: dict, number: int, total: int,
                          example: str = ""):
    slide = _blank_slide(prs)
    _set_background(slide, style["background"])
    _add_title_header(slide, title, style)

    body_box = _add_textbox(slide, Inches(0.9), Inches(1.7), Inches(11.5),
                             Inches(4.5 if not example else 3.4))
    _add_bullets(body_box.text_frame, bullets, style)

    if example:
        create_example_callout(slide, example, style, top=Inches(5.3))

    add_slide_number(slide, number, total, style)
    return slide


def create_two_column_slide(prs, title: str, left_bullets: list, right_bullets: list,
                             style: dict, number: int, total: int,
                             left_heading: str = "", right_heading: str = ""):
    slide = _blank_slide(prs)
    _set_background(slide, style["background"])
    _add_title_header(slide, title, style)

    col_width = Inches(5.6)
    left_box = _add_textbox(slide, Inches(0.7), Inches(1.8), col_width, Inches(5.0))
    right_box = _add_textbox(slide, Inches(6.9), Inches(1.8), col_width, Inches(5.0))

    if left_heading:
        p = left_box.text_frame.paragraphs[0]
        run = p.add_run()
        run.text = left_heading
        _style_run(run, style["font_name"], Pt(18), style["accent_color"], bold=True)
        _add_bullets_continue(left_box.text_frame, left_bullets, style)
    else:
        _add_bullets(left_box.text_frame, left_bullets, style)

    if right_heading:
        p = right_box.text_frame.paragraphs[0]
        run = p.add_run()
        run.text = right_heading
        _style_run(run, style["font_name"], Pt(18), style["accent_color"], bold=True)
        _add_bullets_continue(right_box.text_frame, right_bullets, style)
    else:
        _add_bullets(right_box.text_frame, right_bullets, style)

    add_slide_number(slide, number, total, style)
    return slide


def _add_bullets_continue(text_frame, bullets, style):
    for bullet in bullets:
        p = text_frame.add_paragraph()
        run = p.add_run()
        run.text = f"•  {bullet}"
        _style_run(run, style["font_name"], style["body_size"], style["body_color"])
        p.space_after = Pt(12)


def create_example_callout(slide, example_text: str, style: dict, top):
    from pptx.enum.shapes import MSO_SHAPE
    box_shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.9), top,
                                        Inches(11.5), Inches(1.4))
    box_shape.fill.solid()
    box_shape.fill.fore_color.rgb = style["accent_color"]
    box_shape.line.fill.background()
    box_shape.shadow.inherit = False

    tf = box_shape.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.2)
    tf.margin_right = Inches(0.2)
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = f"Example: {example_text}"
    _style_run(run, style["font_name"], Pt(16), RGBColor(0xFF, 0xFF, 0xFF), bold=False, italic=True)


def create_example_slide(prs, title: str, bullets: list, example: str, style: dict,
                          number: int, total: int):
    """A slide dedicated primarily to a worked example."""
    slide = _blank_slide(prs)
    _set_background(slide, style["background"])
    _add_title_header(slide, title, style)

    if bullets:
        body_box = _add_textbox(slide, Inches(0.9), Inches(1.7), Inches(11.5), Inches(2.6))
        _add_bullets(body_box.text_frame, bullets, style)
        example_top = Inches(4.5)
    else:
        example_top = Inches(2.2)

    if example:
        create_example_callout(slide, example, style, top=example_top)

    add_slide_number(slide, number, total, style)
    return slide


def create_conclusion_slide(prs, title: str, bullets: list, style: dict, number: int, total: int):
    slide = _blank_slide(prs)
    _set_background(slide, style["background"])
    add_accent_bar(slide, style, top=Inches(0), height=Inches(0.12))

    title_box = _add_textbox(slide, Inches(0.9), Inches(0.7), Inches(11.5), Inches(1.0))
    p = title_box.text_frame.paragraphs[0]
    run = p.add_run()
    run.text = title
    _style_run(run, style["font_name"], style["title_size"], style["title_color"], bold=True)

    body_box = _add_textbox(slide, Inches(0.9), Inches(1.9), Inches(11.5), Inches(4.5))
    _add_bullets(body_box.text_frame, bullets, style)

    add_slide_number(slide, number, total, style)
    return slide

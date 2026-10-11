import os
import pptx
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml import parse_xml

def create_presentation(output_path):
    prs = Presentation()
    # 16:9 Widescreen standard
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6]

    # Color Palette Definitions
    BG_DARK = RGBColor(15, 23, 42)          # #0F172A Deep Navy
    BG_CARD_DARK = RGBColor(30, 41, 59)     # #1E293B Dark Slate Card
    BG_LIGHT = RGBColor(248, 250, 252)      # #F8FAFC Crisp Light
    CARD_BG = RGBColor(255, 255, 255)       # Pure White
    CARD_BORDER = RGBColor(226, 232, 240)   # #E2E8F0 Subtle Gray Border
    
    TEXT_DARK = RGBColor(15, 23, 42)        # Main dark text
    TEXT_MUTED = RGBColor(71, 85, 105)      # Slate gray text
    TEXT_LIGHT = RGBColor(248, 250, 252)    # Light white text
    TEXT_LIGHT_MUTED = RGBColor(148, 163, 184) # Light muted text
    
    ACCENT_TEAL = RGBColor(13, 148, 136)     # #0D9488 Teal
    ACCENT_CYAN = RGBColor(2, 132, 199)      # #0284C7 Sky Blue
    ACCENT_EMERALD = RGBColor(16, 185, 129)  # #10B981 Emerald
    ACCENT_AMBER = RGBColor(217, 119, 6)     # #D97706 Amber
    ACCENT_ROSE = RGBColor(225, 29, 72)      # #E11D48 Rose Red
    ACCENT_INDIGO = RGBColor(79, 70, 229)    # #4F46E5 Indigo
    ACCENT_GOLD = RGBColor(234, 179, 8)      # #EAB308 Gold
    
    FONT_FA = 'Tahoma'

    def apply_rtl_and_font(paragraph, text="", font_size=Pt(13), bold=False, color=TEXT_DARK, align=PP_ALIGN.RIGHT, space_after=Pt(4)):
        paragraph.alignment = align
        if space_after:
            paragraph.space_after = space_after
        pPr = paragraph._p.get_or_add_pPr()
        pPr.set('rtl', '1')
        if align == PP_ALIGN.RIGHT:
            pPr.set('algn', 'r')
        elif align == PP_ALIGN.CENTER:
            pPr.set('algn', 'ctr')
        elif align == PP_ALIGN.LEFT:
            pPr.set('algn', 'l')
            
        if text:
            run = paragraph.add_run()
            run.text = text
            run.font.name = FONT_FA
            run.font.size = font_size
            run.font.bold = bold
            run.font.color.rgb = color
            
            rPr = run._r.get_or_add_rPr()
            rPr.set('lang', 'fa-IR')
            rPr.set('altLang', 'en-US')
            cs = parse_xml(f'<a:cs xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" typeface="{FONT_FA}"/>')
            rPr.append(cs)
            ea = parse_xml(f'<a:ea xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" typeface="{FONT_FA}"/>')
            rPr.append(ea)
            latin = parse_xml(f'<a:latin xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" typeface="{FONT_FA}"/>')
            rPr.append(latin)
            return run
        return None

    def add_background(slide, color):
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = color
        bg.line.fill.background()
        return bg

    def add_header(slide, badge_text, title_text, subtitle_text=""):
        header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.733), Inches(1.25))
        tf = header_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        
        # Badge line
        p_badge = tf.paragraphs[0]
        apply_rtl_and_font(p_badge, f"« {badge_text} »", font_size=Pt(11), bold=True, color=ACCENT_TEAL, space_after=Pt(2))
        
        # Title line
        p_title = tf.add_paragraph()
        apply_rtl_and_font(p_title, title_text, font_size=Pt(22), bold=True, color=TEXT_DARK, space_after=Pt(3))
        
        # Subtitle line
        if subtitle_text:
            p_sub = tf.add_paragraph()
            apply_rtl_and_font(p_sub, subtitle_text, font_size=Pt(12), bold=False, color=TEXT_MUTED, space_after=Pt(0))

    def add_footer(slide, slide_num, total_slides=17):
        footer_box = slide.shapes.add_textbox(Inches(0.8), Inches(7.0), Inches(11.733), Inches(0.4))
        tf = footer_box.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.RIGHT
        pPr = p._p.get_or_add_pPr()
        pPr.set('rtl', '1')
        pPr.set('algn', 'r')
        
        r1 = p.add_run()
        r1.text = f"درس حسابرسی  |  استاد بهرامیان  |  مفهوم رویدادهای بعد از تاریخ ترازنامه                          اسلاید {slide_num} از {total_slides}"
        r1.font.name = FONT_FA
        r1.font.size = Pt(10)
        r1.font.color.rgb = TEXT_MUTED
        rPr = r1._r.get_or_add_rPr()
        rPr.set('lang', 'fa-IR')
        rPr.set('altLang', 'en-US')

    def create_card(slide, left, top, width, height, accent_color=ACCENT_TEAL, bg_color=CARD_BG, border_color=CARD_BORDER):
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
        card.fill.solid()
        card.fill.fore_color.rgb = bg_color
        if border_color:
            card.line.color.rgb = border_color
            card.line.width = Pt(1.2)
        else:
            card.line.fill.background()
            
        strip = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, Inches(0.12))
        strip.fill.solid()
        strip.fill.fore_color.rgb = accent_color
        strip.line.fill.background()
        return card

    # ==========================================
    # SLIDE 1: Title Slide (Dark Hero Style)
    # ==========================================
    s1 = prs.slides.add_slide(blank_layout)
    add_background(s1, BG_DARK)
    
    bg_decor = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.0), Inches(0.8), Inches(11.333), Inches(5.9))
    bg_decor.fill.solid()
    bg_decor.fill.fore_color.rgb = BG_CARD_DARK
    bg_decor.line.color.rgb = RGBColor(51, 65, 85)
    bg_decor.line.width = Pt(1)

    # Top Pill Badge
    pill = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(4.6), Inches(1.2), Inches(4.1), Inches(0.45))
    pill.fill.solid()
    pill.fill.fore_color.rgb = RGBColor(19, 78, 74)
    pill.line.color.rgb = ACCENT_TEAL
    p_pill = pill.text_frame.paragraphs[0]
    apply_rtl_and_font(p_pill, "ارائه جامع درسی و دانشگاهی", font_size=Pt(12), bold=True, color=RGBColor(45, 212, 191), align=PP_ALIGN.CENTER)

    # Main Title Box
    title_box = s1.shapes.add_textbox(Inches(1.5), Inches(1.9), Inches(10.333), Inches(2.3))
    tf1 = title_box.text_frame
    tf1.word_wrap = True
    
    p_t1 = tf1.paragraphs[0]
    apply_rtl_and_font(p_t1, "مفهوم رویدادهای بعد از تاریخ ترازنامه", font_size=Pt(32), bold=True, color=TEXT_LIGHT, align=PP_ALIGN.CENTER, space_after=Pt(6))
    
    p_t2 = tf1.add_paragraph()
    apply_rtl_and_font(p_t2, "و وظایف حسابرس نسبت به آن", font_size=Pt(30), bold=True, color=RGBColor(56, 189, 248), align=PP_ALIGN.CENTER, space_after=Pt(8))
    
    p_t3 = tf1.add_paragraph()
    apply_rtl_and_font(p_t3, "بررسی استانداردهای حسابرسی، رویدادهای تعدیلی و غیرتعدیلی و رویه‌های گزارشگری", font_size=Pt(14), bold=False, color=TEXT_LIGHT_MUTED, align=PP_ALIGN.CENTER)

    # Info Box (Professor and presentation meta)
    info_card = s1.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(2.2), Inches(4.5), Inches(8.9), Inches(1.6))
    info_card.fill.solid()
    info_card.fill.fore_color.rgb = RGBColor(15, 23, 42)
    info_card.line.color.rgb = RGBColor(71, 85, 105)
    
    tf_info = info_card.text_frame
    tf_info.word_wrap = True
    
    p_i1 = tf_info.paragraphs[0]
    apply_rtl_and_font(p_i1, "استاد ارجمند: جناب استاد بهرامیان", font_size=Pt(17), bold=True, color=RGBColor(253, 224, 71), align=PP_ALIGN.CENTER, space_after=Pt(4))
    
    p_i2 = tf_info.add_paragraph()
    apply_rtl_and_font(p_i2, "درس: اصول و مباحث جاری در حسابرسی و حسابداری", font_size=Pt(13), bold=False, color=TEXT_LIGHT, align=PP_ALIGN.CENTER, space_after=Pt(2))
    
    p_i3 = tf_info.add_paragraph()
    apply_rtl_and_font(p_i3, "تنظیم و ارائه: سمینار دانشجویی کارشناسی و کارشناسی ارشد", font_size=Pt(12), bold=False, color=TEXT_LIGHT_MUTED, align=PP_ALIGN.CENTER)

    # ==========================================
    # SLIDE 2: Table of Contents (Dark Clean Layout)
    # ==========================================
    s2 = prs.slides.add_slide(blank_layout)
    add_background(s2, BG_DARK)
    
    h2 = s2.shapes.add_textbox(Inches(0.8), Inches(0.5), Inches(11.733), Inches(1.1))
    tf2 = h2.text_frame
    p = tf2.paragraphs[0]
    apply_rtl_and_font(p, "« ساختار ارائه »", font_size=Pt(11), bold=True, color=ACCENT_CYAN, space_after=Pt(2))
    p2 = tf2.add_paragraph()
    apply_rtl_and_font(p2, "فهرست مطالب و محورهای اصلی سمینار", font_size=Pt(24), bold=True, color=TEXT_LIGHT)

    agenda_items = [
        ("محور اول: مقدمه و اصل افشای کامل", "تنوع ذینفعان، محدودیت‌های حسابداری و ضرورت شفافیت اطلاعاتی", ACCENT_TEAL),
        ("محور دوم: تعریف و خط زمانی رویدادها", "مفهوم رویدادهای پس از تاریخ ترازنامه و بازه زمانی وقوع", ACCENT_CYAN),
        ("محور سوم: طبقه‌بندی جامع رویدادها", "بیانیه شماره ۲۵، رویدادهای تعدیلی و رویدادهای غیرتعدیلی", ACCENT_EMERALD),
        ("محور چهارم: رویدادهای احتمالی و صورت‌های فرضی", "مفهوم مقتضیات احتمالی و ارائه صورت‌های مالی فرضی [Pro-Forma]", ACCENT_AMBER),
        ("محور پنجم: روش‌های رسیدگی در ۳ مقطع زمانی", "رسیدگی تا تاریخ گزارش، پیش از انتشار و پس از انتشار عمومی", ACCENT_ROSE),
        ("محور ششم: تاریخ‌گذاری دوگانه و جمع‌بندی", "مفهوم Dual Dating، مقایسه رویکردها و ماتریس نهایی وظایف", ACCENT_INDIGO)
    ]
    
    card_w = Inches(3.7)
    card_h = Inches(2.2)
    positions = [
        (Inches(8.8), Inches(1.8)),  # Col 1 (Rightmost)
        (Inches(4.8), Inches(1.8)),  # Col 2
        (Inches(0.8), Inches(1.8)),  # Col 3
        (Inches(8.8), Inches(4.3)),  # Row 2 Col 1
        (Inches(4.8), Inches(4.3)),  # Row 2 Col 2
        (Inches(0.8), Inches(4.3))   # Row 2 Col 3
    ]
    
    for idx, (title, desc, acc) in enumerate(agenda_items):
        pos_x, pos_y = positions[idx]
        cd = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pos_x, pos_y, card_w, card_h)
        cd.fill.solid()
        cd.fill.fore_color.rgb = BG_CARD_DARK
        cd.line.color.rgb = RGBColor(51, 65, 85)
        cd.line.width = Pt(1)
        
        st = s2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pos_x, pos_y, card_w, Inches(0.1))
        st.fill.solid()
        st.fill.fore_color.rgb = acc
        st.line.fill.background()
        
        tf_c = cd.text_frame
        tf_c.word_wrap = True
        tf_c.margin_left = tf_c.margin_right = tf_c.margin_top = Inches(0.2)
        p_c1 = tf_c.paragraphs[0]
        apply_rtl_and_font(p_c1, title, font_size=Pt(13.5), bold=True, color=TEXT_LIGHT, space_after=Pt(6))
        
        p_c2 = tf_c.add_paragraph()
        apply_rtl_and_font(p_c2, desc, font_size=Pt(11), bold=False, color=TEXT_LIGHT_MUTED)

    add_footer(s2, 2)

    # ==========================================
    # SLIDE 3: Introduction & Full Disclosure (Light)
    # ==========================================
    s3 = prs.slides.add_slide(blank_layout)
    add_background(s3, BG_LIGHT)
    add_header(s3, "بخش اول: مبانی نظری", "مقدمه؛ استفاده‌کنندگان گزارش‌های مالی و اصل افشای کامل", "چرا رویدادهای پس از تاریخ ترازنامه برای استفاده‌کنندگان صورت‌های مالی حیاتی هستند؟")
    
    w3 = Inches(3.7)
    h3 = Inches(4.8)
    
    # Card 1 (Rightmost)
    c1 = create_card(s3, Inches(8.8), Inches(1.8), w3, h3, ACCENT_CYAN)
    tf = c1.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۱. تنوع نیازهای اطلاعاتی ذینفعان", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(8))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- استفاده‌کنندگان صورت‌های مالی از اقشار گوناگون اجتماع تشکیل شده‌اند (سهامداران، اعتباردهندگان، دولت و مدیران).", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- سطوح آگاهی، علایق و نیازهای تصمیم‌گیری این گروه‌ها بسیار متفاوت و گسترده است.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- ارضای کامل تمام نیازهای فردی امکان‌پذیر نیست؛ لذا استانداردسازی اطلاعات برای عموم ضرورت دارد.", font_size=Pt(12), color=TEXT_DARK)

    # Card 2 (Center)
    c2 = create_card(s3, Inches(4.8), Inches(1.8), w3, h3, ACCENT_AMBER)
    tf = c2.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۲. محدودیت‌های محیطی و عدم‌قطعیت", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(8))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- حسابداران در تهیه اطلاعات مالی با محدودیت‌های محیطی و فرض‌های بنیادی حسابداری مواجهند.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- تقریباً کلیه ارقام صورت‌های مالی به علت ابهامات مربوط به آینده، دارای ماهیت غیرقطعی هستند.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- اتکای ارقام مالی بر برآوردها و قضاوت‌ها، ضرورت دریافت شواهد تکمیلی را دوچندان می‌کند.", font_size=Pt(12), color=TEXT_DARK)

    # Card 3 (Leftmost)
    c3 = create_card(s3, Inches(0.8), Inches(1.8), w3, h3, ACCENT_TEAL)
    tf = c3.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۳. اصل بنیادی افشای کامل", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(8))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- یکی از اصول اول اولیه حسابداری، افشای تمامی واقعیت‌های بااهمیت مالی و رویدادهای مؤثر است.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "اهداف کلیدی اصل افشای کامل:", font_size=Pt(12), bold=True, color=ACCENT_TEAL, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "• ارزیابی دقیق عملکرد واقعی واحد تجاری\n• داوری منصفانه درباره نحوه استفاده از منابع\n• پیش‌بینی صحیح دورنما و ریسک‌های آینده", font_size=Pt(12), color=TEXT_DARK)

    add_footer(s3, 3)

    # ==========================================
    # SLIDE 4: Definition & Timeline of Subsequent Events
    # ==========================================
    s4 = prs.slides.add_slide(blank_layout)
    add_background(s4, BG_LIGHT)
    add_header(s4, "بخش اول: مبانی نظری", "تعریف رویدادهای پس از تاریخ ترازنامه و بازه زمانی وقوع", "بررسی فاصله زمانی میان پایان سال مالی و صدور گزارش حسابرسی")
    
    # Top Card: Definition
    c_def = create_card(s4, Inches(0.8), Inches(1.8), Inches(11.733), Inches(2.3), ACCENT_CYAN)
    tf_def = c_def.text_frame
    tf_def.word_wrap = True
    tf_def.margin_left = tf_def.margin_right = Inches(0.3)
    tf_def.margin_top = Inches(0.25)
    
    p = tf_def.paragraphs[0]
    apply_rtl_and_font(p, "تعریف رسمی و استانداردی رویدادهای پس از تاریخ ترازنامه [Subsequent Events]:", font_size=Pt(15), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf_def.add_paragraph()
    apply_rtl_and_font(p, "«به آن گروه از رویدادها که پس از تاریخ ترازنامه (پایان دوره مالی مورد گزارش)، اما قبل از صدور و انتشار صورت‌های مالی و گزارش حسابرسی اتفاق می‌افتد و دارای آثار بااهمیت بر صورت‌های مالی بوده و نیازمند اصلاح ارقام یا افشا در صورت‌های مالی است، رویدادهای پس از تاریخ ترازنامه گفته می‌شود.»", font_size=Pt(12.5), bold=False, color=RGBColor(30, 41, 59), space_after=Pt(6))
    p = tf_def.add_paragraph()
    apply_rtl_and_font(p, "نکته کلیدی: با گذشت زمان، ابهامات موجود در تاریخ ترازنامه برطرف می‌شود و اطلاعات تکمیلی به دست می‌آید؛ این اطلاعات ممکن است قضاوت تصمیم‌گیرندگان را تغییر دهد.", font_size=Pt(12), bold=True, color=ACCENT_CYAN)

    # Bottom Area: 3 Timeline stages
    timeline_boxes = [
        ("مرحله ۱: پایان سال مالی", "تاریخ ترازنامه (پایان دوره مالی)\nاندازه‌گیری منابع، بدهی‌ها و حقوق صاحبان سهام در پایان دوره", ACCENT_INDIGO, Inches(8.8)),
        ("مرحله ۲: دوره رسیدگی میدانی", "فاصله زمانی تا اتمام کار حسابرسی\nکسب اطلاعات تکمیلی، رفع ابهامات و بررسی رویدادهای بااهمیت", ACCENT_AMBER, Inches(4.8)),
        ("مرحله ۳: گزارشگری و انتشار", "تاریخ گزارش حسابرس و انتشار عمومی\nانعکاس تعدیلات در متن یا افشا در یادداشت‌های همراه صورت‌های مالی", ACCENT_EMERALD, Inches(0.8))
    ]
    
    for title, desc, col, pos_x in timeline_boxes:
        box = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pos_x, Inches(4.4), Inches(3.7), Inches(2.2))
        box.fill.solid()
        box.fill.fore_color.rgb = CARD_BG
        box.line.color.rgb = col
        box.line.width = Pt(1.5)
        
        st = s4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, pos_x, Inches(4.4), Inches(3.7), Inches(0.12))
        st.fill.solid()
        st.fill.fore_color.rgb = col
        st.line.fill.background()
        
        tf_b = box.text_frame
        tf_b.word_wrap = True
        tf_b.margin_left = tf_b.margin_right = Inches(0.2)
        tf_b.margin_top = Inches(0.2)
        
        p = tf_b.paragraphs[0]
        apply_rtl_and_font(p, title, font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
        p = tf_b.add_paragraph()
        apply_rtl_and_font(p, desc, font_size=Pt(11), bold=False, color=TEXT_MUTED)

    add_footer(s4, 4)

    # ==========================================
    # SLIDE 5: Classification by Statement No. 25
    # ==========================================
    s5 = prs.slides.add_slide(blank_layout)
    add_background(s5, BG_LIGHT)
    add_header(s5, "بخش دوم: طبقه‌بندی رویدادها", "طبقه‌بندی رویدادها بر اساس بیانیه روش‌های حسابرسی شماره ۲۵", "تفکیک انواع رویدادها و معاملات پس از تاریخ ترازنامه به سه گروه تخصصی")
    
    c1 = create_card(s5, Inches(8.8), Inches(1.8), Inches(3.7), Inches(4.8), ACCENT_EMERALD)
    tf1 = c1.text_frame
    tf1.word_wrap = True
    tf1.margin_left = tf1.margin_right = Inches(0.25)
    tf1.margin_top = Inches(0.25)
    p = tf1.paragraphs[0]
    apply_rtl_and_font(p, "رویدادهای گروه اول\n[دارای اثر مستقیم بر ارقام]", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(8))
    p = tf1.add_paragraph()
    apply_rtl_and_font(p, "- رویدادهایی هستند که مستقیماً بر مبالغ و ارقام صورت‌های مالی تأثیر می‌گذارند.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf1.add_paragraph()
    apply_rtl_and_font(p, "- اطلاعات بعدی مبنایی دقیق‌تر برای برآوردها و پیش‌بینی‌ها فراهم می‌آورد.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf1.add_paragraph()
    apply_rtl_and_font(p, "- الزام حسابداری: اگر این اطلاعات در تاریخ ترازنامه موجود بود، اعمال می‌شد؛ لذا باید اصلاحات و تعدیلات مناسب در صورت‌های مالی انجام پذیرد.", font_size=Pt(12), bold=True, color=ACCENT_EMERALD)

    c2 = create_card(s5, Inches(4.8), Inches(1.8), Inches(3.7), Inches(4.8), ACCENT_CYAN)
    tf2 = c2.text_frame
    tf2.word_wrap = True
    tf2.margin_left = tf2.margin_right = Inches(0.25)
    tf2.margin_top = Inches(0.25)
    p = tf2.paragraphs[0]
    apply_rtl_and_font(p, "رویدادهای گروه دوم\n[فاقد اثر مستقیم بر ارقام]", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(8))
    p = tf2.add_paragraph()
    apply_rtl_and_font(p, "- رویدادهایی که تأثیر مستقیم بر مبالغ صورت‌های مالی دوره مورد گزارش ندارند.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf2.add_paragraph()
    apply_rtl_and_font(p, "- اصلاح ارقام دوره‌های قبل را الزامی نمی‌کنند.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf2.add_paragraph()
    apply_rtl_and_font(p, "- الزام حسابداری: اثر آن‌ها به گونه‌ای است که افشای آن‌ها در یادداشت‌های پیوست برای آگاهی ذینفعان و تصمیم‌گیری درست ضرورت دارد.", font_size=Pt(12), bold=True, color=ACCENT_CYAN)

    c3 = create_card(s5, Inches(0.8), Inches(1.8), Inches(3.7), Inches(4.8), ACCENT_ROSE)
    tf3 = c3.text_frame
    tf3.word_wrap = True
    tf3.margin_left = tf3.margin_right = Inches(0.25)
    tf3.margin_top = Inches(0.25)
    p = tf3.paragraphs[0]
    apply_rtl_and_font(p, "رویدادهای گروه سوم\n[رویدادهای غیرحسابداری]", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(8))
    p = tf3.add_paragraph()
    apply_rtl_and_font(p, "- رویدادهای محیطی مانند وقوع جنگ، تغییرات مدیریتی، اعتصابات کارگری و ورشکستگی مشتریان عمده.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf3.add_paragraph()
    apply_rtl_and_font(p, "- افشای این اطلاعات معمولاً موجب شک و تردید نسبت به علل رخداد آن‌ها می‌شود.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf3.add_paragraph()
    apply_rtl_and_font(p, "- چالش افشا: همان‌قدر که افشای آن‌ها آگاهی‌دهنده است، به همان اندازه می‌تواند موجب گمراهی استفاده‌کنندگان شود.", font_size=Pt(12), bold=True, color=ACCENT_ROSE)

    add_footer(s5, 5)

    # ==========================================
    # SLIDE 6: Group 1 - Adjusting Events
    # ==========================================
    s6 = prs.slides.add_slide(blank_layout)
    add_background(s6, BG_LIGHT)
    add_header(s6, "بخش دوم: طبقه‌بندی رویدادها", "گروه اول: رویدادهای تعدیلی [Adjusting Events]", "ویژگی‌ها، معیارهای شناسایی و شرایط انعکاس در متن صورت‌های مالی اساسی")
    
    w6 = Inches(5.7)
    h6 = Inches(4.8)
    
    # Card 1 (Right): Definition
    c_adj_def = create_card(s6, Inches(6.8), Inches(1.8), w6, h6, ACCENT_EMERALD)
    tf = c_adj_def.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "مفهوم و ماهیت رویدادهای تعدیلی", font_size=Pt(15), bold=True, color=TEXT_DARK, space_after=Pt(8))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- رویدادهایی هستند که منجر به روشن شدن اطلاعات بیشتر درباره شرایطی می‌شوند که در تاریخ ترازنامه وجود داشته‌اند.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- علت رخداد: ناشی از نبود اطلاعات کافی طی دوره مالی است و با دسترسی به شواهد جدید، ارزیابی‌ها و برآوردها دگرگون می‌شود.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- اثر حسابداری: مستقیماً بر مبالغ متن صورت‌های مالی اثر گذاشته و مستلزم اصلاح و تعدیل ارقام قبل از انتشار هستند.", font_size=Pt(12), bold=True, color=ACCENT_EMERALD, space_after=Pt(8))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "نمونه‌های بارز رویدادهای تعدیلی:", font_size=Pt(12.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "۱. ورشکستگی مشتری پس از پایان دوره مالی به علت بدهی قبلی\n۲. صدور حکم قطعی دادگاه درباره دعوای حقوقی معوق با رقم مشخص", font_size=Pt(11.5), color=TEXT_MUTED)

    # Card 2 (Left): 3 Essential Conditions
    c_adj_cond = create_card(s6, Inches(0.8), Inches(1.8), w6, h6, ACCENT_CYAN)
    tf = c_adj_cond.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "شرایط سه‌گانه انعکاس در متن صورت‌های مالی", font_size=Pt(15), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "آثار رویدادهای پس از تاریخ ترازنامه تنها در صورتی در متن صورت‌های مالی تعدیل می‌شود که دارای این ۳ شرط همزمان باشد:", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(8))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "شرط اول: شواهد تکمیلی درباره شرایط تاریخ ترازنامه", font_size=Pt(12.5), bold=True, color=ACCENT_CYAN, space_after=Pt(2))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "رویداد باید فراهم‌کننده شواهد و مدارک اضافی درباره وضعیت‌هایی باشد که در تاریخ ترازنامه وجود داشته است.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(6))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "شرط دوم: اثرگذاری بر برآوردهای فرایند گزارشگری", font_size=Pt(12.5), bold=True, color=ACCENT_CYAN, space_after=Pt(2))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "رویداد بر برآوردهای اجتناب‌ناپذیر حسابداری در تهیه صورت‌های مالی تأثیر مستقیم داشته باشد.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(6))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "شرط سوم: ضرورت اصلاح ارقام مالی اساسی", font_size=Pt(12.5), bold=True, color=ACCENT_CYAN, space_after=Pt(2))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "تعدیل اطلاعات مالی منعکس در متن صورت‌های مالی اساسی ناشی از این برآوردها را کاملاً ضروری سازد.", font_size=Pt(11.5), color=TEXT_DARK)

    add_footer(s6, 6)

    # ==========================================
    # SLIDE 7: Group 2 - Non-Adjusting Events
    # ==========================================
    s7 = prs.slides.add_slide(blank_layout)
    add_background(s7, BG_LIGHT)
    add_header(s7, "بخش دوم: طبقه‌بندی رویدادها", "گروه دوم: رویدادهای غیرتعدیلی [Non-Adjusting Events]", "رویدادهای ناشی از شرایط جدید پس از تاریخ ترازنامه و ضوابط افشا در یادداشت‌ها")
    
    c_non_def = create_card(s7, Inches(6.8), Inches(1.8), w6, h6, ACCENT_AMBER)
    tf = c_non_def.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "مفهوم و ماهیت رویدادهای غیرتعدیلی", font_size=Pt(15), bold=True, color=TEXT_DARK, space_after=Pt(8))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- رویدادهایی هستند که منجر به روشن شدن اطلاعات درباره شرایطی می‌شود که در تاریخ ترازنامه وجود نداشته و پس از آن اتفاق افتاده است.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- عدم تعدیل ارقام: این رویدادها مستلزم اصلاح و تعدیل ارقام مبالغ مالی متن ترازنامه و سود و زیان نیستند.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- الزام افشا: صرفاً افشای آن‌ها از راه یادداشت‌های پیوست صورت‌های مالی کافی خواهد بود تا استفاده‌کننده تصویر منصفانه‌ای دریافت کند.", font_size=Pt(12), bold=True, color=ACCENT_AMBER, space_after=Pt(8))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "نمونه‌های متداول رویدادهای غیرتعدیلی:", font_size=Pt(12.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "• آتش‌سوزی در انبار یا کارخانه در سال مالی جدید\n• صدور سهام جدید یا انتشار اوراق مشارکت با مبالغ بااهمیت\n• نوسان شدید قیمت‌ها و کاهش ارزش سرمایه‌گذاری‌ها", font_size=Pt(11.5), color=TEXT_MUTED)

    # Card 2 (Left): Conditions for note disclosure
    c_non_cond = create_card(s7, Inches(0.8), Inches(1.8), w6, h6, ACCENT_INDIGO)
    tf = c_non_cond.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "ضوابط سه‌گانه افشا در یادداشت‌های پیوست", font_size=Pt(15), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "رویدادهای پس از تاریخ ترازنامه را هنگامی می‌توان صرفاً از طریق یادداشت‌های پیوست افشا نمود که واجد شرایط زیر باشند:", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(8))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "۱. عدم ارتباط با شرایط تاریخ ترازنامه", font_size=Pt(12.5), bold=True, color=ACCENT_INDIGO, space_after=Pt(2))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "ناشی از شرایط موجود در تاریخ ترازنامه نباشد (پدیده‌ای کاملاً تازه باشد).", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(6))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "۲. وقوع حتمی پس از تاریخ ترازنامه", font_size=Pt(12.5), bold=True, color=ACCENT_INDIGO, space_after=Pt(2))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "حتماً و قطعاً در فاصله زمانی پس از تاریخ ترازنامه واقع شده باشد.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(6))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "۳. عدم تطابق با معیارهای تعدیل ارقام", font_size=Pt(12.5), bold=True, color=ACCENT_INDIGO, space_after=Pt(2))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "بدون شرایط و معیارهای لازم برای اصلاح متن باشد، اما بدون اطلاع از آن، استفاده‌کننده دچار گمراهی در قضاوت شود.", font_size=Pt(11.5), color=TEXT_DARK)

    add_footer(s7, 7)

    # ==========================================
    # SLIDE 8: Contingent Events & Pro-Forma Statements
    # ==========================================
    s8 = prs.slides.add_slide(blank_layout)
    add_background(s8, BG_LIGHT)
    add_header(s8, "بخش دوم: طبقه‌بندی رویدادها", "رویدادهای احتمالی و صورت‌های مالی فرضی [Pro-Forma]", "نحوه مواجهه با عدم قطعیت‌های شدید و رویدادهای دگرگون‌کننده ساختار مالی")
    
    c_cont = create_card(s8, Inches(6.8), Inches(1.8), w6, h6, ACCENT_CYAN)
    tf = c_cont.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "رویدادهای احتمالی [Contingent Events]", font_size=Pt(15), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "رویدادهای احتمالی به عنوان بخش مهمی از رویدادهای پس از تاریخ ترازنامه تلقی شده و نیازمند توجه ویژه حسابرس هستند.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "تعریف رویداد احتمالی:", font_size=Pt(12.5), bold=True, color=ACCENT_CYAN, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "«وضعیت، شرایط یا مجموعه‌ای از مقتضیات موجود است که با ضرایب احتمال مختلفی ممکن است بر اثر رویدادهای آتی مربوط به تحصیل یا از دست دادن دارایی یا ایجاد یا پرهیز از بدهی (معمولاً همراه با کسب سود یا تحمل زیان) منجر شود.»", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "الزام گزارشگری: بررسی درجه احتمال وقوع برای تصمیم‌گیری در خصوص شناسایی ذخیره یا صرفاً افشا در یادداشت‌های پیوست.", font_size=Pt(11.5), bold=True, color=TEXT_MUTED)

    c_prof = create_card(s8, Inches(0.8), Inches(1.8), w6, h6, ACCENT_AMBER)
    tf = c_prof.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "صورت‌های مالی فرضی [Pro-Forma]", font_size=Pt(15), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "گاه رویدادهای پس از تاریخ ترازنامه چنان بااهمیت است که همراه صورت‌های مالی اصلی، صورت‌های مالی فرضی ارائه می‌شود.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "هدف ارائه فرضی:", font_size=Pt(12.5), bold=True, color=ACCENT_AMBER, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "تاثیر رویدادهای پس از تاریخ ترازنامه را به گونه‌ای نشان دهد که گویی رویداد در همان تاریخ ترازنامه رخ داده است.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "شیوه ارائه و موارد کاربرد:", font_size=Pt(12.5), bold=True, color=TEXT_DARK, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- معمولاً تنها ترازنامه فرضی در یک ستون در کنار ترازنامه اصلی ارائه می‌شود.\n- کاربرد اصلی در مواردی نظیر ادغام شرکت‌ها [Mergers] است که رویداد اثر چشمگیری بر ساختار دارایی‌ها یا سرمایه دارد.", font_size=Pt(11.5), color=TEXT_MUTED)

    add_footer(s8, 8)

    # ==========================================
    # SLIDE 9: Audit Objectives
    # ==========================================
    s9 = prs.slides.add_slide(blank_layout)
    add_background(s9, BG_LIGHT)
    add_header(s9, "بخش سوم: مسئولیت‌ها و اهداف حسابرسی", "اهداف اساسی حسابرسی رویدادهای پس از تاریخ ترازنامه", "کسب اطمینان معقول و صیانت از تمامیت و قابلیت اتکای صورت‌های مالی")
    
    grid_w = Inches(5.7)
    grid_h = Inches(2.25)
    
    b1 = create_card(s9, Inches(6.8), Inches(1.8), grid_w, grid_h, ACCENT_TEAL)
    tf = b1.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۱. کسب اطمینان معقول [Reasonable Assurance]", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "کسب اطمینان معقول درباره شناسایی تمامی رویدادهای مهم واقع شده پس از تاریخ ترازنامه و ارزیابی لزوم افشا یا ثبت آن‌ها.", font_size=Pt(11.5), color=TEXT_DARK)

    b2 = create_card(s9, Inches(0.8), Inches(1.8), grid_w, grid_h, ACCENT_CYAN)
    tf = b2.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۲. انعکاس صحیح و مناسب [Appropriate Accounting]", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "اطمینان از اینکه تمامی رویدادها بسته به ماهیت خود، به درستی در متن حساب‌ها منظور شده یا در یادداشت‌های پیوست افشا گردیده‌اند.", font_size=Pt(11.5), color=TEXT_DARK)

    b3 = create_card(s9, Inches(6.8), Inches(4.35), grid_w, grid_h, ACCENT_EMERALD)
    tf = b3.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۳. صحت ارزش‌های ترازنامه‌ای [Valuation]", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "اطمینان از اینکه ارزش دارایی‌ها و بدهی‌های گزارش شده در ترازنامه به طور صحیح شامل آثار رویدادهای تعدیلی بعدی است.", font_size=Pt(11.5), color=TEXT_DARK)

    b4 = create_card(s9, Inches(0.8), Inches(4.35), grid_w, grid_h, ACCENT_ROSE)
    tf = b4.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۴. صیانت از تمامیت صورت‌های مالی [Completeness]", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "حسابرس باید اطمینان حاصل کند که هیچ رویداد بااهمیتی که موجب مخدوش شدن اظهارنظر درباره تمامیت صورت‌های مالی شود وجود ندارد.", font_size=Pt(11.5), color=TEXT_DARK)

    add_footer(s9, 9)

    # ==========================================
    # SLIDE 10: Auditor Responsibilities Roadmap (3 Intervals)
    # ==========================================
    s10 = prs.slides.add_slide(blank_layout)
    add_background(s10, BG_LIGHT)
    add_header(s10, "بخش چهارم: روش‌های رسیدگی", "مقاطع زمانی سه‌گانه وظایف حسابرس (نقشه راه رسیدگی)", "تفکیک زمانی مسئولیت‌های حسابرس در رهنمودهای استانداردهای حسابرسی")
    
    w10 = Inches(3.7)
    h10 = Inches(4.8)
    
    # Period 1 (Rightmost)
    p1 = create_card(s10, Inches(8.8), Inches(1.8), w10, h10, ACCENT_EMERALD)
    tf = p1.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "مقطع اول:\nتا تاریخ گزارش حسابرس", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "بازه: از تاریخ ترازنامه تا پایان عملیات میدانی", font_size=Pt(11), bold=True, color=ACCENT_EMERALD, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- نوع مسئولیت: مسئولیت فعالانه [Active]", font_size=Pt(12), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- حسابرس موظف است روش‌های خاصی برای کسب شواهد کافی و قابل قبول جهت شناسایی رویدادها اجرا نماید.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- شامل بررسی رویه‌ها، صورتجلسات، صورت‌های میان‌دوره‌ای، آزمون انقطاع و پرس‌وجو از مدیریت.", font_size=Pt(11), color=TEXT_MUTED)

    # Period 2 (Center)
    p2 = create_card(s10, Inches(4.8), Inches(1.8), w10, h10, ACCENT_AMBER)
    tf = p2.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "مقطع دوم:\nپس از گزارش تا انتشار صورت‌ها", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "بازه: از امضای گزارش تا انتشار عمومی", font_size=Pt(11), bold=True, color=ACCENT_AMBER, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- نوع مسئولیت: مسئولیت واکنشی [Passive]", font_size=Pt(12), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- حسابرس مسئولیت تجسس فعال ندارد؛ مسئولیت اطلاع‌رسانی بر عهده مدیریت واحد تجاری است.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- در صورت آگاهی از حقایق بااهمیت، حسابرس مکلف به اقدام فوری (اصلاح یا تغییر نظر گزارش) است.", font_size=Pt(11), color=TEXT_MUTED)

    # Period 3 (Leftmost)
    p3 = create_card(s10, Inches(0.8), Inches(1.8), w10, h10, ACCENT_ROSE)
    tf = p3.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.25)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "مقطع سوم:\nپس از انتشار عمومی صورت‌ها", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "بازه: پس از انتشار عمومی و دردسترس بودن", font_size=Pt(11), bold=True, color=ACCENT_ROSE, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- نوع مسئولیت: حقایق کشف شده بعدی", font_size=Pt(12), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- حسابرس وظیفه پرس‌وجو ندارد مگر حقایقی کشف شود که در تاریخ گزارش وجود داشته است.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- اقدامات: صدور گزارش تجدیدنظر شده با بند تأکید بر مطلب خاص یا سلب اتکا از گزارش در صورت عدم همکاری.", font_size=Pt(11), color=TEXT_MUTED)

    add_footer(s10, 10)

    # ==========================================
    # SLIDE 11: Audit Procedures up to Report Date
    # ==========================================
    s11 = prs.slides.add_slide(blank_layout)
    add_background(s11, BG_LIGHT)
    add_header(s11, "بخش چهارم: روش‌های رسیدگی", "مرحله اول: روش‌های رسیدگی تا تاریخ گزارش حسابرس", "اقدامات ضروری حسابرس در نزدیک‌ترین زمان ممکن به پایان عملیات میدانی")
    
    b1 = create_card(s11, Inches(6.8), Inches(1.8), grid_w, grid_h, ACCENT_CYAN)
    tf = b1.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۱. بررسی رویه‌های مدیریت و کنترل‌ها", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "بررسی روش‌های برقرار شده توسط مدیریت برای حصول اطمینان از شناسایی به‌موقع رویدادهای پس از تاریخ ترازنامه.", font_size=Pt(11.5), color=TEXT_DARK)

    b2 = create_card(s11, Inches(0.8), Inches(1.8), grid_w, grid_h, ACCENT_EMERALD)
    tf = b2.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۲. مطالعه و بررسی صورتجلسات رسمی", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "مطالعه صورتجلسات مجامع عمومی صاحبان سهام، جلسات هیئت مدیره و کمیته‌های هیئت مدیره (کمیته حسابرسی) و کاوش در جلسات نهایی.", font_size=Pt(11.5), color=TEXT_DARK)

    b3 = create_card(s11, Inches(6.8), Inches(4.35), grid_w, grid_h, ACCENT_AMBER)
    tf = b3.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۳. بررسی صورت‌های میان‌دوره‌ای و بودجه‌ها", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "مطالعه آخرین صورت‌های مالی میان‌دوره‌ای و مقایسه با صورت‌های حسابرسی شده، بودجه‌ها و جریان‌های وجوه نقد برآوردی.", font_size=Pt(11.5), color=TEXT_DARK)

    b4 = create_card(s11, Inches(0.8), Inches(4.35), grid_w, grid_h, ACCENT_INDIGO)
    tf = b4.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.25)
    tf.margin_top = Inches(0.2)
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "۴. بررسی ثبت‌های حسابداری و آزمون انقطاع", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "بررسی ثبت‌های اساسی دفاتر روزنامه و کل، پرداخت‌ها و دریافت‌های نقدی تا آخرین روز کار میدانی و اجرای آزمون انقطاع زمانی [Cut-off].", font_size=Pt(11.5), color=TEXT_DARK)

    add_footer(s11, 11)

    # ==========================================
    # SLIDE 12: Management Inquiries and Representation Letter
    # ==========================================
    s12 = prs.slides.add_slide(blank_layout)
    add_background(s12, BG_LIGHT)
    add_header(s12, "بخش چهارم: روش‌های رسیدگی", "پرس‌وجوهای کلیدی از مدیریت و اخذ تأییدیه مدیران", "چک‌لیست پرس‌وجو از مدیریت و الزامات تأییدیه کتبی [Representation Letter]")
    
    # Left Card: Detailed Inquiries Checklist (w=7.333), Right Card: Representation Letter (w=4.1)
    c_inq = create_card(s12, Inches(5.2), Inches(1.8), Inches(7.333), Inches(4.8), ACCENT_TEAL)
    tf_inq = c_inq.text_frame
    tf_inq.word_wrap = True
    tf_inq.margin_left = tf_inq.margin_right = Inches(0.3)
    tf_inq.margin_top = Inches(0.2)
    
    p = tf_inq.paragraphs[0]
    apply_rtl_and_font(p, "محورهای کلیدی پرس‌وجو از مدیریت واحد مورد رسیدگی:", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
    
    inquiries_text = [
        "- تعهدات، استقراض‌ها، ضمانت‌نامه‌ها یا بدهی‌های احتمالی جدید ایجاد شده",
        "- ایجاد تغییرات قابل توجه در سرمایه، بدهی‌های بلندمدت یا سرمایه در گردش",
        "- تعدیلات غیرعادی یا تغییرات در برآوردهای حسابداری انجام‌شده پس از تاریخ ترازنامه",
        "- تغییر در روند فروش، هزینه‌ها، سود و قیمت مواد اولیه و ارزش جایگزینی موجودی‌ها",
        "- لغو سفارشات فروش یا متضرر شدن مشتریان اصلی پس از تاریخ حسابرسی",
        "- رویدادهای پیش‌بینی‌نشده (آتش‌سوزی، سرقت، خسارات طبیعی و دعاوی جدید)",
        "- فروش دارایی‌های غیرجاری، صدور سهام جدید یا ادغام و انحلال واحد تجاری",
        "- معاملات با اشخاص وابسته و رویدادهای مخدوش‌کننده «فرض تداوم فعالیت»"
    ]
    for inq in inquiries_text:
        p = tf_inq.add_paragraph()
        apply_rtl_and_font(p, inq, font_size=Pt(11), color=TEXT_DARK, space_after=Pt(3))

    c_rep = create_card(s12, Inches(0.8), Inches(1.8), Inches(4.1), Inches(4.8), ACCENT_AMBER)
    tf_rep = c_rep.text_frame
    tf_rep.word_wrap = True
    tf_rep.margin_left = tf_rep.margin_right = Inches(0.25)
    tf_rep.margin_top = Inches(0.25)
    
    p = tf_rep.paragraphs[0]
    apply_rtl_and_font(p, "تأییدیه کتبی مدیریت\n[Management Representation]", font_size=Pt(14), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf_rep.add_paragraph()
    apply_rtl_and_font(p, "- اخذ تأییدیه کتبی با امضای مدیر با دو هدف راهبردی صورت می‌گیرد:", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(4))
    p = tf_rep.add_paragraph()
    apply_rtl_and_font(p, "۱. تأکید بر اینکه مسئولیت صورت‌های مالی به عهده مدیریت است.\n۲. تهیه شواهد حسابرسی در مواردی که روش‌های عادی کفایت نمی‌کند.", font_size=Pt(11.5), bold=True, color=ACCENT_AMBER, space_after=Pt(8))
    
    p = tf_rep.add_paragraph()
    apply_rtl_and_font(p, "حسابرسان شعب و بخش‌های فرعی:", font_size=Pt(12.5), bold=True, color=TEXT_DARK, space_after=Pt(3))
    p = tf_rep.add_paragraph()
    apply_rtl_and_font(p, "در مواردی که اجزای واحد توسط حسابرس دیگر رسیدگی می‌شود، حسابرس اصلی باید روش‌های آنان را بررسی و تاریخ گزارش خود را هماهنگ نماید.", font_size=Pt(11), color=TEXT_MUTED)

    add_footer(s12, 12)

    # ==========================================
    # SLIDE 13: Phase 2 - Between Report Date and Issuance
    # ==========================================
    s13 = prs.slides.add_slide(blank_layout)
    add_background(s13, BG_LIGHT)
    add_header(s13, "بخش چهارم: روش‌های رسیدگی", "مرحله دوم: حقایق کشف شده پس از تاریخ گزارش و پیش از انتشار", "مسئولیت‌ها، نحوه برخورد با اصلاح مدیریت و ضمانت‌اجراهای قانونی حسابرس")
    
    c_p2_1 = create_card(s13, Inches(6.8), Inches(1.8), w6, h6, ACCENT_EMERALD)
    tf = c_p2_1.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "حالت اول: مدیریت صورت‌های مالی را اصلاح می‌کند", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- حسابرس نسبت به اجرای روش‌ها پس از تاریخ گزارش مسئولیتی ندارد؛ مسئولیت آگاه کردن حسابرس به عهده مدیریت است.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- در صورت اطلاع از حقایق بااهمیت، حسابرس ضرورت تعدیل را ارزیابی و موضوع را با مدیریت در میان می‌گذارد.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "اقدامات حسابرس در صورت اصلاح توسط مدیریت:", font_size=Pt(12.5), bold=True, color=ACCENT_EMERALD, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "۱. اجرای روش‌های حسابرسی لازم در شرایط موجود\n۲. صدور گزارش جدید درباره صورت‌های مالی اصلاح شده\n۳. تاریخ گزارش جدید نباید پیش از تاریخ تأیید صورت‌های اصلاحی باشد", font_size=Pt(11.5), color=TEXT_DARK)

    c_p2_2 = create_card(s13, Inches(0.8), Inches(1.8), w6, h6, ACCENT_ROSE)
    tf = c_p2_2.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "حالت دوم: خودداری مدیریت از انجام اصلاحات", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "چنانچه حسابرس به ضرورت اصلاح اعتقاد داشته باشد اما مدیریت از اصلاح صورت‌های مالی خودداری ورزد:", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "الف) اگر گزارش هنوز تسلیم نشده باشد:", font_size=Pt(12.5), bold=True, color=ACCENT_ROSE, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "حسابرس گزارش خود را تعدیل نموده و نظر مشروط [Qualified] یا مردود [Adverse] ارائه می‌کند.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(6))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "ب) اگر گزارش قبلاً به واحد تجاری ارائه شده باشد:", font_size=Pt(12.5), bold=True, color=ACCENT_ROSE, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- هشدار به ارکان اداره امور (هیئت مدیره) برای جلوگیری از انتشار صورت‌های مالی\n- در صورت انتشار، انجام اقدامات لازم جهت جلوگیری از اتکا به گزارش (اعلام به مجامع سهامداران، بورس اوراق بهادار، بانک‌ها و نهادهای قانونی با نظر وکیل).", font_size=Pt(11.5), color=TEXT_DARK)

    add_footer(s13, 13)

    # ==========================================
    # SLIDE 14: Phase 3 - Discovered After Issuance
    # ==========================================
    s14 = prs.slides.add_slide(blank_layout)
    add_background(s14, BG_LIGHT)
    add_header(s14, "بخش چهارم: روش‌های رسیدگی", "مرحله سوم: حقایق کشف شده پس از انتشار صورت‌های مالی", "رویه مواجهه با حقایق موجود در تاریخ گزارش که پس از انتشار کشف شده‌اند")
    
    c_p3_1 = create_card(s14, Inches(6.8), Inches(1.8), w6, h6, ACCENT_INDIGO)
    tf = c_p3_1.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "تجدیدنظر در صورت‌های مالی توسط مدیریت", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- شرط شمول: حقایقی کشف شود که در تاریخ گزارش حسابرس وجود داشته و اطلاع از آن‌ها موجب تغییر در گزارش می‌شده است.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "اقدامات حسابرس در صورت تصمیم مدیریت به تجدیدنظر:", font_size=Pt(12.5), bold=True, color=ACCENT_INDIGO, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "۱. بررسی اقدامات مدیریت جهت اطمینان از آگاه شدن تمام دریافت‌کنندگان قبلی\n۲. اجرای روش‌های حسابرسی لازم در آن شرایط\n۳. صدور گزارش جدید با درج «بند تأکید بر مطلب خاص»\n۴. اشاره به یادداشت همراه صورت‌ها و تشریح کامل علت تجدیدنظر", font_size=Pt(11.5), color=TEXT_DARK)

    c_p3_2 = create_card(s14, Inches(0.8), Inches(1.8), w6, h6, ACCENT_ROSE)
    tf = c_p3_2.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "امتناع مدیریت و استثنای گزارشگری", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "واکنش حسابرس در صورت عدم تجدیدنظر توسط مدیریت:", font_size=Pt(12.5), bold=True, color=ACCENT_ROSE, space_after=Pt(4))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- هشدار رسمی حسابرس به مسئولان اصلی واحد مورد رسیدگی (هیئت مدیره)\n- انجام اقدامات مقتضی جهت جلوگیری از هرگونه اتکا به گزارش حسابرس در آینده (بر اساس اختیارات قانونی و توصیه مشاور حقوقی).", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(8))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "استثنای کاربردی در استانداردهای حسابرسی:", font_size=Pt(12.5), bold=True, color=TEXT_DARK, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "در صورت مشخص و نزدیک بودن زمان انتشار صورت‌های مالی دوره بعد، تجدیدنظر در صورت‌های قبلی به شرطی ضرورت ندارد که افشای مناسب موضوع در صورت‌های دوره بعد انجام گیرد.", font_size=Pt(11.5), bold=True, color=ACCENT_AMBER)

    add_footer(s14, 14)

    # ==========================================
    # SLIDE 15: Dual Dating of Audit Report
    # ==========================================
    s15 = prs.slides.add_slide(blank_layout)
    add_background(s15, BG_LIGHT)
    add_header(s15, "بخش پنجم: تاریخ‌گذاری دوگانه", "تاریخ‌گذاری دوگانه گزارش حسابرسی [Dual Dating]", "رویکردی هوشمندانه برای تحدید مسئولیت حسابرس در قبال یک رویداد خاص")
    
    c_dd_1 = create_card(s15, Inches(6.8), Inches(1.8), w6, h6, ACCENT_TEAL)
    tf = c_dd_1.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "مفهوم و نمونه کاربردی تاریخ‌گذاری دوگانه", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- قاعده عمومی: تاریخ گزارش حسابرس اصولاً برابر با تاریخ پایان عملیات میدانی است و مسئولیت رسیدگی فعال تا آن تاریخ پایان می‌یابد.", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- سناریو: اگر پس از اتمام رسیدگی، رویدادی خاص (مثلاً حل‌وفصل دعوای حقوقی در ۱۱ تیر) به اطلاع حسابرس برسد و در یادداشت‌ها منعکس شود:", font_size=Pt(12), color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "فرمت استاندارد تاریخ‌گذاری دوگانه:", font_size=Pt(12.5), bold=True, color=ACCENT_TEAL, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "«۳ تیر ماه، به استثنای یادداشت شماره X که تاریخ آن ۱۲ تیر ماه است.»", font_size=Pt(13.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "این متن بیان می‌کند که حسابرس نسبت به سایر رویدادها پس از ۳ تیر مسئولیتی ندارد و فقط مسئولیت بند X تا ۱۲ تیر گسترش یافته است.", font_size=Pt(11.5), color=TEXT_MUTED)

    c_dd_2 = create_card(s15, Inches(0.8), Inches(1.8), w6, h6, ACCENT_AMBER)
    tf = c_dd_2.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.3)
    tf.margin_top = Inches(0.25)
    
    p = tf.paragraphs[0]
    apply_rtl_and_font(p, "مقایسه راهبردی: تاریخ دوگانه در برابر تمدید کل تاریخ", font_size=Pt(14.5), bold=True, color=TEXT_DARK, space_after=Pt(6))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "گزینه اول: تاریخ‌گذاری دوگانه [Dual Dating]", font_size=Pt(12.5), bold=True, color=ACCENT_TEAL, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- مزیت اساسی: مسئولیت حسابرس صرفاً برای افشای همان یک قلم خاص تا دومین تاریخ گسترش می‌یابد.\n- عدم نیاز به تکرار روش‌های رسیدگی برای سایر اقلام و صرفه‌جویی بالا در زمان و ریسک حرفه‌ای.", font_size=Pt(11.5), color=TEXT_DARK, space_after=Pt(8))
    
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "گزینه دوم: تمدید تاریخ کل گزارش حسابرسی", font_size=Pt(12.5), bold=True, color=ACCENT_ROSE, space_after=Pt(3))
    p = tf.add_paragraph()
    apply_rtl_and_font(p, "- اگر حسابرس تاریخ کل گزارش را به ۱۲ تیر تغییر دهد:\n- مسئولیت قانونی حسابرس در قبال تمامی مندرجات صورت‌های مالی تا تاریخ جدید گسترش می‌یابد و او ملزم است تمام روش‌های رسیدگی را مجدداً تکرار کند.", font_size=Pt(11.5), color=TEXT_DARK)

    add_footer(s15, 15)

    # ==========================================
    # SLIDE 16: Comprehensive Summary Table & Matrix
    # ==========================================
    s16 = prs.slides.add_slide(blank_layout)
    add_background(s16, BG_LIGHT)
    add_header(s16, "بخش ششم: جمع‌بندی و نتیجه‌گیری", "ماتریس مقایسه‌ای و خلاصه تحلیلی رویدادها و وظایف حسابرس", "مرور جامع تفاوت‌های بنیادین، نوع افشا و سطح مسئولیت‌های حرفه‌ای")
    
    # Clean Table Shape
    table_shape = s16.shapes.add_table(5, 4, Inches(0.8), Inches(1.8), Inches(11.733), Inches(4.8))
    table = table_shape.table
    table.columns[0].width = Inches(2.2) # Feature
    table.columns[1].width = Inches(3.2) # Adjusting
    table.columns[2].width = Inches(3.2) # Non-Adjusting
    table.columns[3].width = Inches(3.133) # Auditor Duty
    
    headers = ["شاخص و ویژگی مقایسه", "رویدادهای تعدیلی [گروه اول]", "رویدادهای غیرتعدیلی [گروه دوم]", "وظایف و الزامات حسابرس"]
    for i, h_text in enumerate(headers):
        cell = table.cell(0, i)
        cell.fill.solid()
        cell.fill.fore_color.rgb = BG_DARK
        p = cell.text_frame.paragraphs[0]
        apply_rtl_and_font(p, h_text, font_size=Pt(11.5), bold=True, color=TEXT_LIGHT, align=PP_ALIGN.CENTER, space_after=Pt(0))
        
    rows_data = [
        ("منشأ و زمان شرایط", "شواهد درباره شرایط موجود در تاریخ ترازنامه", "شرایطی که تماماً پس از تاریخ ترازنامه حادث شده", "تشخیص دقیق ریشه زمانی رویداد با شواهد کافی"),
        ("نحوه برخورد حسابداری", "اصلاح و تعدیل ارقام در متن صورت‌های مالی اساسی", "عدم اصلاح ارقام؛ صرفاً افشا در یادداشت‌های پیوست", "اطمینان از کفایت افشا یا صحت ثبت سند تعدیلی"),
        ("تأثیر بر استفاده‌کنندگان", "برطرف‌کننده ابهام برآوردهای پایان دوره مالی", "فراهم‌کننده تصویر منصفانه از چشم‌انداز آینده", "جلوگیری از صدور نظر مقبول در صورت عدم اصلاح"),
        ("ابزار گزارشگری حسابرس", "صدور گزارش با ارقام اصلاح‌شده و تاریخ جدید", "بند تأکید بر مطلب خاص یا تاریخ‌گذاری دوگانه", "تحدید مسئولیت حرفه‌ای با تاریخ‌گذاری دوگانه")
    ]
    
    for row_idx, r_data in enumerate(rows_data, start=1):
        for col_idx, text in enumerate(r_data):
            cell = table.cell(row_idx, col_idx)
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD_BG if row_idx % 2 == 1 else RGBColor(241, 245, 249)
            p = cell.text_frame.paragraphs[0]
            is_bold = (col_idx == 0)
            text_color = ACCENT_INDIGO if col_idx == 0 else TEXT_DARK
            apply_rtl_and_font(p, text, font_size=Pt(11), bold=is_bold, color=text_color, align=PP_ALIGN.RIGHT, space_after=Pt(0))

    add_footer(s16, 16)

    # ==========================================
    # SLIDE 17: Closing Slide (Q&A and Gratitude)
    # ==========================================
    s17 = prs.slides.add_slide(blank_layout)
    add_background(s17, BG_DARK)
    
    bg_decor17 = s17.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(1.5), Inches(1.0), Inches(10.333), Inches(5.5))
    bg_decor17.fill.solid()
    bg_decor17.fill.fore_color.rgb = BG_CARD_DARK
    bg_decor17.line.color.rgb = RGBColor(51, 65, 85)
    
    tf17 = bg_decor17.text_frame
    tf17.word_wrap = True
    
    p = tf17.paragraphs[0]
    apply_rtl_and_font(p, "با سپاس و قدردانی فراوان", font_size=Pt(32), bold=True, color=TEXT_LIGHT, align=PP_ALIGN.CENTER, space_after=Pt(8))
    
    p = tf17.add_paragraph()
    apply_rtl_and_font(p, "از توجه و راهنمایی‌های ارزشمند استاد گرانقدر:", font_size=Pt(18), bold=False, color=TEXT_LIGHT_MUTED, align=PP_ALIGN.CENTER, space_after=Pt(4))
    
    p = tf17.add_paragraph()
    apply_rtl_and_font(p, "جناب استاد بهرامیان", font_size=Pt(28), bold=True, color=RGBColor(253, 224, 71), align=PP_ALIGN.CENTER, space_after=Pt(6))
    
    p = tf17.add_paragraph()
    apply_rtl_and_font(p, "و همراهی شما همکلاسی‌های ارجمند", font_size=Pt(16), bold=False, color=TEXT_LIGHT, align=PP_ALIGN.CENTER, space_after=Pt(10))
    
    p = tf17.add_paragraph()
    apply_rtl_and_font(p, "________________________", font_size=Pt(16), bold=False, color=RGBColor(71, 85, 105), align=PP_ALIGN.CENTER, space_after=Pt(10))
    
    p = tf17.add_paragraph()
    apply_rtl_and_font(p, "بخش پرسش و پاسخ [Q & A]", font_size=Pt(20), bold=True, color=RGBColor(56, 189, 248), align=PP_ALIGN.CENTER, space_after=Pt(4))
    
    p = tf17.add_paragraph()
    apply_rtl_and_font(p, "مشتاق شنیدن نظرات، دیدگاه‌ها و سوالات شما عزیزان هستیم", font_size=Pt(13), bold=False, color=TEXT_LIGHT_MUTED, align=PP_ALIGN.CENTER)

    # Save Presentation
    prs.save(output_path)
    eng_path = os.path.join(os.path.dirname(output_path), "Events_After_Balance_Sheet_Date.pptx")
    prs.save(eng_path)
    print("Presentation saved successfully!")

if __name__ == '__main__':
    out_dir = r"c:\Users\Sadeghi\OneDrive\Desktop\New folder (7)"
    out_file = os.path.join(out_dir, "رویدادهای_بعد_از_تاریخ_ترازنامه.pptx")
    create_presentation(out_file)

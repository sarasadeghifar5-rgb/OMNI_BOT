import base64
import io
import math
from typing import Tuple, Optional, Dict, Any, List
from PIL import Image, ExifTags
import numpy as np
import cv2

class VisionService:
    """
    Image processing and multimodal utilities:
    - Downscaling/compressing images to optimal sizes
    - Generating standard Data URL Base64 strings
    - Formatting multimodal user messages for LLM APIs
    """
    @staticmethod
    def process_and_encode_image(
        file_bytes: bytes,
        mime_type: str = "image/jpeg",
        max_dimension: int = 1536,
        quality: int = 85
    ) -> Tuple[str, int, int]:
        """
        Resize image if larger than max_dimension and return base64 data url.
        """
        try:
            image = Image.open(io.BytesIO(file_bytes))
            # Convert RGBA or CMYK to RGB if saving as JPEG
            if image.mode in ("RGBA", "P") and "jpeg" in mime_type.lower():
                image = image.convert("RGB")
            elif image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGB")

            # Check if resizing is needed
            width, height = image.size
            if max(width, height) > max_dimension:
                scale = max_dimension / max(width, height)
                new_width = int(width * scale)
                new_height = int(height * scale)
                image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                width, height = new_width, new_height

            output_buffer = io.BytesIO()
            format_to_save = "JPEG" if "jpeg" in mime_type.lower() or "jpg" in mime_type.lower() else "PNG"
            image.save(output_buffer, format=format_to_save, quality=quality, optimize=True)
            encoded = base64.b64encode(output_buffer.getvalue()).decode("utf-8")
            
            data_url = f"data:{mime_type};base64,{encoded}"
            return data_url, width, height
        except Exception as e:
            # Fallback to direct raw base64 if Pillow processing encounters issues
            encoded = base64.b64encode(file_bytes).decode("utf-8")
            return f"data:{mime_type};base64,{encoded}", 0, 0

    @staticmethod
    def build_multimodal_message(text: str, image_data_urls: List[str]) -> Dict[str, Any]:
        """
        Builds a standard OpenAI/Anthropic multimodal user message.
        """
        if not image_data_urls:
            return {"role": "user", "content": text}

        content_parts = []
        # Add text prompt first
        if text:
            content_parts.append({"type": "text", "text": text})

        # Add images
        for url in image_data_urls:
            content_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": url,
                    "detail": "auto"
                }
            })

        return {"role": "user", "content": content_parts}

    @classmethod
    def analyze_image_features(cls, data_url_or_bytes: Any) -> Dict[str, Any]:
        """
        Extract physical, visual, structural, and chromatic features from an image
        using local Computer Vision (PIL + OpenCV + NumPy) without requiring any external API key.
        """
        try:
            if isinstance(data_url_or_bytes, str):
                if "," in data_url_or_bytes:
                    b64data = data_url_or_bytes.split(",", 1)[1]
                else:
                    b64data = data_url_or_bytes
                raw_bytes = base64.b64decode(b64data)
            else:
                raw_bytes = data_url_or_bytes

            pil_img = Image.open(io.BytesIO(raw_bytes))
            rgb_img = pil_img.convert("RGB")
            width, height = rgb_img.size

            # Aspect Ratio calculation
            gcd_val = math.gcd(width, height)
            ratio_w, ratio_h = width // gcd_val, height // gcd_val
            if abs(width / height - 16 / 9) < 0.05:
                ratio_str = "16:9 (عریض سینمایی)"
            elif abs(width / height - 4 / 3) < 0.05:
                ratio_str = "4:3 (استاندارد)"
            elif abs(width / height - 1.0) < 0.05:
                ratio_str = "1:1 (مربع)"
            elif abs(width / height - 9 / 16) < 0.05:
                ratio_str = "9:16 (عمودی / استوری)"
            else:
                ratio_str = f"{ratio_w}:{ratio_h}"

            orientation = "افقی (Landscape)" if width > height else ("عمودی (Portrait)" if height > width else "مربع (Square)")
            megapixels = round((width * height) / 1_000_000, 2)

            # Dominant Colors (quantize to 5 colors)
            small_for_colors = rgb_img.resize((150, 150))
            quantized = small_for_colors.quantize(colors=5, method=2).convert("RGB")
            color_counts = quantized.getcolors(maxcolors=30000) or []
            total_pixels = sum(c[0] for c in color_counts) or 1

            dominant_colors = []
            for count, (r, g, b) in sorted(color_counts, reverse=True, key=lambda x: x[0])[:4]:
                pct = round((count / total_pixels) * 100, 1)
                hex_code = f"#{r:02x}{g:02x}{b:02x}".upper()
                name = cls._get_persian_color_name(r, g, b)
                dominant_colors.append({
                    "hex": hex_code,
                    "rgb": (r, g, b),
                    "percentage": pct,
                    "name": name
                })

            # OpenCV Image Metrics
            np_arr = np.frombuffer(raw_bytes, np.uint8)
            cv_img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

            brightness_val = 128.0
            contrast_val = 50.0
            sharpness_val = 100.0
            edge_density = 5.0

            if cv_img is not None:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                brightness_val = float(np.mean(gray))
                contrast_val = float(np.std(gray))
                sharpness_val = float(cv2.Laplacian(gray, cv2.CV_64F).var())

                # Canny Edge Detection
                edges = cv2.Canny(gray, 100, 200)
                edge_density = float((np.count_nonzero(edges) / edges.size) * 100)

            # Brightness assessment
            if brightness_val < 70:
                bright_label = "تاریک و کم‌نور (Low-Key)"
            elif brightness_val > 185:
                bright_label = "بسیار روشن (High-Key)"
            else:
                bright_label = "متوازن و استاندارد"

            # Contrast assessment
            if contrast_val < 35:
                contrast_label = "ملایم با کنتراست پایین"
            elif contrast_val > 65:
                contrast_label = "کنتراست بالا و تفکیک برجسته"
            else:
                contrast_label = "کنتراست طبیعی و متعادل"

            # Sharpness assessment
            if sharpness_val > 150:
                sharp_label = "بسیار واضح و شارپ (High Definition)"
            elif sharpness_val < 40:
                sharp_label = "فوکوس ملایم یا دارای تاری (Soft / Bokeh)"
            else:
                sharp_label = "وضوح نرمال"

            # Complexity & Structure
            if edge_density > 14:
                struct_label = "پرجزئیات و بافت‌دار (تصویر پیچیده یا حاوی متن/طرح)"
            elif edge_density < 3.5:
                struct_label = "مینیمال با پس‌زمینه یکدست یا گرافیک ساده"
            else:
                struct_label = "طبیعی با توزیع متعادل عناصر"

            # Semantic Scene Heuristics
            scene_type = "عکس یا تصویر دیجیتال با کنتراست متعادل"
            if brightness_val < 85 and edge_density < 6.0:
                scene_type = "تصویر پس‌زمینه تیره (Dark Mode / Minimalist UI) با المان‌های متمرکز، لوگو یا متن روشن"
            elif brightness_val > 180 and edge_density < 6.0:
                scene_type = "طرح با تم روشن، سند متنی، فرم یا رابط کاربری وب (Light Mode)"
            elif edge_density > 13.0:
                scene_type = "تصویر یا سند بسیار پرجزئیات، بافت‌دار یا حاوی بلوک‌های متنی/نموداری متراکم"
            elif brightness_val > 80 and contrast_val > 45:
                scene_type = "عکس محیطی یا منظره طبیعی با طیف نوری گسترده و تفکیک رنگی بالا"

            # EXIF extraction
            exif_data = {}
            if hasattr(pil_img, "_getexif") and pil_img._getexif():
                raw_exif = pil_img._getexif()
                for tag_id, val in raw_exif.items():
                    tag_name = ExifTags.TAGS.get(tag_id, tag_id)
                    if tag_name in ("Make", "Model", "DateTime", "ExposureTime", "FNumber", "ISOSpeedRatings"):
                        exif_data[tag_name] = str(val)

            return {
                "width": width,
                "height": height,
                "megapixels": megapixels,
                "aspect_ratio": ratio_str,
                "orientation": orientation,
                "scene_type": scene_type,
                "dominant_colors": dominant_colors,
                "brightness": {
                    "score": round(brightness_val, 1),
                    "label": bright_label
                },
                "contrast": {
                    "score": round(contrast_val, 1),
                    "label": contrast_label
                },
                "sharpness": {
                    "score": round(sharpness_val, 1),
                    "label": sharp_label
                },
                "complexity": {
                    "edge_density": round(edge_density, 1),
                    "label": struct_label
                },
                "exif": exif_data
            }
        except Exception as e:
            return {
                "error": str(e),
                "width": 0,
                "height": 0,
                "megapixels": 0,
                "aspect_ratio": "نامشخص",
                "orientation": "نامشخص",
                "dominant_colors": [],
                "brightness": {"score": 0, "label": "نامشخص"},
                "contrast": {"score": 0, "label": "نامشخص"},
                "sharpness": {"score": 0, "label": "نامشخص"},
                "complexity": {"edge_density": 0, "label": "نامشخص"},
                "exif": {}
            }

    @classmethod
    def format_vision_report(cls, analysis: Dict[str, Any]) -> str:
        """
        Formats computer vision analysis into a clean markdown card.
        """
        if not analysis or analysis.get("width", 0) == 0:
            return ""

        w = analysis.get("width", 0)
        h = analysis.get("height", 0)
        mp = analysis.get("megapixels", 0)
        ratio = analysis.get("aspect_ratio", "")
        orient = analysis.get("orientation", "")
        colors = analysis.get("dominant_colors", [])
        bright = analysis.get("brightness", {})
        contrast = analysis.get("contrast", {})
        sharp = analysis.get("sharpness", {})
        comp = analysis.get("complexity", {})
        exif = analysis.get("exif", {})

        color_str_list = [f"`{c['hex']}` ({c['name']} - {c['percentage']}%)" for c in colors]
        colors_display = "، ".join(color_str_list) if color_str_list else "غیرقابل تشخیص"

        report = [
            "### 🖼️ مشخصات ساختاری و بصری استخراج‌شده از تصویر:",
            f"- **ابعاد و رزولوشن:** {w} × {h} پیکسل ({mp} مگاپیکسل)",
            f"- **نسبت تصویر و حالت:** نسبت {ratio} | جهت: {orient}",
            f"- **پالت رنگ‌های شاخص:** {colors_display}",
            f"- **نورپردازی و کنتراست:** {bright.get('label', '')} (روشنایی {bright.get('score', 0)}/255) | {contrast.get('label', '')}",
            f"- **کیفیت و وضوح فوکوس:** {sharp.get('label', '')}",
            f"- **تراکم بافت و خطوط:** {comp.get('label', '')} (تراکم لبه‌ها: {comp.get('edge_density', 0)}%)",
        ]

        if exif:
            exif_parts = []
            if "Make" in exif or "Model" in exif:
                exif_parts.append(f"دستگاه: {exif.get('Make', '')} {exif.get('Model', '')}".strip())
            if "DateTime" in exif:
                exif_parts.append(f"تاریخ ثبت: {exif['DateTime']}")
            if exif_parts:
                report.append(f"- **اطلاعات دوربین (EXIF):** {' | '.join(exif_parts)}")

        return "\n".join(report)

    @staticmethod
    def _get_persian_color_name(r: int, g: int, b: int) -> str:
        """
        Determines human-friendly Persian name for an RGB color.
        """
        mx = max(r, g, b)
        mn = min(r, g, b)
        diff = mx - mn

        if mx < 35:
            return "مشکی / تیره"
        if mn > 225:
            return "سفید خالص"
        if diff < 22:
            return "خاکستری تیره" if mx < 120 else ("خاکستری روشن" if mx < 190 else "نقره‌ای / شیری")

        if r > 160 and g < 90 and b < 90:
            return "قرمز درخشان"
        if r > 190 and g > 110 and b < 60:
            return "نارنجی گرم"
        if r > 180 and g > 180 and b < 80:
            return "زرد طلایی"
        if g > max(r, b) + 18:
            return "سبز زمردی" if g < 150 else "سبز روشن"
        if b > max(r, g) + 18:
            if g > 130:
                return "فیروزه‌ای / آبی آسمانی"
            return "آبی / لاجوردی"
        if r > 125 and b > 125 and g < 110:
            return "بنفش / ارغوانی"
        if r > 170 and g > 100 and b > 140:
            return "صورتی"
        if r > 90 and g > 50 and b < 50:
            return "قهوه‌ای"

        return "رنگ ترکیبی"

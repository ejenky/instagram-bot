import re
"""
Instagram Content Processor Telegram Bot - v2
Styled like @clips, @lmaoys, @laxative viral formats
"""

import os
import logging
import asyncio
import subprocess
import tempfile
import json
import random
import string
from datetime import datetime
from typing import Optional, Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ConversationHandler, ContextTypes, filters
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
WATERMARK_IMAGE_PATH = os.getenv('WATERMARK_PATH', '/app/assets/watermark.png')
DEFAULT_WATERMARK_TEXT = os.getenv('DEFAULT_WATERMARK', '@yourusername')
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
PRESETS_FILE = os.path.join(DATA_DIR, 'filter_presets.json')

# Instagram Reels dimensions
REEL_WIDTH = 1080
REEL_HEIGHT = 1920

# Conversation states
(WAITING_FOR_CONTENT, CHOOSE_CROP, CHOOSE_MODE, ENTER_TEXT, CONFIRM_TEXT,
 CHOOSE_WATERMARK, ENTER_WATERMARK_TEXT, CHOOSE_FILTER, 
 MANAGE_PRESETS, CREATE_PRESET) = range(10)


def detect_content_region(video_path):
    """Detect actual video content area, excluding text bars and overlays"""
    import subprocess
    import json

    # Get video dimensions
    probe = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', video_path
    ], capture_output=True, text=True)

    try:
        data = json.loads(probe.stdout)
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                width = stream.get('width', 0)
                height = stream.get('height', 0)
                break
        else:
            return None
    except:
        return None

    if width == 0 or height == 0:
        return None

    # Use ffmpeg cropdetect to find content area (handles black bars)
    result = subprocess.run([
        'ffmpeg', '-i', video_path, '-vframes', '30', '-vf',
        'cropdetect=24:16:0', '-f', 'null', '-'
    ], capture_output=True, text=True, timeout=30)

    # Parse cropdetect output for most common crop value
    crop_lines = re.findall(r'crop=(\d+):(\d+):(\d+):(\d+)', result.stderr)
    if crop_lines:
        # Get the last (most stable) crop detection
        w, h, x, y = map(int, crop_lines[-1])
        # Only return crop if it's significantly different (>5% cropped)
        if h < height * 0.95 or w < width * 0.95:
            return {'w': w, 'h': h, 'x': x, 'y': y, 'orig_w': width, 'orig_h': height}

    return None


def detect_text_overlay_region(video_path):
    """
    Smart detection of text overlay regions by comparing edge colors between rows.
    Text overlays have consistent background colors at the edges across multiple rows.
    Returns crop coordinates to remove these regions.
    """
    import subprocess
    import json
    import tempfile
    import os

    # Get video dimensions
    probe = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', video_path
    ], capture_output=True, text=True)

    try:
        data = json.loads(probe.stdout)
        for stream in data.get('streams', []):
            if stream.get('codec_type') == 'video':
                width = stream.get('width', 0)
                height = stream.get('height', 0)
                break
        else:
            return None
    except:
        return None

    if width == 0 or height == 0:
        return None

    with tempfile.NamedTemporaryFile(suffix='.ppm', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Extract frame, skip 0.5s to avoid black intro
        subprocess.run([
            'ffmpeg', '-y', '-ss', '0.5', '-i', video_path, '-vframes', '1',
            '-f', 'image2', tmp_path
        ], capture_output=True, timeout=30)

        if not os.path.exists(tmp_path):
            return None

        with open(tmp_path, 'rb') as f:
            header = f.readline()
            line = f.readline()
            while line.startswith(b'#'):
                line = f.readline()
            dims = line.decode().strip().split()
            if len(dims) < 2:
                return None
            img_w, img_h = int(dims[0]), int(dims[1])
            f.readline()
            pixels = f.read()

        if len(pixels) < img_w * img_h * 3:
            return None

        def get_edge_avg_color(y_pos):
            """Get average color from left and right edges of a row"""
            start = y_pos * img_w * 3
            row = pixels[start:start + img_w * 3]
            if len(row) < img_w * 3:
                return None

            # Sample 30 pixels from each edge
            colors = []
            for i in range(30):
                # Left edge
                idx = i * 3
                if idx + 2 < len(row):
                    colors.append((row[idx], row[idx+1], row[idx+2]))
                # Right edge
                idx = (img_w - 1 - i) * 3
                if idx + 2 < len(row):
                    colors.append((row[idx], row[idx+1], row[idx+2]))

            if not colors:
                return None

            return (
                sum(c[0] for c in colors) / len(colors),
                sum(c[1] for c in colors) / len(colors),
                sum(c[2] for c in colors) / len(colors)
            )

        def colors_similar(c1, c2, threshold=45):
            """Check if two colors are similar"""
            if not c1 or not c2:
                return False
            return all(abs(c1[i] - c2[i]) < threshold for i in range(3))

        # Get reference color from very top
        ref_top_color = get_edge_avg_color(5)

        # Find where top text overlay ends
        top_crop = 0
        if ref_top_color:
            for y in range(10, min(img_h // 2, 800)):
                curr_color = get_edge_avg_color(y)
                if not colors_similar(ref_top_color, curr_color):
                    top_crop = y
                    break

        # Get reference color from very bottom
        ref_bottom_color = get_edge_avg_color(img_h - 5)

        # Find where bottom text overlay starts
        bottom_crop = img_h
        if ref_bottom_color:
            for y in range(img_h - 10, max(img_h // 2, 200), -1):
                curr_color = get_edge_avg_color(y)
                if not colors_similar(ref_bottom_color, curr_color):
                    bottom_crop = y
                    break

        content_height = bottom_crop - top_crop
        top_percent = top_crop / img_h
        bottom_percent = (img_h - bottom_crop) / img_h

        # Crop if we found overlay regions (>2% of frame)
        if (top_percent > 0.02 or bottom_percent > 0.02) and content_height > img_h * 0.3:
            scale_y = height / img_h
            logger.info(f"Smart crop: top={top_crop}px ({top_percent*100:.1f}%), bottom={img_h-bottom_crop}px ({bottom_percent*100:.1f}%)")
            return {
                'w': width,
                'h': int(content_height * scale_y),
                'x': 0,
                'y': int(top_crop * scale_y),
                'orig_w': width,
                'orig_h': height,
                'top_crop': int(top_crop * scale_y),
                'bottom_crop': int((img_h - bottom_crop) * scale_y)
            }

        return None

    except Exception as e:
        logger.warning(f"Text overlay detection failed: {e}")
        return None
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


class PresetManager:
    DEFAULT_PRESETS = {
        "vibrant": {"name": "Vibrant", "description": "Boosted saturation and contrast", "filters": {"saturation": 1.4, "contrast": 1.2, "brightness": 1.05}},
        "muted": {"name": "Muted", "description": "Subtle, desaturated look", "filters": {"saturation": 0.7, "contrast": 0.95, "brightness": 1.0}},
        "warm": {"name": "Warm", "description": "Warm orange tones", "filters": {"saturation": 1.1, "contrast": 1.1, "brightness": 1.02, "temperature": 30}},
        "cool": {"name": "Cool", "description": "Cool blue tones", "filters": {"saturation": 1.05, "contrast": 1.1, "brightness": 1.0, "temperature": -30}},
        "high_contrast": {"name": "High Contrast", "description": "Punchy blacks and whites", "filters": {"saturation": 1.1, "contrast": 1.4, "brightness": 1.0}},
        "faded": {"name": "Faded", "description": "Lifted blacks, vintage feel", "filters": {"saturation": 0.85, "contrast": 0.85, "brightness": 1.05, "black_point": 30}},
        "none": {"name": "No Filter", "description": "Original image", "filters": {}}
    }
    
    def __init__(self, presets_file: str):
        self.presets_file = presets_file
        self.presets = self._load_presets()
    
    def _load_presets(self) -> Dict:
        presets = self.DEFAULT_PRESETS.copy()
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r') as f:
                    presets.update(json.load(f))
            except Exception as e:
                logger.error(f"Error loading presets: {e}")
        return presets
    
    def save_presets(self):
        os.makedirs(os.path.dirname(self.presets_file), exist_ok=True)
        custom = {k: v for k, v in self.presets.items() if k not in self.DEFAULT_PRESETS}
        with open(self.presets_file, 'w') as f:
            json.dump(custom, f, indent=2)
    
    def add_preset(self, key: str, name: str, description: str, filters: Dict):
        self.presets[key] = {"name": name, "description": description, "filters": filters}
        self.save_presets()
    
    def delete_preset(self, key: str) -> bool:
        if key in self.DEFAULT_PRESETS:
            return False
        if key in self.presets:
            del self.presets[key]
            self.save_presets()
            return True
        return False
    
    def get_preset(self, key: str) -> Optional[Dict]:
        return self.presets.get(key)
    
    def list_presets(self) -> Dict:
        return self.presets


class MediaProcessor:
    def __init__(self, temp_dir: str, preset_manager: PresetManager):
        self.temp_dir = temp_dir
        self.preset_manager = preset_manager
    
    def _random_str(self, length: int = 8) -> str:
        return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    
    async def download_video(self, url: str) -> str:
        rand = self._random_str()
        output_template = os.path.join(self.temp_dir, f'input_{rand}.%(ext)s')

        # Enhanced yt-dlp options for better compatibility with X/Twitter
        cmd = [
            'yt-dlp',
            '--no-warnings',
            '-f', 'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            '--merge-output-format', 'mp4',
            '-o', output_template,
            '--no-playlist',
            '--no-check-certificates',
            '--retries', '3',
            '--fragment-retries', '3',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--extractor-args', 'twitter:api=syndication',
            url
        ]

        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode() if stderr else "Unknown error"
            logger.error(f"yt-dlp failed: {error_msg}")
            raise Exception(f"Download failed. Check the link is valid and public.")

        for f in os.listdir(self.temp_dir):
            if f.startswith(f'input_{rand}'):
                return os.path.join(self.temp_dir, f)
        raise Exception("Downloaded file not found")
    
    def get_media_info(self, path: str) -> Dict:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_format', '-show_streams', path]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            info = json.loads(result.stdout)
        except:
            return {'width': 0, 'height': 0, 'duration': 0, 'is_video': False, 'has_audio': False}
        video_stream = next((s for s in info.get('streams', []) if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in info.get('streams', []) if s['codec_type'] == 'audio'), None)
        if video_stream:
            rotation = int(video_stream.get('tags', {}).get('rotate', 0))
            w, h = int(video_stream.get('width', 0)), int(video_stream.get('height', 0))
            if rotation in [90, 270]:
                w, h = h, w
            duration = float(info.get('format', {}).get('duration', 0))
            return {'width': w, 'height': h, 'duration': duration, 'is_video': audio_stream is not None or duration > 0, 'has_audio': audio_stream is not None}
        return {'width': 0, 'height': 0, 'duration': 0, 'is_video': False, 'has_audio': False}
    
    def _build_filter_eq(self, filters: Dict) -> Optional[str]:
        parts = []
        sat = filters.get('saturation', 1.0)
        con = filters.get('contrast', 1.0)
        bri = filters.get('brightness', 1.0)
        if sat != 1.0 or con != 1.0 or bri != 1.0:
            parts.append(f"eq=contrast={con}:brightness={bri-1.0}:saturation={sat}")
        temp = filters.get('temperature', 0)
        if temp != 0:
            if temp > 0:
                parts.append(f"colorbalance=rs={temp/100}:gs={temp/200}:bs=-{temp/100}")
            else:
                t = abs(temp)
                parts.append(f"colorbalance=rs=-{t/100}:gs=-{t/200}:bs={t/100}")
        bp = filters.get('black_point', 0)
        if bp > 0:
            parts.append(f"curves=m='0/{bp/255:.3f} 1/1'")
        return ','.join(parts) if parts else None
    
    async def process_video(self, input_path: str, output_path: str, crop_mode: str = 'smart',
                           top_text: Optional[str] = None, watermark_text: Optional[str] = None,
                           watermark_image: Optional[str] = None, dark_mode: bool = True,
                           filter_preset: Optional[str] = None) -> str:
        info = self.get_media_info(input_path)
        src_w, src_h = info['width'], info['height']
        if src_w == 0 or src_h == 0:
            raise Exception("Could not read video dimensions")

        # Smart crop: detect existing text overlays and crop them out
        text_region = None
        if crop_mode == 'smart':
            text_region = detect_text_overlay_region(input_path)
            if text_region:
                logger.info(f"Detected text overlay region: top={text_region.get('top_crop', 0)}px, bottom={text_region.get('bottom_crop', 0)}px")
                # Update source dimensions to the cropped region
                src_w = text_region['w']
                src_h = text_region['h']

        # Layout settings - VIRAL STYLE like @clips
        bg_color = "black" if dark_mode else "white"
        text_color = "white" if dark_mode else "black"

        filter_parts = []

        # Build initial video filter chain
        # First, apply smart crop to remove text overlays if detected
        if text_region:
            precrop = f"crop={text_region['w']}:{text_region['h']}:{text_region['x']}:{text_region['y']}"
            input_label = f"[0:v]{precrop}[precropped]"
            filter_parts.append(input_label)
            video_input = "[precropped]"
        else:
            video_input = "[0:v]"

        # Apply video filter if specified
        filter_eq = None
        if filter_preset and filter_preset != 'none':
            preset = self.preset_manager.get_preset(filter_preset)
            if preset:
                filter_eq = self._build_filter_eq(preset.get('filters', {}))

        # Calculate text area dynamically
        text_area_height = 0
        text_lines = []
        text_font_size = 58
        line_height = 78

        if top_text:
            # Clean text
            clean_text = ''.join(c if (32 <= ord(c) <= 126) else ' ' for c in top_text)
            clean_text = re.sub(r' {2,}', ' ', clean_text).strip()

            # Dynamic font size - @clips style (slightly smaller, cleaner)
            total_chars = len(clean_text)
            if total_chars <= 40:
                text_font_size = 58
                max_chars_per_line = 22
            elif total_chars <= 80:
                text_font_size = 50
                max_chars_per_line = 26
            elif total_chars <= 120:
                text_font_size = 44
                max_chars_per_line = 30
            else:
                text_font_size = 38
                max_chars_per_line = 34

            line_height = int(text_font_size * 1.4)

            # Word wrap
            words = clean_text.split()
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= max_chars_per_line:
                    current_line = (current_line + " " + word).strip()
                else:
                    if current_line:
                        text_lines.append(current_line)
                    current_line = word
            if current_line:
                text_lines.append(current_line)

            # Calculate text area: lines * line_height + padding
            text_area_height = len(text_lines) * line_height + 80  # 40px top + 40px bottom padding

        # Video positioning - @clips style: text close to video
        video_top_margin = text_area_height + 30 if top_text else 80
        video_bottom_margin = 80
        content_height = REEL_HEIGHT - video_top_margin - video_bottom_margin
        content_width = REEL_WIDTH - 40  # Minimal side margins

        # Scale video - ALWAYS use FIT mode when smart crop is applied to preserve content
        src_aspect = src_w / src_h
        target_aspect = content_width / content_height

        use_fit_mode = (crop_mode == 'fit') or (text_region is not None)

        if use_fit_mode:
            # Fit mode: show entire video, may have black bars on sides
            if src_aspect > target_aspect:
                # Video is wider - fit to width
                scaled_w = content_width
                scaled_h = int(content_width / src_aspect)
            else:
                # Video is taller - fit to height
                scaled_h = content_height
                scaled_w = int(content_height * src_aspect)
            # Ensure even dimensions
            scaled_w = scaled_w if scaled_w % 2 == 0 else scaled_w - 1
            scaled_h = scaled_h if scaled_h % 2 == 0 else scaled_h - 1
            scale_filter = f"scale={scaled_w}:{scaled_h}"
        else:
            # Crop mode: fill frame, crop excess
            if src_aspect > target_aspect:
                scale_h = content_height
                scale_w = int(src_w * (content_height / src_h))
            else:
                scale_w = content_width
                scale_h = int(src_h * (content_width / src_w))
            scale_w = scale_w if scale_w % 2 == 0 else scale_w - 1
            scale_h = scale_h if scale_h % 2 == 0 else scale_h - 1
            crop_x = (scale_w - content_width) // 2
            if crop_mode == 'top':
                crop_y = 0
            elif crop_mode == 'bottom':
                crop_y = scale_h - content_height
            else:
                crop_y = (scale_h - content_height) // 2
            scale_filter = f"scale={scale_w}:{scale_h},crop={content_width}:{content_height}:{crop_x}:{crop_y}"
            scaled_w = content_width
            scaled_h = content_height

        # Build video filter chain
        video_filters = scale_filter
        if filter_eq:
            video_filters = f"{filter_eq},{video_filters}"
        filter_parts.append(f"{video_input}{video_filters},setsar=1[scaled]")

        # Background
        filter_parts.append(f"color={bg_color}:{REEL_WIDTH}x{REEL_HEIGHT}:d=1,format=yuv420p[bg]")

        # Center video horizontally and vertically in its area
        overlay_x = (REEL_WIDTH - scaled_w) // 2
        overlay_y = video_top_margin + (content_height - scaled_h) // 2
        filter_parts.append(f"[bg][scaled]overlay={overlay_x}:{overlay_y}:shortest=0[canvas]")

        current = "[canvas]"

        # Add text - @clips style
        if top_text and text_lines:
            start_y = 40  # Start 40px from top

            for i, line in enumerate(text_lines):
                escaped_line = line.replace("'", "'\\''").replace(":", "\\:").replace("\\", "\\\\")
                line_y = start_y + (i * line_height)
                out_label = f"[txt{i}]"
                filter_parts.append(
                    f"{current}drawtext="
                    f"text='{escaped_line}':"
                    f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"fontsize={text_font_size}:"
                    f"fontcolor={text_color}:"
                    f"x=(w-text_w)/2:"
                    f"y={line_y}"
                    f"{out_label}"
                )
                current = out_label

            filter_parts.append(f"{current}null[texted]")
            current = "[texted]"

        # Watermark settings
        wm_font_size = 32
        wm_margin = 20
        wm_opacity = 0.85

        # Add watermark - inside video area
        if watermark_text:
            escaped_wm = watermark_text.replace("'", "'\\''").replace(":", "\\:")
            wm_y = overlay_y + 15
            filter_parts.append(
                f"{current}drawtext="
                f"text='{escaped_wm}':"
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"fontsize={wm_font_size}:"
                f"fontcolor=white@{wm_opacity}:"
                f"x=w-tw-{wm_margin}:"
                f"y={wm_y}:"
                f"shadowcolor=black@0.5:"
                f"shadowx=1:shadowy=1"
                f"[final]"
            )
        elif watermark_image and os.path.exists(watermark_image):
            filter_parts.append(f"[1:v]scale=100:-1,format=yuva420p,colorchannelmixer=aa={wm_opacity}[wm]")
            wm_y = overlay_y + 15
            filter_parts.append(f"{current}[wm]overlay=W-w-{wm_margin}:{wm_y}[final]")
        else:
            filter_parts.append(f"{current}null[final]")

        filter_complex = ';'.join(filter_parts)

        # Determine if we need watermark image input
        wm_input = []
        if watermark_image and os.path.exists(watermark_image) and not watermark_text:
            wm_input = ['-i', watermark_image]

        # Build ffmpeg command with better quality settings
        cmd = ['ffmpeg', '-y', '-i', input_path, *wm_input, '-filter_complex', filter_complex, '-map', '[final]']
        if info.get('has_audio'):
            cmd.extend(['-map', '0:a?', '-c:a', 'aac', '-b:a', '192k'])
        cmd.extend([
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
            '-pix_fmt', 'yuv420p', '-aspect', '9:16', '-movflags', '+faststart',
            '-map_metadata', '-1',
            '-metadata', f'creation_time={datetime.utcnow().isoformat()}Z',
            '-metadata', f'encoder=custom_{self._random_str(12)}',
            '-metadata', f'comment={self._random_str(16)}',
            '-fflags', '+genpts',
            output_path
        ])
        
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception("Video processing failed")
        return output_path
    
    async def process_image(self, input_path: str, output_path: str, crop_mode: str = 'smart',
                           top_text: Optional[str] = None, watermark_text: Optional[str] = None,
                           watermark_image: Optional[str] = None, filter_preset: Optional[str] = None,
                           dark_mode: bool = True) -> str:
        info = self.get_media_info(input_path)
        src_w, src_h = info['width'], info['height']
        if src_w == 0 or src_h == 0:
            raise Exception("Could not read image dimensions")

        # Layout settings - @clips style
        bg_color = "black" if dark_mode else "white"
        text_color = "white" if dark_mode else "black"

        filter_parts = []

        # Apply filter preset if specified
        filter_eq = None
        if filter_preset and filter_preset != 'none':
            preset = self.preset_manager.get_preset(filter_preset)
            if preset:
                filter_eq = self._build_filter_eq(preset.get('filters', {}))

        # Calculate text area dynamically
        text_area_height = 0
        text_lines = []
        text_font_size = 58
        line_height = 78

        if top_text:
            clean_text = ''.join(c if (32 <= ord(c) <= 126) else ' ' for c in top_text)
            clean_text = re.sub(r' {2,}', ' ', clean_text).strip()

            total_chars = len(clean_text)
            if total_chars <= 40:
                text_font_size = 58
                max_chars_per_line = 22
            elif total_chars <= 80:
                text_font_size = 50
                max_chars_per_line = 26
            elif total_chars <= 120:
                text_font_size = 44
                max_chars_per_line = 30
            else:
                text_font_size = 38
                max_chars_per_line = 34

            line_height = int(text_font_size * 1.4)

            words = clean_text.split()
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= max_chars_per_line:
                    current_line = (current_line + " " + word).strip()
                else:
                    if current_line:
                        text_lines.append(current_line)
                    current_line = word
            if current_line:
                text_lines.append(current_line)

            text_area_height = len(text_lines) * line_height + 80

        # Image positioning
        image_top_margin = text_area_height + 30 if top_text else 80
        image_bottom_margin = 80
        content_height = REEL_HEIGHT - image_top_margin - image_bottom_margin
        content_width = REEL_WIDTH - 40

        src_aspect = src_w / src_h
        target_aspect = content_width / content_height

        # Always use fit mode for images to preserve content
        if src_aspect > target_aspect:
            scaled_w = content_width
            scaled_h = int(content_width / src_aspect)
        else:
            scaled_h = content_height
            scaled_w = int(content_height * src_aspect)
        scaled_w = scaled_w if scaled_w % 2 == 0 else scaled_w - 1
        scaled_h = scaled_h if scaled_h % 2 == 0 else scaled_h - 1

        scale_filter = f"scale={scaled_w}:{scaled_h}"
        if filter_eq:
            scale_filter = f"{filter_eq},{scale_filter}"
        filter_parts.append(f"[0:v]{scale_filter},setsar=1[scaled]")

        filter_parts.append(f"color={bg_color}:{REEL_WIDTH}x{REEL_HEIGHT}[bg]")

        overlay_x = (REEL_WIDTH - scaled_w) // 2
        overlay_y = image_top_margin + (content_height - scaled_h) // 2
        filter_parts.append(f"[bg][scaled]overlay={overlay_x}:{overlay_y}[canvas]")

        current = "[canvas]"

        # Add text
        if top_text and text_lines:
            start_y = 40

            for i, line in enumerate(text_lines):
                escaped_line = line.replace("'", "'\\''").replace(":", "\\:").replace("\\", "\\\\")
                line_y = start_y + (i * line_height)
                out_label = f"[txt{i}]"
                filter_parts.append(
                    f"{current}drawtext="
                    f"text='{escaped_line}':"
                    f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                    f"fontsize={text_font_size}:"
                    f"fontcolor={text_color}:"
                    f"x=(w-text_w)/2:"
                    f"y={line_y}"
                    f"{out_label}"
                )
                current = out_label

            filter_parts.append(f"{current}null[texted]")
            current = "[texted]"

        # Watermark settings
        wm_font_size = 32
        wm_margin = 20
        wm_opacity = 0.85

        if watermark_text:
            escaped_wm = watermark_text.replace("'", "'\\''").replace(":", "\\:")
            wm_y = overlay_y + 15
            filter_parts.append(
                f"{current}drawtext="
                f"text='{escaped_wm}':"
                f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
                f"fontsize={wm_font_size}:"
                f"fontcolor=white@{wm_opacity}:"
                f"x=w-tw-{wm_margin}:"
                f"y={wm_y}:"
                f"shadowcolor=black@0.5:"
                f"shadowx=1:shadowy=1"
                f"[final]"
            )
        elif watermark_image and os.path.exists(watermark_image):
            filter_parts.append(f"[1:v]scale=100:-1,format=yuva420p,colorchannelmixer=aa={wm_opacity}[wm]")
            wm_y = overlay_y + 15
            filter_parts.append(f"{current}[wm]overlay=W-w-{wm_margin}:{wm_y}[final]")
        else:
            filter_parts.append(f"{current}null[final]")
        
        filter_complex = ';'.join(filter_parts)
        
        wm_input = []
        if watermark_image and os.path.exists(watermark_image) and not watermark_text:
            wm_input = ['-i', watermark_image]
        
        cmd = ['ffmpeg', '-y', '-i', input_path, *wm_input, '-filter_complex', filter_complex, '-map', '[final]', '-q:v', '2',
               '-map_metadata', '-1', '-metadata', f'comment={self._random_str(16)}', output_path]
        
        process = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"FFmpeg error: {stderr.decode()}")
            raise Exception("Image processing failed")
        return output_path


os.makedirs(DATA_DIR, exist_ok=True)
preset_manager = PresetManager(PRESETS_FILE)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "🎬 *Instagram Content Processor*\n\n"
        "Send me:\n"
        "• A video link (Twitter, TikTok, Instagram, YouTube)\n"
        "• Or upload a video/image directly\n\n"
        "I'll format it for Instagram Reels with:\n"
        "✅ Fresh metadata (avoids duplicate flags)\n"
        "✅ Custom cropping options\n"
        "✅ Dark/Light mode\n"
        "✅ Text overlay (viral style)\n"
        "✅ Watermark\n"
        "✅ Filter presets for images\n\n"
        "*Commands:*\n"
        "/presets - Manage filter presets\n"
        "/settings - View settings\n"
        "/cancel - Cancel operation",
        parse_mode='Markdown'
    )
    return WAITING_FOR_CONTENT


async def handle_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.message
    if msg.text:
        url = msg.text.strip()
        domains = ['twitter.com', 'x.com', 'tiktok.com', 'instagram.com', 'youtube.com', 'youtu.be']
        if any(d in url.lower() for d in domains):
            context.user_data['url'] = url
            context.user_data['content_type'] = 'video'
            await msg.reply_text("⬇️ Downloading video...")
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    processor = MediaProcessor(temp_dir, preset_manager)
                    input_path = await processor.download_video(url)
                    persistent = os.path.join(DATA_DIR, f'input_{msg.from_user.id}.mp4')
                    subprocess.run(['cp', input_path, persistent])
                    context.user_data['input_path'] = persistent
                    context.user_data['media_info'] = processor.get_media_info(persistent)
                await msg.reply_text("✅ Downloaded!")
                return await show_crop_options(update, context)
            except Exception as e:
                await msg.reply_text(f"❌ Download failed: {e}\n\nTry a different link.")
                return WAITING_FOR_CONTENT
        else:
            await msg.reply_text("Send a valid link from Twitter/X, TikTok, Instagram, or YouTube.\nOr upload media directly.")
            return WAITING_FOR_CONTENT
    elif msg.photo:
        photo = msg.photo[-1]
        file = await photo.get_file()
        path = os.path.join(DATA_DIR, f'input_{msg.from_user.id}.jpg')
        await file.download_to_drive(path)
        context.user_data['input_path'] = path
        context.user_data['content_type'] = 'image'
        await msg.reply_text("✅ Image received!")
        return await show_crop_options(update, context)
    elif msg.video or msg.document:
        file = await (msg.video or msg.document).get_file()
        ext = 'mp4'
        if msg.document and msg.document.file_name:
            ext = msg.document.file_name.split('.')[-1]
        path = os.path.join(DATA_DIR, f'input_{msg.from_user.id}.{ext}')
        await file.download_to_drive(path)
        with tempfile.TemporaryDirectory() as td:
            proc = MediaProcessor(td, preset_manager)
            info = proc.get_media_info(path)
        context.user_data['input_path'] = path
        context.user_data['content_type'] = 'video' if info.get('is_video') else 'image'
        context.user_data['media_info'] = info
        await msg.reply_text(f"✅ {'Video' if info.get('is_video') else 'Image'} received!")
        return await show_crop_options(update, context)
    await msg.reply_text("Send a link, video, or image.")
    return WAITING_FOR_CONTENT


async def show_crop_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton("🎯 Smart Crop", callback_data="crop_smart"), InlineKeyboardButton("⬛ Center", callback_data="crop_center")],
        [InlineKeyboardButton("⬆️ Top", callback_data="crop_top"), InlineKeyboardButton("⬇️ Bottom", callback_data="crop_bottom")],
        [InlineKeyboardButton("📐 Fit (Bars)", callback_data="crop_fit")],
    ]
    msg = update.message or update.callback_query.message
    await msg.reply_text("📐 *How to crop?*\n\n• *Smart/Center*: Fill frame, centered\n• *Top/Bottom*: Keep top or bottom\n• *Fit*: Show all with bars", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CHOOSE_CROP


async def crop_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['crop_mode'] = query.data.replace("crop_", "")
    
    # Now ask for dark/light mode
    keyboard = [
        [InlineKeyboardButton("🌑 Dark Mode", callback_data="mode_dark")],
        [InlineKeyboardButton("☀️ Light Mode", callback_data="mode_light")],
    ]
    await query.edit_message_text(
        f"✅ Crop: *{context.user_data['crop_mode'].title()}*\n\n🎨 Choose background:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='Markdown'
    )
    return CHOOSE_MODE


async def mode_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['dark_mode'] = query.data == "mode_dark"
    mode_name = "Dark" if context.user_data['dark_mode'] else "Light"
    
    keyboard = [[InlineKeyboardButton("✍️ Add Text", callback_data="text_yes"), InlineKeyboardButton("⏭️ Skip", callback_data="text_no")]]
    await query.edit_message_text(f"✅ Mode: *{mode_name}*\n\nAdd text above the content?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ENTER_TEXT


async def text_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "text_yes":
        await query.edit_message_text("✍️ Enter the text to appear above:\n\n_Tip: Use short punchy text like the viral pages_", parse_mode='Markdown')
        return CONFIRM_TEXT
    context.user_data['top_text'] = None
    return await show_watermark_options(update, context)


async def receive_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['top_text'] = update.message.text.strip()
    keyboard = [[InlineKeyboardButton("✅ Confirm", callback_data="text_confirm"), InlineKeyboardButton("✏️ Re-enter", callback_data="text_reenter")]]
    await update.message.reply_text(f"📝 Preview:\n\n*{context.user_data['top_text']}*\n\nLook good?", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CONFIRM_TEXT


async def text_confirmed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "text_reenter":
        await query.edit_message_text("✍️ Enter the text again:")
        return CONFIRM_TEXT
    return await show_watermark_options(update, context)


async def show_watermark_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [InlineKeyboardButton(f"📍 Default ({DEFAULT_WATERMARK_TEXT})", callback_data="wm_default")],
        [InlineKeyboardButton("✍️ Custom Text", callback_data="wm_custom"), InlineKeyboardButton("🖼️ Image", callback_data="wm_image")],
        [InlineKeyboardButton("⏭️ No Watermark", callback_data="wm_none")],
    ]
    query = update.callback_query
    if query:
        await query.edit_message_text("💧 *Watermark:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text("💧 *Watermark:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CHOOSE_WATERMARK


async def watermark_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "wm_default":
        context.user_data['watermark_text'] = DEFAULT_WATERMARK_TEXT
        context.user_data['watermark_image'] = None
    elif query.data == "wm_custom":
        await query.edit_message_text("✍️ Enter watermark text (e.g. @yourusername):")
        return ENTER_WATERMARK_TEXT
    elif query.data == "wm_image":
        if os.path.exists(WATERMARK_IMAGE_PATH):
            context.user_data['watermark_text'] = None
            context.user_data['watermark_image'] = WATERMARK_IMAGE_PATH
        else:
            await query.edit_message_text("❌ No watermark image set. Set WATERMARK_PATH env var.")
            return await show_watermark_options(update, context)
    else:
        context.user_data['watermark_text'] = None
        context.user_data['watermark_image'] = None
    return await maybe_show_filters(update, context)


async def receive_watermark_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['watermark_text'] = update.message.text.strip()
    context.user_data['watermark_image'] = None
    return await maybe_show_filters(update, context)


async def maybe_show_filters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Show filters for both videos and images
    return await show_filter_options(update, context)


async def show_filter_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    presets = preset_manager.list_presets()
    keyboard = []
    row = []
    for key, preset in presets.items():
        row.append(InlineKeyboardButton(preset['name'], callback_data=f"filter_{key}"))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text("🎨 *Choose filter:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return CHOOSE_FILTER


async def filter_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data['filter_preset'] = query.data.replace("filter_", "")
    preset = preset_manager.get_preset(context.user_data['filter_preset'])
    await query.edit_message_text(f"✅ Filter: *{preset['name'] if preset else 'None'}*", parse_mode='Markdown')
    return await process_content(update, context)


async def process_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = update.callback_query.message if update.callback_query else update.message
    status = await msg.reply_text("⚙️ Processing...")
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            processor = MediaProcessor(temp_dir, preset_manager)
            input_path = context.user_data['input_path']
            content_type = context.user_data['content_type']
            dark_mode = context.user_data.get('dark_mode', True)
            rand = processor._random_str()
            ext = 'mp4' if content_type == 'video' else 'jpg'
            output_path = os.path.join(temp_dir, f'output_{rand}.{ext}')
            if content_type == 'video':
                await status.edit_text("⚙️ Processing video...\n🎬 Applying viral format...")
                await processor.process_video(
                    input_path, output_path,
                    crop_mode=context.user_data.get('crop_mode', 'smart'),
                    top_text=context.user_data.get('top_text'),
                    watermark_text=context.user_data.get('watermark_text'),
                    watermark_image=context.user_data.get('watermark_image'),
                    dark_mode=dark_mode,
                    filter_preset=context.user_data.get('filter_preset')
                )
                await status.edit_text("📤 Uploading...")
                with open(output_path, 'rb') as f:
                    await msg.reply_video(video=f, caption="✅ Done!\n📱 Ready for Reels\n🔄 Fresh metadata", supports_streaming=True)
            else:
                await status.edit_text("⚙️ Processing image...\n🖼️ Applying viral format...")
                await processor.process_image(
                    input_path, output_path,
                    crop_mode=context.user_data.get('crop_mode', 'smart'),
                    top_text=context.user_data.get('top_text'),
                    watermark_text=context.user_data.get('watermark_text'),
                    watermark_image=context.user_data.get('watermark_image'),
                    filter_preset=context.user_data.get('filter_preset'),
                    dark_mode=dark_mode
                )
                await status.edit_text("📤 Uploading...")
                with open(output_path, 'rb') as f:
                    await msg.reply_photo(photo=f, caption="✅ Done!\n📱 Ready for Instagram\n🔄 Fresh metadata")
        await status.delete()
        if os.path.exists(input_path):
            os.remove(input_path)
        context.user_data.clear()
        await msg.reply_text("🎉 Send another link or file!")
        return WAITING_FOR_CONTENT
    except Exception as e:
        logger.error(f"Processing error: {e}", exc_info=True)
        await status.edit_text(f"❌ Failed: {e}")
        context.user_data.clear()
        return WAITING_FOR_CONTENT


async def manage_presets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    presets = preset_manager.list_presets()
    preset_list = "\n".join([f"• *{p['name']}*: {p['description']}" for p in presets.values()])
    keyboard = [[InlineKeyboardButton("➕ Create Preset", callback_data="preset_create")], [InlineKeyboardButton("🗑️ Delete Preset", callback_data="preset_delete")], [InlineKeyboardButton("🔙 Back", callback_data="preset_back")]]
    await update.message.reply_text(f"🎨 *Filter Presets*\n\n{preset_list}", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return MANAGE_PRESETS


async def preset_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "preset_back":
        await query.edit_message_text("Send a link or file to process!")
        return WAITING_FOR_CONTENT
    elif query.data == "preset_create":
        await query.edit_message_text("🆕 *Create Preset*\n\nSend in format:\n\n`name: My Filter`\n`description: Cool look`\n`saturation: 1.2`\n`contrast: 1.1`\n`brightness: 1.0`\n`temperature: 20`\n\n_Values are multipliers (1.0 = normal)_", parse_mode='Markdown')
        return CREATE_PRESET
    elif query.data == "preset_delete":
        custom = {k: v for k, v in preset_manager.list_presets().items() if k not in PresetManager.DEFAULT_PRESETS}
        if not custom:
            await query.edit_message_text("No custom presets to delete.")
            return WAITING_FOR_CONTENT
        keyboard = [[InlineKeyboardButton(f"🗑️ {p['name']}", callback_data=f"delete_{k}")] for k, p in custom.items()]
        keyboard.append([InlineKeyboardButton("🔙 Cancel", callback_data="preset_back")])
        await query.edit_message_text("Select preset to delete:", reply_markup=InlineKeyboardMarkup(keyboard))
        return MANAGE_PRESETS
    elif query.data.startswith("delete_"):
        key = query.data.replace("delete_", "")
        preset_manager.delete_preset(key)
        await query.edit_message_text("✅ Deleted!")
        return WAITING_FOR_CONTENT
    return MANAGE_PRESETS


async def create_preset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lines = update.message.text.strip().split('\n')
        config = {}
        for line in lines:
            if ':' in line:
                k, v = line.split(':', 1)
                config[k.strip().lower()] = v.strip()
        name = config.get('name', 'Custom')
        desc = config.get('description', 'Custom filter')
        filters = {}
        for k in ['saturation', 'contrast', 'brightness']:
            if k in config:
                filters[k] = float(config[k])
        if 'temperature' in config:
            filters['temperature'] = int(config['temperature'])
        key = ''.join(c for c in name.lower().replace(' ', '_') if c.isalnum() or c == '_')
        preset_manager.add_preset(key, name, desc, filters)
        await update.message.reply_text(f"✅ Created '*{name}*'!\n\nSend content to try it.", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")
    return WAITING_FOR_CONTENT


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.clear()
    await update.message.reply_text("❌ Cancelled. Send new content to start.")
    return WAITING_FOR_CONTENT


async def settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(f"⚙️ *Settings*\n\n📐 Output: {REEL_WIDTH}x{REEL_HEIGHT}\n💧 Default watermark: `{DEFAULT_WATERMARK_TEXT}`\n🖼️ Watermark image: {'✅' if os.path.exists(WATERMARK_IMAGE_PATH) else '❌'}", parse_mode='Markdown')


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start), MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_content)],
        states={
            WAITING_FOR_CONTENT: [MessageHandler(filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL, handle_content)],
            CHOOSE_CROP: [CallbackQueryHandler(crop_selected, pattern="^crop_")],
            CHOOSE_MODE: [CallbackQueryHandler(mode_selected, pattern="^mode_")],
            ENTER_TEXT: [CallbackQueryHandler(text_choice, pattern="^text_")],
            CONFIRM_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_text), CallbackQueryHandler(text_confirmed, pattern="^text_")],
            CHOOSE_WATERMARK: [CallbackQueryHandler(watermark_selected, pattern="^wm_")],
            ENTER_WATERMARK_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_watermark_text)],
            CHOOSE_FILTER: [CallbackQueryHandler(filter_selected, pattern="^filter_")],
            MANAGE_PRESETS: [CallbackQueryHandler(preset_action)],
            CREATE_PRESET: [MessageHandler(filters.TEXT & ~filters.COMMAND, create_preset)],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )
    app.add_handler(conv)
    app.add_handler(CommandHandler("presets", manage_presets))
    app.add_handler(CommandHandler("settings", settings))
    print("🤖 Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()

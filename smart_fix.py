import re

with open('/root/instagram-bot/bot.py', 'r') as f:
    content = f.read()

# FIX 1: Add smart crop detection function after imports
smart_crop_func = '''
def detect_content_region(video_path):
    """Detect actual video content area, excluding text bars"""
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
    
    # Use ffmpeg cropdetect to find content area
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

'''

# Add after imports
import_section_end = content.find('\nclass ')
if import_section_end == -1:
    import_section_end = content.find('\ndef ')

content = content[:import_section_end] + smart_crop_func + content[import_section_end:]

# FIX 2: Replace fixed font size with dynamic sizing
old_font_line = 'text_font_size = 60'
new_font_logic = '''# Dynamic font size based on text length
        total_chars = len(clean_text)
        if total_chars <= 30:
            text_font_size = 72  # Big for short text
        elif total_chars <= 60:
            text_font_size = 62  # Medium
        elif total_chars <= 100:
            text_font_size = 52  # Smaller
        else:
            text_font_size = 44  # Smallest for long text'''

# Find where text_font_size is set in the text processing section
# We need to add this AFTER clean_text is created
old_line_height = 'line_height = int(text_font_size * 1.35)'
new_with_dynamic = new_font_logic + '''
        
        line_height = int(text_font_size * 1.35)'''

content = content.replace(old_line_height, new_with_dynamic)

# Remove the old fixed text_font_size if it's set elsewhere for text
content = re.sub(r'\n\s+text_font_size = 60\s*#[^\n]*\n', '\n', content)

with open('/root/instagram-bot/bot.py', 'w') as f:
    f.write(content)

print("✅ Added smart crop detection + dynamic text sizing")

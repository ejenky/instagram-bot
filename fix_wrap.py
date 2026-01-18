import re

with open('/root/instagram-bot/bot.py', 'r') as f:
    content = f.read()

# Add wrap_text function after imports if not already there
if 'def wrap_text(' not in content:
    wrap_func = '''
def wrap_text(text, max_chars=25):
    """Wrap text to multiple lines"""
    if not text:
        return []
    lines = []
    for paragraph in text.split('\\n'):
        words = paragraph.split()
        if not words:
            lines.append('')
            continue
        current_line = words[0]
        for word in words[1:]:
            if len(current_line) + 1 + len(word) <= max_chars:
                current_line += ' ' + word
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)
    return lines

'''
    content = content.replace(
        'logger = logging.getLogger(__name__)',
        'logger = logging.getLogger(__name__)' + wrap_func
    )

# Find and replace the text drawing section
old_block = '''    # Add top text - VIRAL STYLE
    if top_text:
        # Handle multi-line text (split by newline or auto-wrap long text)
        escaped = top_text.replace("'", "'\\\\''").replace(":", "\\\\:").replace("\\\\", "\\\\\\\\")
        filter_parts.append(
            f"{current}drawtext="
            f"text='{escaped}':"
            f"fontfile=/usr/share/fonts/truetype/inter/Inter-Bold.ttf:"
            f"fontsize={text_font_size}:"
            f"fontcolor={text_color}:"
            f"x=(w-text_w)/2:"
            f"y={text_y_position}:"
            f"shadowcolor={shadow_color}:"
            f"shadowx=2:shadowy=2"
            f"[texted]"
        )
        current = "[texted]"'''

new_block = '''    # Add top text - VIRAL STYLE with word wrapping
    if top_text:
        text_lines = wrap_text(top_text, max_chars=25)
        line_height = int(text_font_size * 1.4)
        start_y = 100  # Start from top
        
        for i, line in enumerate(text_lines):
            if not line.strip():
                continue
            escaped_line = line.replace("'", "'\\\\''").replace(":", "\\\\:").replace("\\\\", "\\\\\\\\")
            line_y = start_y + (i * line_height)
            out_label = f"[txt{i}]"
            
            filter_parts.append(
                f"{current}drawtext="
                f"text='{escaped_line}':"
                f"fontfile=/usr/share/fonts/truetype/inter/Inter-Bold.ttf:"
                f"fontsize={text_font_size}:"
                f"fontcolor={text_color}:"
                f"x=(w-text_w)/2:"
                f"y={line_y}:"
                f"shadowcolor={shadow_color}:"
                f"shadowx=2:shadowy=2"
                f"{out_label}"
            )
            current = out_label
        
        # If no text lines were processed, keep current as is
        if not text_lines or not any(l.strip() for l in text_lines):
            pass  # current unchanged'''

if old_block in content:
    content = content.replace(old_block, new_block)
    print("✅ Replaced text block successfully")
else:
    print("❌ Could not find exact text block to replace")
    print("Searching for partial match...")
    # Try to find it with regex
    if "# Add top text - VIRAL STYLE" in content:
        print("Found the comment marker")

with open('/root/instagram-bot/bot.py', 'w') as f:
    f.write(content)

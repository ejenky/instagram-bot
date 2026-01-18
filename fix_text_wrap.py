import re

# Read the file
with open('/root/instagram-bot/bot.py', 'r') as f:
    content = f.read()

# Add text wrap helper function after the imports (find "logger = logging" line)
wrap_function = '''

def wrap_text(text, max_chars=28):
    """Wrap text to multiple lines, respecting word boundaries"""
    if not text:
        return []
    
    # First split by actual newlines in the input
    paragraphs = text.split('\\n')
    lines = []
    
    for para in paragraphs:
        words = para.split()
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

# Insert after logger definition
content = content.replace(
    "logger = logging.getLogger(__name__)",
    "logger = logging.getLogger(__name__)" + wrap_function
)

# Now replace the text drawing section (lines ~227-249)
old_text_block = '''    # Add top text - VIRAL STYLE
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

new_text_block = '''    # Add top text - VIRAL STYLE with word wrapping
    if top_text:
        # Wrap text to multiple lines
        text_lines = wrap_text(top_text, max_chars=28)
        line_height = int(text_font_size * 1.3)  # Line spacing
        
        # Calculate starting Y to center the text block vertically in text area
        total_text_height = len(text_lines) * line_height
        start_y = max(80, text_y_position - (total_text_height // 2) + (line_height // 2))
        
        for i, line in enumerate(text_lines):
            if not line.strip():
                continue
            escaped_line = line.replace("'", "'\\\\''").replace(":", "\\\\:").replace("\\\\", "\\\\\\\\")
            line_y = start_y + (i * line_height)
            output_label = f"[text{i}]"
            
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
                f"{output_label}"
            )
            current = output_label
        
        # Rename final output for consistency
        if text_lines:
            # The last label becomes [texted] for the rest of the pipeline
            pass  # current already holds the last label'''

content = content.replace(old_text_block, new_text_block)

# Also need to fix the reference to [texted] later - change it to use current
content = content.replace(
    'current = "[texted]"',
    '# current already set by loop above'
)

# Write back
with open('/root/instagram-bot/bot.py', 'w') as f:
    f.write(content)

print("✅ Text wrapping patch applied!")

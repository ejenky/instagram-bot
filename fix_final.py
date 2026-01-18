with open('/root/instagram-bot/bot.py', 'r') as f:
    content = f.read()

# The broken section (no proper indentation)
old_section = '''        # Dynamic font size based on text length
total_chars = len(clean_text)
if total_chars <= 30:
    text_font_size = 72  # Big for short text
elif total_chars <= 60:
    text_font_size = 62  # Medium
elif total_chars <= 100:
    text_font_size = 52  # Smaller
else:
    text_font_size = 44  # Smallest for long text

line_height = int(text_font_size * 1.35)
start_y = 160

    for i, line in enumerate(text_lines):
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

    # Alias final text label as [texted] for watermark code
    if text_lines:
        filter_parts.append(f"{current}null[texted]")
        current = "[texted]"'''

# Fixed version with proper 8-space indentation
new_section = '''        # Dynamic font size based on text length
        total_chars = len(clean_text)
        if total_chars <= 30:
            text_font_size = 72  # Big for short text
        elif total_chars <= 60:
            text_font_size = 62  # Medium
        elif total_chars <= 100:
            text_font_size = 52  # Smaller
        else:
            text_font_size = 44  # Smallest for long text

        line_height = int(text_font_size * 1.35)
        start_y = 160

        for i, line in enumerate(text_lines):
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

        # Alias final text label as [texted] for watermark code
        if text_lines:
            filter_parts.append(f"{current}null[texted]")
            current = "[texted]"'''

if old_section in content:
    content = content.replace(old_section, new_section)
    print("✅ Fixed indentation")
else:
    print("❌ Section not found - trying line by line fix")
    lines = content.split('\n')
    fixed = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Fix specific lines that need indentation
        if line == 'total_chars = len(clean_text)':
            line = '        total_chars = len(clean_text)'
        elif line == 'if total_chars <= 30:':
            line = '        if total_chars <= 30:'
        elif line == '    text_font_size = 72  # Big for short text':
            line = '            text_font_size = 72  # Big for short text'
        elif line == 'elif total_chars <= 60:':
            line = '        elif total_chars <= 60:'
        elif line == '    text_font_size = 62  # Medium':
            line = '            text_font_size = 62  # Medium'
        elif line == 'elif total_chars <= 100:':
            line = '        elif total_chars <= 100:'
        elif line == '    text_font_size = 52  # Smaller':
            line = '            text_font_size = 52  # Smaller'
        elif line == 'else:' and i > 0 and 'total_chars' in lines[i-1]:
            line = '        else:'
        elif line == '    text_font_size = 44  # Smallest for long text':
            line = '            text_font_size = 44  # Smallest for long text'
        elif line == 'line_height = int(text_font_size * 1.35)':
            line = '        line_height = int(text_font_size * 1.35)'
        elif line == 'start_y = 160':
            line = '        start_y = 160'
        elif line == '    for i, line in enumerate(text_lines):':
            line = '        for i, line in enumerate(text_lines):'
        fixed.append(line)
        i += 1
    content = '\n'.join(fixed)
    print("✅ Applied line-by-line fixes")

with open('/root/instagram-bot/bot.py', 'w') as f:
    f.write(content)

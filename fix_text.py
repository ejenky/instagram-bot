import re

with open('/root/instagram-bot/bot.py', 'r') as f:
    content = f.read()

old_block = '''        # Add top text - VIRAL STYLE
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

new_block = '''        # Add top text - VIRAL STYLE with multi-line support
        if top_text:
            # Clean text: ONLY allow basic printable ASCII
            clean_text = ''.join(c if (32 <= ord(c) <= 126) else ' ' for c in top_text)
            clean_text = re.sub(r' {2,}', ' ', clean_text).strip()
            
            # Word wrap to fit frame (max ~24 chars per line for font size 60)
            words = clean_text.split()
            text_lines = []
            current_line = ""
            for word in words:
                if len(current_line + " " + word) <= 24:
                    current_line = (current_line + " " + word).strip()
                else:
                    if current_line:
                        text_lines.append(current_line)
                    current_line = word
            if current_line:
                text_lines.append(current_line)
            
            line_height = int(text_font_size * 1.35)
            start_y = 50
            
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

if old_block in content:
    content = content.replace(old_block, new_block)
    print("✅ Replaced text block")
else:
    print("❌ Block not found exactly - check for whitespace differences")
    import sys
    sys.exit(1)

# Add re import at top if not present
if "import re" not in content.split("def ")[0]:
    content = "import re\n" + content

# Set font size to 60 (like @clips)
content = re.sub(r'text_font_size = \d+', 'text_font_size = 60', content)

with open('/root/instagram-bot/bot.py', 'w') as f:
    f.write(content)

print("✅ Done: multi-line, char filter, font 60px")

with open('/root/instagram-bot/bot.py', 'r') as f:
    content = f.read()

# Find and replace the text section more carefully
old_section = '''        line_height = int(text_font_size * 1.35)
        start_y = 160'''

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
        start_y = 160'''

if old_section in content:
    content = content.replace(old_section, new_section)
    print("✅ Added dynamic text sizing")
else:
    print("❌ Could not find target section")
    # Try alternate
    old_alt = '''        line_height = int(text_font_size * 1.35)
        start_y = 50'''
    new_alt = new_section.replace('start_y = 160', 'start_y = 160')
    if old_alt in content:
        content = content.replace(old_alt, new_section)
        print("✅ Added dynamic text sizing (alt)")
    else:
        print("⚠️ Manual fix needed")

with open('/root/instagram-bot/bot.py', 'w') as f:
    f.write(content)

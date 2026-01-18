with open('/root/instagram-bot/bot.py', 'r') as f:
    lines = f.readlines()

fixed = []
for line in lines:
    # These lines need 8 spaces added
    if line.strip().startswith('total_chars = len(clean_text)'):
        line = '        ' + line.lstrip()
    elif line.strip().startswith('if total_chars <= 30:'):
        line = '        ' + line.lstrip()
    elif line.strip().startswith('text_font_size = 72'):
        line = '            ' + line.lstrip()
    elif line.strip().startswith('elif total_chars <= 60:'):
        line = '        ' + line.lstrip()
    elif line.strip().startswith('text_font_size = 62'):
        line = '            ' + line.lstrip()
    elif line.strip().startswith('elif total_chars <= 100:'):
        line = '        ' + line.lstrip()
    elif line.strip().startswith('text_font_size = 52'):
        line = '            ' + line.lstrip()
    elif line.strip() == 'else:' and len(line) - len(line.lstrip()) == 0:
        line = '        else:\n'
    elif line.strip().startswith('text_font_size = 44'):
        line = '            ' + line.lstrip()
    elif line.strip().startswith('line_height = int(text_font_size'):
        line = '        ' + line.lstrip()
    elif line.strip() == 'start_y = 160':
        line = '        start_y = 160\n'
    fixed.append(line)

with open('/root/instagram-bot/bot.py', 'w') as f:
    f.writelines(fixed)

print("✅ Fixed indentation")

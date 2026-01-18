with open('/root/instagram-bot/bot.py', 'r') as f:
    lines = f.readlines()

# Fix lines 309+ that have extra indentation in the for loop
fixed_lines = []
in_for_block = False
for i, line in enumerate(lines):
    # Detect start of the problematic for loop (around line 309)
    if 'for i, line in enumerate(text_lines):' in line and line.startswith('            '):
        # Remove 4 spaces of extra indent
        line = line.replace('            for', '        for', 1)
        in_for_block = True
    elif in_for_block and line.startswith('                '):
        # Inside for loop - remove 4 spaces
        line = '            ' + line.lstrip()
    elif in_for_block and line.startswith('            ') and 'filter_parts.append' in line:
        line = '        ' + line.lstrip()
    elif in_for_block and not line.strip():
        pass  # Empty line
    elif in_for_block and not line.startswith('            ') and not line.startswith('                '):
        in_for_block = False
    
    fixed_lines.append(line)

with open('/root/instagram-bot/bot.py', 'w') as f:
    f.writelines(fixed_lines)

print("✅ Fixed indentation")

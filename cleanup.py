with open("floodgate.py", "r", encoding="utf-8") as f:
    c = f.read()

# Find both occurrences
first = c.find("def _open_custom_dialog")
second = c.find("def _open_custom_dialog", first + 1)

if second > 0:
    # Find the end of the second one
    next_def = c.find("\n    def ", second + 1)
    duplicate = c[second:next_def]
    c = c.replace(duplicate, "")
    print("Removed duplicate _open_custom_dialog")

with open("floodgate.py", "w", encoding="utf-8") as f:
    f.write(c)

print("Done - Codebase is clean")
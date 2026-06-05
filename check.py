with open("remixer.py", "r", encoding="utf-8") as f:
    for line in f.readlines():
        if "CLIP_DURATION" in line:
            print(line.strip())
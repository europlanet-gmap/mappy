#!/usr/bin/env python


if __name__ == "__main__":
    file = "../INFO.md"

    from pathlib import Path
    f = Path(file)
    if not f.exists():
        print("FIle not found")
        exit()

    ofile = "../mappy/INFO.html"

    import markdown
    with open(file, "r") as f:
        o = markdown.markdown(f.read(), extensions=["tables"])

    with open(ofile, "w") as f:
        f.write(o)
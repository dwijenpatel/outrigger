"""Greedy word-wrapping utility.

Spec:
- wrap(text, width) splits text into words on any whitespace and greedily
  packs them into lines joined by single spaces, each line at most `width`
  characters long.
- A word longer than `width` is hard-broken into chunks of exactly `width`
  characters (the last chunk may be shorter); chunks then flow like words.
- wrap("", n) and wrap(whitespace-only, n) return [].
- width < 1 raises ValueError.
"""


def wrap(text, width):
    words = []
    for w in text.split():
        words.append(w)

    lines = []
    current = ""
    for word in words:
        if not current:
            current = word
        elif len(current) + len(word) < width:
            current = current + " " + word
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines

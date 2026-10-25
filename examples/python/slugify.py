def slugify(text):
    # BUG: spaces are removed instead of turned into dashes
    return text.strip().lower().replace(" ", "")

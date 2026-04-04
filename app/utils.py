import string

ALPHABET = string.ascii_letters + string.digits


def encode_base62(num):
    if num == 0:
        return ALPHABET[0]
    chars = []
    while num:
        num, rem = divmod(num, 62)
        chars.append(ALPHABET[rem])
    return "".join(reversed(chars))

from datetime import date, timedelta

JAIN_FORBIDDEN = {"onion", "garlic", "potato", "carrot", "beet", "radish", "egg", "meat", "fish", "honey"}


def is_jain(pref: str) -> bool:
    return "jain" in pref.lower()


def meal_code(pref: str) -> str:
    p = pref.lower()
    if "jain" in p:
        return "VJML"
    if "vegan" in p:
        return "VGML"
    if "veg" in p:
        return "AVML"
    return "STANDARD"


def jain_ok(dish: str) -> bool:
    d = dish.lower()
    return not any(x in d for x in JAIN_FORBIDDEN)


def daterange(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)

"""Explicit natural conversation closings, without treating ordinary thanks as goodbye."""

import re


def is_end_request(text, wake_phrase="Jarvis"):
    def normalize(value):
        value = str(value).lower().replace("’", "'").replace("‘", "'")
        value = re.sub(r"[.!?,;:]", " ", value).replace("con-conversation", "conversation")
        return re.sub(r"\s+", " ", value).strip()

    value = normalize(text)
    name = normalize(wake_phrase)
    names = sorted({name, re.sub(r"^(?:hey|okay|ok) ", "", name)} - {""}, key=len, reverse=True)
    named = thanked = False
    for _ in range(6):
        before = value
        value = re.sub(r"^(?:(?:ok(?:ay)?|hey|well|alright) +)+", "", value)
        value = re.sub(r" please$", "", value)
        value = re.sub(r"(?<!for) now$", "", value)
        for name in names:
            if value == name:
                value = ""
                named = True
            elif value.startswith(name + " "):
                value = value[len(name) + 1 :]
                named = True
            elif value.endswith(" " + name):
                value = value[: -len(name) - 1]
                named = True
        prefix = r"^(?:thank you(?: very much)?|thanks(?: a lot)?)(?: |$)"
        suffix = r" (?:thank you(?: very much)?|thanks(?: a lot)?)$"
        if re.search(prefix, value):
            value = re.sub(prefix, "", value)
            thanked = True
        if re.search(suffix, value):
            value = re.sub(suffix, "", value)
            thanked = True
        value = value.strip()
        if value == before:
            break
    if not value:
        return named and thanked
    return bool(
        re.fullmatch(
            r"(?:(?:please|(?:can|could|would) you(?: please)?|i (?:need|want)(?: you)? to) )?(?:stop listening|end (?:the |this )?conversation|goodbye|bye(?: bye)?|that(?:'s| is| would be| will be|'ll be) (?:all|it|everything)|i(?:'m| am) done|we(?:'re| are) done|nothing else|no more questions)(?: for (?:now|today))?",
            value,
        )
    )

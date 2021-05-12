from os import environ
API_ID = int(environ["API_ID"])
API_HASH = environ["API_HASH"]
SUDO_CHAT_ID = int(environ["SUDO_CHAT_ID"])
SUDOERS = list(int(x) for x in environ.get("SUDOERS", "").split())
SESSION_STRING = environ["SESSION_STRING"]

ARQ_API = "https://thearq.tech"

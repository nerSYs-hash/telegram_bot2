import inspect
from telegram import Bot
import json

def run():
    params = inspect.signature(Bot.send_message).parameters
    res = {
        'disable_web_page_preview': 'disable_web_page_preview' in params,
        'link_preview_options': 'link_preview_options' in params
    }
    print(json.dumps(res))

run()

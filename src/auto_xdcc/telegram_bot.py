import logging
import requests
import json
import datetime

from auto_xdcc.thread_runner import ThreadRunner


class TelegramBot(ThreadRunner):
    api_url = 'https://api.telegram.org/bot'
    parser = None

    def __init__(self, token, chat_id=None):
        self.token = token
        self.chat_id = chat_id
        self.api_url += token + '/'
        self.session = requests.Session()
        super().__init__(logging.getLogger('telegram_bot'))

    def set_chat_id_cb(self, config):
        def on_chat_id_cb(chat_id):
            config['credentials']['telegram'] = {'token': self.token, 'chat_id': chat_id}
            config.persist()

        self.on_chat_id_cb = on_chat_id_cb
        return self

    def set_arg_parser(self, parser):
        self.parser = parser
        return self

    def start(self):
        if not self.parser:
            raise Exception('Missing argument parser, cannot start thread')
        super().start()

    def _run(self):
        last_id = None
        while not self.is_stopping() and not self.chat_id:
            for update in self.get_updates():
                self.chat_id = update['message']['chat']['id']
                if self.on_chat_id_cb:
                    self.on_chat_id_cb(self.chat_id)
                last_id = update['update_id']
                break

        self.send_message('Select command', reply_markup={
            'keyboard': [
                ['show add', 'show remove', 'show update'],
                ['show list', 'show archive', 'show restore'],
                ['packlist reset', 'packlist run'],
                ['bot']
            ]
        }, disable_notification=True)
        self.logger.info('starting update check')
        while not self.is_stopping():
            for update in self.get_updates(last_id=last_id):
                last_id = update['update_id']
                self.run_command(update['message']['text'])

    def run_command(self, cmd):
        args = None
        if cmd == 'show list':
            args = ['show', 'list']

        if args:
            self.logger.debug('Command received: %s', cmd)
            parsed_args = self.parser.parse_args(args)
            parsed_args.handler(parsed_args)

    def get_url(self, endpoint):
        return self.api_url + endpoint

    def get_updates(self, last_id=None, timeout=10, allowed_updates=['message']):
        params = {
            'timeout': timeout,
            'allowed_updates': json.dumps(allowed_updates)
        }

        if last_id is not None:
            params['offset'] = last_id + 1

        r = self.session.get(self.get_url('getUpdates'), params=params, timeout=timeout + 3)

        return r.json()['result']

    def get_me(self):
        r = self.session.get(self.get_url('getMe'))
        return r.json()['result']

    def send_message(self, text, **kwargs):
        body = {
            'chat_id': self.chat_id,
            'text': text
        }
        body.update(kwargs)
        return self.session.post(self.get_url('sendMessage'), json=body)

import logging
import requests
import json
import shlex

from auto_xdcc.thread_runner import ThreadRunner


class TelegramBot(ThreadRunner):
    parser = None

    def __init__(self, token, chat_id=None):
        self.token = token
        self.chat_id = chat_id
        self.api_url = 'https://api.telegram.org/bot' + token + '/'
        self.session = requests.Session()
        super().__init__(logging.getLogger('telegram_bot'))

    @classmethod
    def init_from_config(cls, config):
        telegram_conf = config['credentials']['telegram']
        telegram_bot = cls(telegram_conf['token'], chat_id=telegram_conf.get('chat_id'))
        telegram_bot.set_chat_id_cb(config).start()
        return telegram_bot

    def set_parser(self, parser):
        self.parser = parser

    def set_chat_id_cb(self, config):
        def on_chat_id_cb(chat_id):
            config['credentials']['telegram'] = {'token': self.token, 'chat_id': chat_id}
            config.persist()

        self.on_chat_id_cb = on_chat_id_cb
        return self

    def _run(self):
        last_id = None
        while not self.is_stopping() and not self.chat_id:
            for update in self.get_updates():
                self.chat_id = update['message']['chat']['id']
                if self.on_chat_id_cb:
                    self.on_chat_id_cb(self.chat_id)
                last_id = update['update_id']
                break

        self.send_message('-> AXDCC bot ready! <-', reply_markup={
            'keyboard': [
                ['show list', 'show list archived']
            ]
        }, disable_notification=True)
        self.logger.info('starting update check')
        while not self.is_stopping():
            self.logger.debug('waiting for updates')
            for update in self.get_updates(last_id=last_id):
                last_id = update['update_id']
                self.process_message(update['message'])

    def process_message(self, message):
        args = [arg for arg in shlex.split(message['text']) if arg != '']
        if args:
            try:
                self.logger.debug('processing message from %s "%s"', message['from']['username'], message['text'])
                parsed_args = self.parser.parse_args(args)
                self.logger.debug('calling handler of message %s "%s"', message['from']['username'], message['text'])
                parsed_args.handler(parsed_args)
                self.logger.debug('message %s "%s" handled', message['from']['username'], message['text'])
            except Exception:
                pass


    def get_url(self, endpoint):
        return self.api_url + endpoint

    def get_updates(self, last_id=None, timeout=10, allowed_updates=['message']):
        params = {
            'timeout': timeout,
            'allowed_updates': json.dumps(allowed_updates)
        }

        if last_id is not None:
            params['offset'] = last_id + 1

        try:
            r = self.session.get(self.get_url('getUpdates'), params=params, timeout=timeout + 3)
            return r.json().get('result', [])
        except requests.exceptions.RequestException as e:
            self.logger.error('Error during update request', exc_info=e)
            return []


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

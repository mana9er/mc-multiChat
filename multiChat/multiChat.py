"""
A front-end for MultiChat.
Based on PyQt5 Websockets.
"""

import json
from PyQt5 import QtCore
from PyQt5.QtWebSockets import QWebSocket

RETRY_INTERVAL_MIN = 5000 # 5000ms
RETRY_INTERVAL_MAX = 3600 * 1000 # 1h
SUPPORTED_LANGUAGES = ['en', 'zh-cn']

class MultiChatWS(QtCore.QObject):
    """
    Websocket connected to MultiChat-Server.
    """

    def __init__(self, logger, core, config):
        super().__init__(core)
        self.core = core
        self.logger = logger
        disabled = False
        self.config = config
        self.url = config['multichat-url'].rstrip('/') + '/'
        self.key = config['multichat-key']
        self.server_name = config['server-name'] if 'server-name' in config else ''
        self.do_listen = config['listen']
        self.do_post = config['post']
        self.ignore_prefix = config['ignore-prefix']
        self.lang = 'en'  # default value
        if 'lang' in config:
            if config['lang'] not in SUPPORTED_LANGUAGES:
                self.logger.warning('Not supported language: {}'.format(config['lang']))
            else:
                self.lang = config['lang']
        
        # load mcBasicLib
        self.utils = core.get_plugin('mcBasicLib')
        if self.utils is None:
            self.logger.error('Failed to load plugin "mcBasicLib", multiChat will be disabled.')
            self.logger.error('Please make sure that "mcBasicLib" has been added to plugins.')
            disabled = True
        if disabled:
            return

        self.ws = QWebSocket()
        self.ws_valid = False
        # connect signals and slots
        self.utils.sig_input.connect(self.on_player_input)
        self.utils.sig_login.connect(self.on_player_login)
        self.utils.sig_logout.connect(self.on_player_logout)
        self.utils.sig_advancement.connect(self.on_advancement)
        self.utils.sig_death.connect(self.on_death)
        self.ws.connected.connect(self.on_connected)
        self.ws.textMessageReceived.connect(self.on_recv)
        self.ws.disconnected.connect(self.on_connection_broken)
        self.retry_interval = RETRY_INTERVAL_MIN
        self.retry_timer = QtCore.QTimer()
        self.retry_timer.timeout.connect(self.on_retry_timer)
        self.on_retry_timer()  # open connection using this function


    def post(self, message):
        self.utils.tell('@a', message, color='#777777')

    
    def send_msg(self, message):
        """
        A simple wrap for sending message to multichat-server.
        """
        if self.ws_valid:
            obj = {
                'action': 'client-message',
                'content': message,
            }
            data = json.dumps(obj)
            self.logger.debug('WebSocket sending: ' + data)
            self.ws.sendTextMessage(data)
        else:
            self.logger.warning('Tried to write websocket when not available')

    
    @QtCore.pyqtSlot()
    def on_connected(self):
        self.logger.info('Successfully connected to: ' + self.url)
        # register
        register_obj = {
            'action': 'register',
            'client-name': 'MC-' + self.server_name if self.server_name else 'MC',
            'secret-key': self.key
        }
        register_str = json.dumps(register_obj)
        self.logger.debug('WebSocket sending:  ' + register_str)
        self.ws.sendTextMessage(register_str)


    @QtCore.pyqtSlot()
    def on_connection_broken(self):
        self.logger.info('Connection broken, retry after ' + str(self.retry_interval) + 'ms')
        self.utils.tell('@a', 'multichat connection broken, retry after ' + str(self.retry_interval) + 'ms')
        self.ws_valid = False
        self.retry_timer.setInterval(self.retry_interval)
        self.retry_timer.start()
        self.retry_interval = min(RETRY_INTERVAL_MAX, self.retry_interval * 2)


    @QtCore.pyqtSlot()
    def on_retry_timer(self):
        self.retry_timer.stop()
        self.logger.info('Connecting to multichat server')
        self.utils.tell('@a', 'multichat: connecting to server')
        self.ws.open(QtCore.QUrl(self.url))

    
    @QtCore.pyqtSlot(str)
    def on_recv(self, message):
        self.logger.debug('WebSocket received: ' + message)
        data = json.loads(message)
        if data['action'] == 'register-ack':
            self.logger.info('Successfully registered.')
            self.utils.tell('@a', 'multichat: server connected')
            self.ws_valid = True
            self.retry_interval = RETRY_INTERVAL_MIN
        if data['action'] == 'forwarding-message' and self.do_post:
            source = data['source-client-name']
            content = data['content']
            post_str = '[{}]{}'.format(source, content)
            # post to mc server
            self.post(post_str)


    @QtCore.pyqtSlot(tuple)
    def on_player_input(self, pair):
        self.logger.debug('MultiChat.on_player_input called')
        player, text = pair
        if text == '!multichat connect':
            if self.ws_valid:
                self.utils.tell(player, 'multichat is already connected to server')
            else:
                self.on_retry_timer()
            return
        if self.do_listen:
            if player.is_console():
                # we should not listen to console
                return
            for prefix in self.ignore_prefix:
                if text.startswith(prefix):
                    return
            msg = '<{}> {}'.format(player.name, text)
            self.send_msg(msg)

    
    @QtCore.pyqtSlot(object)
    def on_player_login(self, player):
        self.logger.debug('MultiChat.on_player_login called')
        # player should never be console
        player = player.name
        if self.lang == 'en':
            msg = '{} joined the game'.format(player)
        elif self.lang == 'zh-cn':
            msg = '{}加入了游戏'.format(player)
        self.send_msg(msg)

    
    @QtCore.pyqtSlot(object)
    def on_player_logout(self, player):
        self.logger.debug('MultiChat.on_player_logout called')
        # player should never be console
        player = player.name
        if self.lang == 'en':
            msg = '{} left the game'.format(player)
        elif self.lang == 'zh-cn':
            msg = '{}退出了游戏'.format(player)
        self.send_msg(msg)

    
    @QtCore.pyqtSlot(object)
    def on_advancement(self, advc):
        self.logger.debug('MultiChat.on_advancement called')
        msg = advc.format(lang=self.lang)
        self.send_msg(msg)

    
    @QtCore.pyqtSlot(object)
    def on_death(self, death_obj):
        self.logger.debug('MultiChat.on_death called')
        msg = death_obj.format(lang=self.lang)
        self.send_msg(msg)
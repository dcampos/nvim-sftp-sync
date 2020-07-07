import pysftp
import sys
import os
import logging
import socket
from threading import Timer


def debounce(wait, call_id, func):
    callers = {}

    def call_func():
        try:
            callers.pop(call_id)
            func()
        except KeyError:
            pass

    try:
        caller = callers[call_id]
        caller.cancel()
    except KeyError:
        pass

    caller = Timer(wait, call_func)
    caller.start()
    callers[call_id] = caller


class SftpClient:
    WAIT_TIME = 0.25

    def __init__(self, nvim, servers):
        self.nvim = nvim
        self.servers = servers
        self.pool = {}
        self.runners = {}
        self.logger = logging.getLogger('SFTP_SYNC')
        pass

    def sync(self, file) -> (bool, str):
        for name, server in self.servers.items():
            if os.path.commonpath([file, server['local_path']]) == server['local_path']:
                selected_server = name
        server = self.servers[selected_server]
        relative_path = os.path.relpath(file, server['local_path'])
        destination = os.path.join(server['remote_path'], relative_path)

        call_id = f'{file}:{destination}:{selected_server}'

        debounce(self.WAIT_TIME, call_id, lambda: self._do_sync(file, destination, selected_server))

    def _do_sync(self, file, destination, selected_server):
        try:
            sftp = self._connect(selected_server)
        except Exception as e:
            self.logger.error(e, exc_info=True)
            result, msg = False, '[SFTP] -> Error connecting to {}: {}'.format(
                selected_server, repr(e))

        result, msg = True, '[SFTP] -> {} -> OK'.format(selected_server)

        try:
            self.logger.debug('Sending file {}'.format(file))
            sftp.put(file, destination)
        except socket.timeout as e:
            self.logger.error(e, exc_info=True)
            result, msg = False, '[SFTP] -> Timeout error: {}'.format(repr(e))
        except OSError as e:
            self.logger.error(e, exc_info=True)
            remote_dir = os.path.dirname(destination)
            sftp.makedirs(remote_dir)
            sftp.put(file, destination)

        if result:
            self.nvim.async_call(
                lambda: self.nvim.out_write(msg + "\n"))
        else:
            self.nvim.async_call(
                lambda: self.nvim.err_write(msg + "\n"))

    def _connect(self, server):
        try:
            sftp = self.pool[server]
        except KeyError:
            self.logger.debug('Creating connection to {}'.format(server))
            config = self.servers[server]
            host = config['host']
            port = config.get('port', 22)
            username = config.get('username')
            password = config.get('password')
            private_key = config.get('private_key')
            private_key_pass = config.get('private_key_pass')
            sftp = pysftp.Connection(host=host,
                                     port=port,
                                     username=username,
                                     password=password,
                                     private_key=private_key,
                                     private_key_pass=private_key_pass)
            sftp.timeout = 10
            sftp._transport.set_keepalive(60)
            self.pool[server] = sftp
        return sftp

    def reset(self):
        self.pool = {}

    def quit(self):
        for server, connection in self.pool.items():
            connection.close()

    def keepalive(self):
        for server, connection in self.pool.items():
            connection.listdir()

import pysftp
import time
import os
import logging
import socket
from threading import Timer
from pynvim import Nvim


class SyncStatus:
    NONE = -1
    OK = 0
    SENDING = 1
    ERROR = 2


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

    def __init__(self, nvim: Nvim, servers: dict):
        self.vim = nvim
        self.servers = servers
        self.pool = {}
        self.runners = {}
        self.logger = logging.getLogger('SFTP_SYNC')
        pass

    def sync(self, file) -> None:
        for name, server in self.servers.items():
            if os.path.commonpath([file, server['local_path']]) == server['local_path']:
                selected_server = name
                break
        else:
            raise Exception("No server selected for the current path")
        server = self.servers[selected_server]
        relative_path = os.path.relpath(file, server['local_path'])
        destination = os.path.join(server['remote_path'], relative_path)

        call_id = f'{file}:{destination}:{selected_server}'

        debounce(self.WAIT_TIME, call_id, lambda: self._do_sync(file, destination, selected_server))

    def _do_sync(self, file, destination, selected_server):
        self.vim.async_call(
            lambda: self._set_status(file, SyncStatus.SENDING))

        start = time.time()

        try:
            sftp = self._connect(selected_server)
        except Exception as e:
            self.logger.error(e, exc_info=True)
            result, msg = False, 'Error connecting to {}: {}'.format(
                selected_server, repr(e))
            self.vim.async_call(lambda: self._update_results(file, result, msg, None))
            return

        result, msg = True, '{} -> OK'.format(selected_server)

        try:
            self.logger.debug('Sending file {}'.format(file))
            sftp.put(file, destination)
        except socket.timeout as e:
            self.logger.error(e, exc_info=True)
            result, msg = False, 'Timeout error: {}'.format(repr(e))
            self.reset()
        except OSError as e:
            self.logger.error(e, exc_info=True)
            remote_dir = os.path.dirname(destination)
            sftp.makedirs(remote_dir)
            sftp.put(file, destination)

        elapsed = time.time() - start

        self.vim.async_call(lambda: self._update_results(file, result, msg, elapsed))

    def _update_results(self, file, result, msg, elapsed):
        self._set_status(file, SyncStatus.OK if result else SyncStatus.ERROR)

        if result:
            self.vim.out_write(f"[SFTP] -> {msg} ({elapsed:.2f}s)\n")
        else:
            self.vim.err_write(f"[SFTP] -> {msg}\n")

    def _set_status(self, file, status):
        bufnr = self.vim.funcs.bufnr(file)
        buffer = self.vim.buffers[bufnr]
        buffer.vars['sync_status'] = status
        self.vim.command('doautocmd User SftpStatusChanged')

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
            sftp.timeout = 30
            sftp._transport.set_keepalive(60)
            self.pool[server] = sftp
        return sftp

    def reset(self):
        self.quit()
        for buffer in self.vim.buffers:
            buffer.vars['sync_status'] = SyncStatus.NONE
        self.pool = {}

    def quit(self):
        for connection in self.pool.values():
            connection.close()

    def keepalive(self):
        for connection in self.pool.values():
            connection.listdir()

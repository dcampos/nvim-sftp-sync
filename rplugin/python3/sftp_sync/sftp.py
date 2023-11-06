import pysftp
import time
import logging
import socket
from threading import Timer
from pynvim import Nvim
from pathlib import Path, PurePosixPath


class SyncStatus:
    NONE = -1
    OK = 0
    SENDING = 1
    ERROR = 2


callers = {}


def debounce(wait, call_id, func):

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
        self.servers = dict(sorted(servers.items()))
        self.pool = {}
        self.runners = {}
        self.logger = logging.getLogger('SFTP_SYNC')
        self.selected_server = None

    def sync(self, file) -> None:
        if self.selected_server == None:
            for name, server in self.servers.items():
                self.logger.debug(f'server: {server["local_path"]}')
                if Path(file).is_relative_to(server['local_path']):
                    selected_server = name
                    self.logger.debug(f'selected server: {server}')
                    break
            else:
                raise Exception("No server selected for the current path")
        else:
            selected_server = self.selected_server

        self.logger.debug('Selected server: {}'.format(selected_server))

        server = self.servers[selected_server]
        local_path = Path(server['local_path'])
        file_path = Path(file)
        relative_path = file_path.relative_to(local_path)
        remote_path = PurePosixPath(server['remote_path'])
        destination = (remote_path / relative_path).as_posix()

        call_id = f'{file}:{destination}:{selected_server}'
        self.logger.debug(call_id)

        debounce(self.WAIT_TIME, call_id, lambda: self.vim.async_call(self._do_sync, file, destination, selected_server))

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
            self.logger.debug('Sending file {} to {}'.format(file, destination))
            sftp.put(file, destination)
        except socket.timeout as e:
            self.logger.error(e, exc_info=True)
            result, msg = False, 'Timeout error: {}'.format(repr(e))
            self.vim.async_call(self.reset)
            self.reset()
        except OSError as e:
            self.logger.error(e, exc_info=True)
            remote_dir = PurePosixPath(destination).parent.as_posix()
            self.logger.debug('Remote path: {}'.format(remote_dir))
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
        buffer.vars['sftp_sync_status'] = status
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
            buffer.vars['sftp_sync_status'] = SyncStatus.NONE
        self.pool = {}

    def quit(self):
        for connection in self.pool.values():
            connection.close()

    def keepalive(self):
        for connection in self.pool.values():
            connection.listdir()

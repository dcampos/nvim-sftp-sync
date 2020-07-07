import pynvim
import logging
from tempfile import gettempdir
from .sftp import SftpClient

@pynvim.plugin
class SftpSync(object):

    def __init__(self, nvim):
        self.nvim = nvim
        vars = self.nvim.vars
        self.enabled = True
        self.log_file = vars.get('sync_log',
                                 '{}/{}'.format(gettempdir(), 'sftp_sync.log'))
        self.logger = logging.getLogger('SFTP_SYNC')
        self.logger.setLevel(logging.DEBUG)
        file_handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.servers = vars.get("sync_servers", {})
        self.sftp = SftpClient(self.nvim, self.servers)

    @pynvim.command('SftpSync', nargs='?', complete='file')
    def sftp_sync(self, args):
        if not self.enabled: return
        try:
            file = args[0]
        except IndexError:
            file = self.nvim.eval("expand('%:p')")
        self.sftp.sync(file)

    @pynvim.command('SftpReset', nargs='0')
    def sftp_reset(self, args):
        self.sftp.reset()

    @pynvim.command('SftpDisable', nargs='0')
    def sftp_disable(self, args):
        self.enabled = False

    @pynvim.command('SftpEnable', nargs='0')
    def sftp_enable(self, args):
        self.enabled = True

    @pynvim.command('SftpOpenLog', nargs='0')
    def sftp_open_log(self, args):
        self.nvim.command('edit {}'.format(self.log_file))

    @pynvim.autocmd('VimLeave', pattern='*', sync=False)
    def on_vimleave(self):
        self.nvim.out_write('[SFTP] Quitting...')
        self.sftp.quit()

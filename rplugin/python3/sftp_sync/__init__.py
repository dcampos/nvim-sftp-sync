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
        self.log_file = vars.get('sftp_sync_log_file',
                                 '{}/{}'.format(gettempdir(), 'sftp_sync.log'))
        self.logger = logging.getLogger('SFTP_SYNC')
        self.log_level = vars.get('sftp_sync_log_level', logging.DEBUG)
        self.logger.setLevel(self.log_level)
        file_handler = logging.FileHandler(self.log_file)
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)
        self.servers = vars.get("sftp_sync_servers", {})
        self.sftp = SftpClient(self.nvim, self.servers)

    @pynvim.command('SftpSend', nargs='?', complete='file')
    def sftp_sync(self, args):
        if not self.enabled: return
        try:
            file = self.nvim.funcs.fnamemodify(args[0], ':p')
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

    @pynvim.command('SftpOpenLog', nargs=0)
    def sftp_open_log(self, args):
        self.nvim.command('edit {}'.format(self.log_file))

    @pynvim.command('SftpSelectServer', nargs=1, complete='customlist,_sftp_complete_server')
    def sftp_select_server(self, args):
        self.nvim.vars['sftp_sync_selected_server'] = args[0]
        self.sftp.selected_server = args[0]

    @pynvim.function('_sftp_complete_server', sync=True)
    def sftp_complete_server(self, args):
        if len(self.servers) > 0:
            return list(self.servers.keys())
        else:
            return []

    @pynvim.autocmd('VimLeave', pattern='*', sync=False)
    def on_vimleave(self):
        self.nvim.out_write('[SFTP] Quitting...')
        self.sftp.quit()

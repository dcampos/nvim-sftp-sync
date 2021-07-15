# SftpSync

SftpSync is a Neovim plugin that helps you sync your projects to an SFTP
server.

## Install

This plugin is known to work with Neovim stable. Version **0.5.0+** is
recommended. It may still work with older releases.

Install SftpSync using your favorite plugin manager. Using vim-plug:

```vim
Plug 'dcampos/nvim-sftp-sinc'
```

This plugin has an external dependence on the pysftp Python module. You can use
the `pip` command to install it:

```
pip install pysftp
```

## Usage

Basic server configuration:

```
let g:sftp_sync_servers = {
            \     'server1': {
            \         'local_path': '/home/myuser/projects/project1',
            \         'remote_path': '/server/project1',
            \         'host': 'myserver.com',
            \         'username': 'mysftpuser',
            \         'password': 's3cret',
            \     }
            \ }
```

Send the currently open file:

```
:SftpSend
```

See `:help sftp-sync` for more details.

## License

MIT license.

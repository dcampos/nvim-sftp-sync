# SftpSync

SftpSync is a Neovim plugin that helps you to sync your projects to a SFTP
server.

## Install

A recent Neovim version is required. Install using your favorite plugin manager.

Using vim-plug:

```vim
Plug 'dcampos/nvim-sftp-sinc'
```

## Usage

Basic server configuration:

```
let g:sync_servers = {
            \     'server1': {
            \         'local_path': '/home/myuser/projects/project1',
            \         'remote_path': '/server/project1',
            \         'host': 'myserver.com',
            \         'username': 'mysftpuser',
            \         'password': 's3cret',
            \     }
            \ }
```

Send the currently opened file:

```
:SftpSync
```

## License

MIT license.

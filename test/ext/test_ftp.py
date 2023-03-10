
from os import chdir, mkdir, symlink, unlink
from subprocess import PIPE
from time import localtime, strftime, tzset
import re

from bup.compat import environ
from bup.helpers import unlink as unlink_if_exists
from buptest import ex, exo
from wvpytest import wvfail, wvpass, wvpasseq, wvpassne, wvstart
import bup.path

bup_cmd = bup.path.exe()

def bup(*args, **kwargs):
    if 'stdout' not in kwargs:
        return exo((bup_cmd,) + args, **kwargs)
    return ex((bup_cmd,) + args, **kwargs)

def jl(*lines):
    return b''.join(line + b'\n' for line in lines)

def match_rx_grp(rx, expected, src):
    match = re.fullmatch(rx, src)
    wvpass(match, 're.fullmatch(%r, %r)' % (rx, src))
    if not match:
        return
    wvpasseq(expected, match.groups())

environ[b'GIT_AUTHOR_NAME'] = b'bup test'
environ[b'GIT_COMMITTER_NAME'] = b'bup test'
environ[b'GIT_AUTHOR_EMAIL'] = b'bup@a425bc70a02811e49bdf73ee56450e6f'
environ[b'GIT_COMMITTER_EMAIL'] = b'bup@a425bc70a02811e49bdf73ee56450e6f'

def test_ftp(tmpdir):
    environ[b'BUP_DIR'] = tmpdir + b'/repo'
    environ[b'GIT_DIR'] = tmpdir + b'/repo'
    environ[b'TZ'] = b'UTC'
    tzset()

    chdir(tmpdir)
    mkdir(b'src')
    chdir(b'src')
    mkdir(b'dir')
    with open(b'file-1', 'wb') as f:
        f.write(b'excitement!\n')
    with open(b'dir/file-2', 'wb') as f:
        f.write(b'more excitement!\n')
    symlink(b'file-1', b'file-symlink')
    symlink(b'dir', b'dir-symlink')
    symlink(b'not-there', b'bad-symlink')

    chdir(tmpdir)    
    bup(b'init')
    bup(b'index', b'src')
    bup(b'save', b'-n', b'src', b'--strip', b'src')
    save_utc = int(exo((b'git', b'show',
                        b'-s', b'--format=%at', b'src')).out.strip())
    save_name = strftime('%Y-%m-%d-%H%M%S', localtime(save_utc)).encode('ascii')
    
    wvstart('help')
    wvpasseq(b'Commands: ls cd pwd cat get mget help quit\n',
             exo((bup_cmd, b'ftp'), input=b'help\n', stderr=PIPE).out)

    wvstart('pwd/cd')
    wvpasseq(b'/\n', bup(b'ftp', input=b'pwd\n').out)
    wvpasseq(b'', bup(b'ftp', input=b'cd src\n').out)
    wvpasseq(b'/src\n', bup(b'ftp', input=jl(b'cd src', b'pwd')).out)
    wvpasseq(b'/src\n/\n', bup(b'ftp', input=jl(b'cd src', b'pwd',
                                                b'cd ..', b'pwd')).out)
    wvpasseq(b'/src\n/\n', bup(b'ftp', input=jl(b'cd src', b'pwd',
                                                b'cd ..', b'cd ..',
                                                b'pwd')).out)
    wvpasseq(b'/src/%s/dir\n' % save_name,
             bup(b'ftp', input=jl(b'cd src/latest/dir-symlink', b'pwd')).out)
    wvpasseq(b'/src/%s/dir\n' % save_name,
             bup(b'ftp', input=jl(b'cd src latest dir-symlink', b'pwd')).out)

    match_rx_grp(br'(error: path does not exist: /src/)[0-9-]+(/not-there\n/\n)',
                 (b'error: path does not exist: /src/', b'/not-there\n/\n'),
                 bup(b'ftp', input=jl(b'cd src/latest/bad-symlink', b'pwd')).out)

    match_rx_grp(br'(error: path does not exist: /src/)[0-9-]+(/not-there\n/\n)',
                 (b'error: path does not exist: /src/', b'/not-there\n/\n'),
                 bup(b'ftp', input=jl(b'cd src/latest/not-there', b'pwd')).out)

    wvstart('ls')
    # FIXME: elaborate
    wvpasseq(b'src\n', bup(b'ftp', input=b'ls\n').out)
    wvpasseq(save_name + b'\nlatest\n',
             bup(b'ftp', input=b'ls src\n').out)

    wvstart('cat')
    wvpasseq(b'excitement!\n',
             bup(b'ftp', input=b'cat src/latest/file-1\n').out)
    wvpasseq(b'excitement!\nmore excitement!\n',
             bup(b'ftp',
                 input=b'cat src/latest/file-1 src/latest/dir/file-2\n').out)
    
    wvstart('get')
    bup(b'ftp', input=jl(b'get src/latest/file-1 dest'))
    with open(b'dest', 'rb') as f:
        wvpasseq(b'excitement!\n', f.read())
    unlink(b'dest')
    bup(b'ftp', input=jl(b'get src/latest/file-symlink dest'))
    with open(b'dest', 'rb') as f:
        wvpasseq(b'excitement!\n', f.read())
    unlink(b'dest')

    match_rx_grp(br'(error: path does not exist: /src/)[0-9-]+(/not-there\n)',
                 (b'error: path does not exist: /src/', b'/not-there\n'),
                 bup(b'ftp', input=jl(b'get src/latest/bad-symlink dest')).out)

    match_rx_grp(br'(error: path does not exist: /src/)[0-9-]+(/not-there\n)',
                 (b'error: path does not exist: /src/', b'/not-there\n'),
                 bup(b'ftp', input=jl(b'get src/latest/not-there dest')).out)

    wvstart('mget')
    unlink_if_exists(b'file-1')
    bup(b'ftp', input=jl(b'mget src/latest/file-1'))
    with open(b'file-1', 'rb') as f:
        wvpasseq(b'excitement!\n', f.read())
    unlink_if_exists(b'file-1')
    unlink_if_exists(b'file-2')
    bup(b'ftp', input=jl(b'mget src/latest/file-1 src/latest/dir/file-2'))
    with open(b'file-1', 'rb') as f:
        wvpasseq(b'excitement!\n', f.read())
    with open(b'file-2', 'rb') as f:
        wvpasseq(b'more excitement!\n', f.read())
    unlink_if_exists(b'file-symlink')
    bup(b'ftp', input=jl(b'mget src/latest/file-symlink'))
    with open(b'file-symlink', 'rb') as f:
        wvpasseq(b'excitement!\n', f.read())
    # bup mget currently always does pattern matching
    bup(b'ftp', input=b'mget src/latest/not-there\n')

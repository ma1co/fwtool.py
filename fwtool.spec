# Run `pyinstaller fwtool.spec` to generate an executable

import subprocess, sys

# Generate filename
suffix = {'linux2': '-linux', 'win32': '-win', 'darwin': '-osx'}
output = 'fwtool-' + subprocess.check_output(['git', 'describe', '--always', '--tags']).decode('ascii').strip() + suffix.get(sys.platform, '')

# Analyze files
a = Analysis(['fwtool.py'], excludes=['bz2', 'cffi', 'Crypto', 'doctest', 'encodings.idna', 'lzma', 'plistlib', 'py_compile', 'socket', 'tempfile', 'tracemalloc'], datas=[('devices.yml', '.')])

# Generate executable
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, [('', 'fwtool.py', 'PYSOURCE')], a.binaries, a.zipfiles, a.datas, name=output)

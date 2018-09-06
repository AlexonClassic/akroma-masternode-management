# -*- mode: python -*-

block_cipher = None


a = Analysis(['akroma-mn-setup.py'],
             pathex=['akroma-masternode-management/source'],
             binaries=[],
             datas=[('templates', 'templates')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='akroma-mn-setup',
          debug=False,
          strip=True,
          upx=True,
          runtime_tmpdir='/dev/shm',
          console=True )

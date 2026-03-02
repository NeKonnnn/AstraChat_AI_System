# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('models', 'models'),
        ('model_small', 'model_small'),
        ('memory', 'memory'),
        ('silero_models', 'silero_models'),
        ('config.py', '.'),
        ('settings.json', '.'),
        ('llm_settings.json', '.'),
    ],
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'torch',
        'torchaudio',
        'vosk',
        'sounddevice',
        'llama_cpp',
        'numpy',
        'queue',
        'threading',
        'json',
        'requests',
        # Новые зависимости для работы с документами
        'docx',
        'PyPDF2',
        'openpyxl',
        'pdfplumber',
        'langchain',
        'langchain_community',
        'langchain_community.vectorstores',
        'langchain_community.embeddings',
        'faiss_cpu',
        'sentence_transformers',
        # Новые зависимости для транскрибации
        'whisper',
        'moviepy',
        'pytube',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='astrachat',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='astrachat',
) 
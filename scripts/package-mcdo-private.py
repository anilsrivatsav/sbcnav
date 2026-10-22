"""Create a private new-PC transfer ZIP. Never publish this ZIP or its connection file."""
import argparse
import json
from pathlib import Path
import shutil
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('--key-file', required=True, type=Path)
parser.add_argument('--installer', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
token = args.key_file.read_text(encoding='utf-8-sig').strip()
if not 32 <= len(token) <= 512 or any(c.isspace() for c in token):
    raise ValueError('The configured connection credential is invalid.')
args.output.mkdir(parents=True, exist_ok=True)
connection = args.output / 'SBC NAV Connection.sbcnav'
connection.write_text(json.dumps({'format': 'sbcnav-connection-v1', 'operator_token': token}), encoding='utf-8')
installer = args.output / args.installer.name
if args.installer.resolve() != installer.resolve():
    shutil.copy2(args.installer, installer)
guide = Path(__file__).resolve().parent.parent / 'desktop-companion/windows/QUICK START.html'
shutil.copy2(guide, args.output / 'START HERE.html')
checksum = args.installer.with_suffix('.sha256')
if checksum.is_file():
    shutil.copy2(checksum, args.output / checksum.name)
archive = args.output.parent / 'SBC NAV - New Windows PC - PRIVATE.zip'
with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=1) as package:
    for name in (installer.name, connection.name, 'START HERE.html', checksum.name):
        source = args.output / name
        if source.is_file():
            package.write(source, arcname='SBC NAV Setup/' + name)
print('Private transfer package created: ' + str(archive))

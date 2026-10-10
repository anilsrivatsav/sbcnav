"""Prepare an authorized computer's private connector without printing its key."""
import argparse,json,shutil
from pathlib import Path

def prepare(key_file,destination):
    root=Path(__file__).resolve().parent.parent
    destination=Path(destination).resolve()
    if destination.is_relative_to(root):
        raise ValueError('The paired connector must stay outside the source repository.')
    credential=Path(key_file).read_text().strip()
    if len(credential)<32:raise ValueError('An existing valid operator credential is required.')
    destination.mkdir(parents=True,exist_ok=True)
    for name in ('manifest.json','worker.js','bridge.js'):
        shutil.copy2(root/'browser-connector'/name,destination/name)
    (destination/'device-access.js').write_text('operatorKey='+json.dumps(credential)+';\n',encoding='utf-8')
    (destination/'READ ME.txt').write_text(
        'SBC NAV connector - private to this computer\n\n'
        '1. In Chrome, open chrome://extensions.\n'
        '2. Enable Developer mode. Choose Load unpacked and select this folder.\n'
        '3. Reload the MCDO page. It connects automatically.\n'
        '4. Click Update earnings and contracts. Sign in to IREPS only if asked.\n\n'
        'Do not share this folder. It contains this computer\'s operator credential.\n'
        'No operator key, API key or DSC PIN is entered into the dashboard.\n',encoding='utf-8')
    return destination

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--key-file',required=True);parser.add_argument('--destination',required=True)
    args=parser.parse_args();prepare(args.key_file,args.destination)
    print('Private connector prepared. Credential was not printed or published.')

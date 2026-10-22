# Standalone Windows package

The installer supports Windows 10/11 x64 and includes Python, Playwright's Node driver, the MCDO collector and Deskflow. Chrome and the physical token's vendor driver/signer must be installed by the operator. No browser sessions, credentials or user evidence are bundled in the generic installer.

Build using a Python environment with `playwright`, `pypdf`, `openpyxl`, `lxml`, `psutil` and `pyinstaller`, plus the official Inno Setup compiler:

```powershell
./scripts/build-mcdo-windows.ps1 -Python C:/Python312/python.exe -InnoCompiler 'C:/Program Files (x86)/Inno Setup 6/ISCC.exe'
```

The output is `dist/windows/SBC-NAV-Setup-2.1.0.exe` and its SHA256 file. Keep the `dist/windows/app` directory for diagnostics. Build output is ignored by Git.

Create a private authorised-operator transfer package separately:

```powershell
python ./scripts/package-mcdo-private.py --key-file C:/private/operator.key --installer ./dist/windows/SBC-NAV-Setup-2.1.0.exe --output C:/private/SBC-NAV-Setup
```

Never commit or publish the connection file or private ZIP. The installer looks for the adjacent `SBC NAV Connection.sbcnav` file and puts it in the user's pending setup folder. The setup wizard validates it against the fixed SBC NAV HTTPS API before saving `operator.key`; it does not accept arbitrary API endpoints. Only the existing authorised dashboard origin can invoke loopback commands. The app retains the source installation's state directory so completed work and recovery checkpoints survive migration. Existing source installations still use their source updater; frozen installations use the Windows installer.

For isolated automated installation tests, `/TESTINSTALL=1` skips shortcuts, protocol registration, connection import, post-install launch and uninstall registry changes. Use `/DIR=` to select a disposable folder. This switch must never be used for normal user installation.

Run `SBCNAVUpdater.exe --diagnostics <report.json>` with a fresh `LOCALAPPDATA` and a PATH containing only Windows System32 to test the bundled driver, Chrome automation, loopback origin checks, Excel export and state persistence. It does not contact IREPS or update Sheets. `--connect-file <file.sbcnav>` validates and installs a connection without starting collection, for controlled setup verification.

The application is built with PyInstaller and distributed with unmodified bundled dependency license notices under `_internal/licenses` and Playwright's own driver notices. The installer uses Inno Setup (Jordan Russell and Martijn Laan, https://jrsoftware.org/).

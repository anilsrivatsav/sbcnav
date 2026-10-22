# Standalone Windows package

The installer supports Windows 10/11 x64 and includes Python, Playwright's Node driver, the MCDO collector and Deskflow. Onboarding checks Chrome and IREPS Signer and offers installation from fixed official URLs. Chrome's Google Authenticode signature is verified; the unsigned official IREPS 1.5.1 MSI is checked against its recorded SHA256. Token driver guidance depends on the physical vendor; installed-software detection alone never claims the token works. Actual IREPS Payments access completes setup. No browser sessions, credentials or user evidence are bundled in the generic installer.

Build using a Python environment with `playwright`, `pypdf`, `openpyxl`, `lxml`, `psutil` and `pyinstaller`, plus the official Inno Setup compiler:

```powershell
./scripts/build-mcdo-windows.ps1 -Python C:/Python312/python.exe -InnoCompiler 'C:/Program Files (x86)/Inno Setup 6/ISCC.exe'
```

The output is `dist/windows/SBC-NAV-Setup-2.2.0.exe` and its SHA256 file. Keep the `dist/windows/app` directory for diagnostics. Build output is ignored by Git.

For a single private office EXE, add `-PrivateConnection C:/private/Connection.sbcnav -PrivateOutput C:/private/Office-setup`. This compiles the private connection into `SBC-NAV-Office-Setup-2.2.0.exe`. Never publish this executable. Installation saves a private copy and a manifest in the operator's state folder for onward downloads from the connected MCDO page. The loopback download accepts only an empty JSON POST from the exact production dashboard origin, checks the configured device and fixed installer path, and sends an uncached attachment. It never returns the operator key as a JSON value or string to browser JavaScript. The public web download redirects only to the fixed generic GitHub release asset.

Create a private authorised-operator transfer package separately:

```powershell
python ./scripts/package-mcdo-private.py --key-file C:/private/operator.key --installer ./dist/windows/SBC-NAV-Setup-2.2.0.exe --output C:/private/SBC-NAV-Setup
```

Never commit or publish the connection file or private ZIP. The installer looks for the adjacent `SBC NAV Connection.sbcnav` file and puts it in the user's pending setup folder. The setup wizard validates it against the fixed SBC NAV HTTPS API before saving `operator.key`; it does not accept arbitrary API endpoints. Only the existing authorised dashboard origin can invoke loopback commands. The app retains the source installation's state directory so completed work and recovery checkpoints survive migration. Existing source installations still use their source updater; frozen installations use the Windows installer.

For isolated automated installation tests, `/TESTINSTALL=1` skips shortcuts, protocol registration, post-install launch and uninstall registry changes. Use `/DIR=` for a disposable installation and `/TESTDATADIR=` for an isolated LocalAppData equivalent. A private EXE imports its pending connection and stores its onward installer there; the public installer skips external connection import in test mode. These switches must never be used for normal user installation.

Run `SBCNAVUpdater.exe --diagnostics <report.json>` with a fresh `LOCALAPPDATA` and a PATH containing only Windows System32 to test the bundled driver, Chrome automation, loopback origin checks, Excel export and state persistence. It does not contact IREPS or update Sheets. `--connect-file <file.sbcnav>` validates and installs a connection without starting collection, for controlled setup verification.

The application is built with PyInstaller and distributed with unmodified bundled dependency license notices under `_internal/licenses` and Playwright's own driver notices. The installer uses Inno Setup (Jordan Russell and Martijn Laan, https://jrsoftware.org/).

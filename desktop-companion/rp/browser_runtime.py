"""Use Playwright's shipped Node driver in source and standalone installations."""
from pathlib import Path
import playwright


def browser_reader_runtime():
    driver = Path(playwright.__file__).resolve().parent / 'driver'
    node = driver / 'node.exe'
    package = driver / 'package'
    if not node.is_file() or not (package / 'package.json').is_file():
        raise RuntimeError('The browser driver is missing. Reinstall SBC NAV Updater.')
    return node, package

"""Strip ALL business figures from a reference MCDO, retaining its print layout."""
import sys
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell

book = load_workbook(sys.argv[1])
for sheet in book:
    for row in sheet:
        for cell in row:
            if isinstance(cell, MergedCell):
                continue
            cell.comment = None
            # Clear the complete data blocks, including other divisions and totals.
            if (sheet.title.strip() == 'Immediate earning' and cell.row >= 9 and cell.column >= 3
                or sheet.title.strip() == 'Policywise' and 7 <= cell.row <= 10 and cell.column >= 3
                or sheet.title.strip() == 'Idle Assets' and cell.row in [6,7,8,9,10,16,17,18,19,20,27,28,29,30,31] and cell.column >= 2):
                cell.value = None
            if sheet.title.strip() == 'Idle Assets' and cell.column == 1 and cell.row in [3,13,24]:
                cell.value = '4. Status of NFR IDLE ASSETS (Position dated: pending)'
    sheet.print_options.horizontalCentered = False
output = Path(__file__).resolve().parents[1] / 'mcdo' / 'templates' / 'sbc_mcdo.xlsx'
output.parent.mkdir(parents=True, exist_ok=True)
book.save(output)
print(output)

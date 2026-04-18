"""
Dump le contenu VBA des modules qui contiennent des connexions DB.
Usage : python scripts/dump_vba_commando.py
"""
import win32com.client
import os

XLSM = r"D:\ATELIER_IT\01-mission commando\CommandoQuant.xlsm"

xl = win32com.client.Dispatch("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False

print(f"Ouverture : {XLSM}")
wb = xl.Workbooks.Open(XLSM)

KEYWORDS = ("CommandoQuant", "ACE", "OLEDB", "Provider", "Data Source",
            "connStr", "dbPath", "conn.Open", "ADODB")

for comp in wb.VBProject.VBComponents:
    mod = comp.CodeModule
    n = mod.CountOfLines
    if n == 0:
        continue
    code = mod.Lines(1, n)
    if any(kw in code for kw in KEYWORDS):
        print(f"\n{'='*60}")
        print(f"MODULE: {comp.Name} ({n} lignes)")
        print('='*60)
        # Print line by line with numbers
        for i, line in enumerate(code.split("\n"), 1):
            if any(kw in line for kw in KEYWORDS):
                print(f"  >> L{i:03d}: {line}")
            # Also print lines immediately before/after DB lines for context
        print()
        print("[CODE COMPLET]")
        print(code)

wb.Close(False)
xl.Quit()
print("\nDump termine.")

"""
Patch le VBA de CommandoQuant.xlsm pour rendre tous les chemins generiques.
Remplace les chemins hardcodes par ThisWorkbook.Path et Environ("LOCALAPPDATA").
Usage : python scripts/patch_vba_commando.py
"""
import win32com.client
import os

XLSM = r"D:\ATELIER_IT\01-mission commando\CommandoQuant.xlsm"

# Chaque tuple = (texte exact dans le VBA, remplacement generique)
PATCHES = [
    # --- Connexion Access ---
    (
        '"Data Source=D:\\ATELIER_IT\\01-mission commando\\CommandoQuant.accdb;"',
        '"Data Source=" & ThisWorkbook.Path & "\\CommandoQuant.accdb;"'
    ),
    (
        '"Data Source=D:\\ATELIER_IT\\01-mission commando\\CommandoQuant.accdb;" & _',
        '"Data Source=" & ThisWorkbook.Path & "\\CommandoQuant.accdb;" & _'
    ),
    (
        'dbPath = "D:\\ATELIER_IT\\01-mission commando\\CommandoQuant.accdb"',
        'dbPath = ThisWorkbook.Path & "\\CommandoQuant.accdb"'
    ),
    # --- Python executable ---
    (
        'pythonExe = "C:\\Users\\Windows\\AppData\\Local\\Python\\bin\\python.exe"',
        'pythonExe = Environ("LOCALAPPDATA") & "\\Python\\bin\\python.exe"'
    ),
    # --- Scripts Python ---
    (
        'scriptPath = "D:\\ATELIER_IT\\01-mission commando\\var_engine.py"',
        'scriptPath = ThisWorkbook.Path & "\\var_engine.py"'
    ),
    (
        'outputPath = "D:\\ATELIER_IT\\01-mission commando\\var_results.xlsx"',
        'outputPath = ThisWorkbook.Path & "\\var_results.xlsx"'
    ),
]

xl = win32com.client.Dispatch("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False

print(f"Ouverture : {XLSM}")
wb = xl.Workbooks.Open(XLSM)

total = 0
for comp in wb.VBProject.VBComponents:
    mod = comp.CodeModule
    n = mod.CountOfLines
    if n == 0:
        continue
    code = mod.Lines(1, n)
    new_code = code
    for old, new in PATCHES:
        if old in new_code:
            new_code = new_code.replace(old, new)
            print(f"  [{comp.Name}] OK : {old[:70]}")
            total += 1
    if new_code != code:
        mod.DeleteLines(1, n)
        mod.InsertLines(1, new_code)

print(f"\n{total} remplacement(s) effectue(s).")
wb.Save()
wb.Close(False)
xl.Quit()
print("Sauvegarde OK —", XLSM)

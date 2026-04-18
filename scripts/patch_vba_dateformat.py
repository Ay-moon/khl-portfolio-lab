"""
Ajoute SET DATEFORMAT ymd apres chaque conn.Open dans CDatabase
pour eviter les problemes de locale (serveur SQL Server en francais).
"""
import win32com.client

XLSM = r"D:\ATELIER_IT\01-mission commando\CommandoQuant.xlsm"

# Dans CDatabase.Class_Initialize, apres m_conn.Open m_connStr
# on ajoute m_conn.Execute "SET DATEFORMAT ymd"
PATCHES = [
    (
        '    m_conn.Open m_connStr\r\n    \r\n    Debug.Print "CDatabase connect',
        '    m_conn.Open m_connStr\r\n    m_conn.Execute "SET DATEFORMAT ymd"\r\n    \r\n    Debug.Print "CDatabase connect'
    ),
    # Variante LF seul
    (
        '    m_conn.Open m_connStr\n    \n    Debug.Print "CDatabase connect',
        '    m_conn.Open m_connStr\n    m_conn.Execute "SET DATEFORMAT ymd"\n    \n    Debug.Print "CDatabase connect'
    ),
]

xl = win32com.client.Dispatch("Excel.Application")
xl.Visible = False
xl.DisplayAlerts = False

wb = xl.Workbooks.Open(XLSM)
total = 0

for comp in wb.VBProject.VBComponents:
    mod = comp.CodeModule
    n   = mod.CountOfLines
    if n == 0:
        continue
    code = mod.Lines(1, n)
    new_code = code
    for old, new in PATCHES:
        if old in new_code:
            new_code = new_code.replace(old, new)
            print(f"  [OK] [{comp.Name}] SET DATEFORMAT ymd ajoute")
            total += 1
            break   # un seul patch par module
    if new_code != code:
        mod.DeleteLines(1, mod.CountOfLines)
        mod.InsertLines(1, new_code)

print(f"\n{total} remplacement(s).")
wb.Save()
wb.Close(False)
xl.Quit()
print("Sauvegarde OK")

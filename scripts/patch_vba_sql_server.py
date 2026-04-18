"""
Migre CommandoQuant.xlsm de Access vers SQL Server.
1. Cree la DB CommandoQuant + tbl_Greeks sur SQL Server
2. Patche le VBA : remplace toutes les connexions ACE OLEDB par SQLOLEDB
3. Corrige le format de date (Access #date# -> SQL Server 'date')
4. Supprime la verification Dir(dbPath) dans BtnPnLSim_

Usage : python scripts/patch_vba_sql_server.py
"""
import win32com.client
import pyodbc
import os
import sys

XLSM      = r"D:\ATELIER_IT\01-mission commando\CommandoQuant.xlsm"
SQL_SRV   = r"PERSO-AJE-DELL\BFASERVER01"
SQL_DB    = "CommandoQuant"

CONN_OLD_MAIN    = "SQLOLEDB_PLACEHOLDER"   # valeur temporaire
CONN_NEW_3LINES  = (
    '"Provider=SQLOLEDB;" & _\r\n'
    '                "Server=PERSO-AJE-DELL\\BFASERVER01;" & _\r\n'
    '                "Database=CommandoQuant;" & _\r\n'
    '                "Trusted_Connection=yes;"'
)

# ──────────────────────────────────────────────
# ETAPE 1 : Creer la DB et tbl_Greeks si absent
# ──────────────────────────────────────────────
def setup_sql_server():
    print("=== Etape 1 : SQL Server ===")
    try:
        conn = pyodbc.connect(
            f"DRIVER={{SQL Server}};SERVER={SQL_SRV};DATABASE=master;"
            "Trusted_Connection=yes;", timeout=5,
            autocommit=True
        )
        cur = conn.cursor()

        # Creer la base si elle n'existe pas
        cur.execute(f"SELECT name FROM sys.databases WHERE name = '{SQL_DB}'")
        if not cur.fetchone():
            cur.execute(f"CREATE DATABASE [{SQL_DB}]")
            print(f"  [OK] Base '{SQL_DB}' creee.")
        else:
            print(f"  [OK] Base '{SQL_DB}' existe deja.")
        conn.close()

        # Se connecter a CommandoQuant et creer tbl_Greeks
        conn2 = pyodbc.connect(
            f"DRIVER={{SQL Server}};SERVER={SQL_SRV};DATABASE={SQL_DB};"
            "Trusted_Connection=yes;", timeout=5
        )
        cur2 = conn2.cursor()
        cur2.execute(
            "SELECT 1 FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_NAME = 'tbl_Greeks'"
        )
        if not cur2.fetchone():
            cur2.execute("""
                CREATE TABLE tbl_Greeks (
                    ID           INT IDENTITY(1,1) PRIMARY KEY,
                    DatePricing  DATETIME      NOT NULL,
                    Underlying   NVARCHAR(50)  NOT NULL,
                    OptionType   NVARCHAR(10)  NOT NULL,
                    Strike       FLOAT         NOT NULL,
                    Maturity     DATE          NOT NULL,
                    Spot         FLOAT         NOT NULL,
                    Vol          FLOAT         NOT NULL,
                    Prix         FLOAT         NOT NULL,
                    Delta        FLOAT         NOT NULL,
                    Gamma        FLOAT         NOT NULL,
                    Vega         FLOAT         NOT NULL,
                    Theta        FLOAT         NOT NULL,
                    Rho          FLOAT         NOT NULL,
                    ImpliedVol   AS Vol,
                    Price        AS Prix
                )
            """)
            conn2.commit()
            print("  [OK] Table tbl_Greeks creee.")
        else:
            print("  [OK] Table tbl_Greeks existe deja.")
        conn2.close()
        return True
    except Exception as e:
        print(f"  [ERREUR] SQL Server : {e}")
        return False


# ──────────────────────────────────────────────
# ETAPE 2 : Patcher le VBA
# ──────────────────────────────────────────────

# Chaque tuple = (texte_exact_a_trouver, remplacement)
# Les chaines utilisent \r\n car c'est le separateur VBA sous Windows.
PATCHES = [

    # ── CDatabase : connexion principale ──────────────────────────────
    (
        '    m_connStr = "Provider=Microsoft.ACE.OLEDB.12.0;" & _\r\n'
        '                "Data Source=" & ThisWorkbook.Path & "\\CommandoQuant.accdb;"',

        '    m_connStr = "Provider=SQLOLEDB;" & _\r\n'
        '                "Server=PERSO-AJE-DELL\\BFASERVER01;" & _\r\n'
        '                "Database=CommandoQuant;" & _\r\n'
        '                "Trusted_Connection=yes;"'
    ),

    # ── CDatabase : format date Access -> SQL Server (Now) ────────────
    (
        '      "#" & Format(Now, "MM/DD/YYYY HH:MM:SS") & "#, " & _',
        '      "\'" & Format(Now, "YYYY-MM-DD HH:MM:SS") & "\', " & _'
    ),

    # ── CDatabase : format date Access -> SQL Server (Maturity) ───────
    (
        '      "#" & Format(maturity, "MM/DD/YYYY") & "#, " & _',
        '      "\'" & Format(maturity, "YYYY-MM-DD") & "\', " & _'
    ),

    # ── CBlotter : connexion en lecture ───────────────────────────────
    (
        '    conn.Open "Provider=Microsoft.ACE.OLEDB.12.0;" & _\r\n'
        '              "Data Source=" & ThisWorkbook.Path & "\\CommandoQuant.accdb;" & _\r\n'
        '              "Mode=Read;"',

        '    conn.Open "Provider=SQLOLEDB;" & _\r\n'
        '              "Server=PERSO-AJE-DELL\\BFASERVER01;" & _\r\n'
        '              "Database=CommandoQuant;" & _\r\n'
        '              "Trusted_Connection=yes;"'
    ),

    # ── BtnGreeks_ : connexion ────────────────────────────────────────
    (
        '    connStr = "Provider=Microsoft.ACE.OLEDB.12.0;" & _\r\n'
        '              "Data Source=" & ThisWorkbook.Path & "\\CommandoQuant.accdb;" & _\r\n'
        '              "Mode=Read;"',

        '    connStr = "Provider=SQLOLEDB;" & _\r\n'
        '              "Server=PERSO-AJE-DELL\\BFASERVER01;" & _\r\n'
        '              "Database=CommandoQuant;" & _\r\n'
        '              "Trusted_Connection=yes;"'
    ),

    # ── BtnGreeks_ : pied de page (mention Access) ────────────────────
    (
        '" \u2014 Donn\xe9es : tbl_Greeks (Access)"',
        '" \u2014 Donn\xe9es : tbl_Greeks (SQL Server)"'
    ),

    # ── BtnPnLSim_ : supprimer dbPath + Dir check + connexion Access ──
    (
        '    dbPath = ThisWorkbook.Path & "\\CommandoQuant.accdb"\r\n'
        '\r\n'
        '    If Dir(dbPath) = "" Then\r\n'
        '        MsgBox "Base Access introuvable :" & vbCrLf & dbPath, vbCritical, "Erreur connexion"\r\n'
        '        Exit Sub\r\n'
        '    End If\r\n'
        '\r\n'
        '    Set conn = CreateObject("ADODB.Connection")\r\n'
        '    conn.Open "Provider=Microsoft.ACE.OLEDB.12.0;" & _\r\n'
        '              "Data Source=" & dbPath & ";" & _\r\n'
        '              "Mode=Read;Persist Security Info=False;"',

        '    Set conn = CreateObject("ADODB.Connection")\r\n'
        '    conn.Open "Provider=SQLOLEDB;" & _\r\n'
        '              "Server=PERSO-AJE-DELL\\BFASERVER01;" & _\r\n'
        '              "Database=CommandoQuant;" & _\r\n'
        '              "Trusted_Connection=yes;"'
    ),

    # ── BtnPnLSim_ : Dim dbPath (variable devenue inutile) ────────────
    (
        '    Dim dbPath      As String\r\n',
        ''
    ),

    # ── BtnPnLSim_ : commentaire section ─────────────────────────────
    (
        "    ' 2. CONNEXION ACCESS",
        "    ' 2. CONNEXION SQL SERVER"
    ),

    # ── BtnGreeks_ : commentaire interne ──────────────────────────────
    (
        "    ' 1. OUVERTURE CONNEXION ACCESS",
        "    ' 1. OUVERTURE CONNEXION SQL SERVER"
    ),
]

# Variantes avec \n seul (si Windows ne retourne pas \r\n)
PATCHES_LF = []
for old, new in PATCHES:
    old_lf = old.replace('\r\n', '\n')
    new_lf = new.replace('\r\n', '\n')
    if old_lf != old:
        PATCHES_LF.append((old_lf, new_lf))


def patch_vba():
    print("\n=== Etape 2 : Patch VBA ===")
    xl = win32com.client.Dispatch("Excel.Application")
    xl.Visible = False
    xl.DisplayAlerts = False

    print(f"Ouverture : {XLSM}")
    wb = xl.Workbooks.Open(XLSM)

    total = 0
    for comp in wb.VBProject.VBComponents:
        mod = comp.CodeModule
        n   = mod.CountOfLines
        if n == 0:
            continue
        code = mod.Lines(1, n)
        new_code = code

        # Essayer d'abord avec \r\n, sinon avec \n
        all_patches = PATCHES + PATCHES_LF
        for old, new in all_patches:
            if old in new_code:
                new_code = new_code.replace(old, new)
                label = old[:60].replace('\r\n', '<CRLF>').replace('\n', '<LF>')
                print(f"  [OK] [{comp.Name}] : {label}...")
                total += 1

        if new_code != code:
            mod.DeleteLines(1, mod.CountOfLines)
            mod.InsertLines(1, new_code)

    print(f"\n{total} remplacement(s) effectue(s).")
    wb.Save()
    wb.Close(False)
    xl.Quit()
    print(f"Sauvegarde OK -> {XLSM}")


if __name__ == "__main__":
    ok = setup_sql_server()
    if not ok:
        print("\n[ATTENTION] SQL Server inaccessible — patch VBA annule.")
        sys.exit(1)
    patch_vba()
    print("\n=== Migration terminee ===")
    print("La macro CommandoQuant utilise maintenant SQL Server.")
    print(f"Server   : {SQL_SRV}")
    print(f"Database : {SQL_DB}")
    print("Table    : tbl_Greeks")

"""
Création des comptes de démonstration KHL Bank CIB Platform
============================================================
Ce script :
  1. Supprime tous les utilisateurs NON-ADMIN existants
  2. Recrée le compte ADMIN (reset mot de passe)
  3. Crée 6 comptes de démonstration (1 par rôle métier)

Usage : python scripts/create_demo_users.py
"""
import sys, os, hashlib, secrets
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
import db

# ══════════════════════════════════════════════════════════════
#  COMPTES À CRÉER
#  Format : (username, password, role, full_name, department)
# ══════════════════════════════════════════════════════════════
USERS = [
    # username          password         role             full_name                  department
    ("admin",           "Admin2026!",    "ADMIN",         "Administrateur KHL",      "IT Admin"),
    ("trader",          "Trader2026!",   "TRADER",        "Alex Dupont",             "Front Office — Trading"),
    ("assetmanager",    "Asset2026!",    "ASSET_MANAGER", "Jean-Marc Lefort",        "Front Office — Gestion"),
    ("quant",           "Quant2026!",    "QUANT",         "Thomas Berger",           "Front Office — Quant"),
    ("riskanalyst",     "Risk2026!",     "RISK_ANALYST",  "Sophie Martin",           "Middle Office — Risk"),
    ("comptable",       "Compta2026!",   "COMPTABLE",     "Isabelle Morel",          "Back Office — Comptabilité"),
    ("dataanalyst",     "Data2026!",     "DATA_ANALYST",  "Maria Chen",              "Back Office — Data"),
]


def _hash(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def main():
    print("=" * 60)
    print("  KHL Bank CIB — Création comptes de démonstration")
    print("=" * 60)

    with db.db_cursor() as cur:

        # ── 1. Supprimer tous les utilisateurs non-admin existants ──
        cur.execute("SELECT username FROM dbo.AppUsers WHERE role != 'ADMIN'")
        to_delete = [r[0] for r in cur.fetchall()]
        if to_delete:
            print(f"\n[SUPPRESSION] {len(to_delete)} utilisateur(s) supprimé(s) :")
            for u in to_delete:
                print(f"  - {u}")
            cur.execute("DELETE FROM dbo.AppUsers WHERE role != 'ADMIN'")
        else:
            print("\n[INFO] Aucun utilisateur non-admin à supprimer.")

        # ── 2. Créer / recréer chaque compte ───────────────────────
        print("\n[CRÉATION] Comptes de démonstration :\n")
        for username, password, role, full_name, department in USERS:
            salt   = secrets.token_hex(16)
            hashed = _hash(password, salt)
            email  = f"{username}@khlbank.fr"

            cur.execute("SELECT user_id FROM dbo.AppUsers WHERE username = ?", username)
            existing = cur.fetchone()
            if existing:
                cur.execute("""
                    UPDATE dbo.AppUsers
                    SET password_hash=?, password_salt=?, role=?, full_name=?,
                        department=?, is_active=1
                    WHERE username=?
                """, hashed, salt, role, full_name, department, username)
                action = "mis à jour"
            else:
                cur.execute("""
                    INSERT INTO dbo.AppUsers
                        (username, email, password_hash, password_salt, role, full_name, department)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, username, email, hashed, salt, role, full_name, department)
                action = "créé"

            print(f"  [{action.upper():12}]  {username:20} | {password:15} | {role}")

    # ── 3. Récapitulatif ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RÉCAPITULATIF DES ACCÈS")
    print("=" * 60)
    print(f"\n  {'IDENTIFIANT':<20} {'MOT DE PASSE':<16} {'RÔLE':<16} {'OFFICE'}")
    print(f"  {'-'*20} {'-'*16} {'-'*16} {'-'*14}")

    office_map = {
        "ADMIN":         "Système",
        "TRADER":        "Front Office",
        "ASSET_MANAGER": "Front Office",
        "QUANT":         "Front Office",
        "RISK_ANALYST":  "Middle Office",
        "COMPTABLE":     "Back Office",
        "DATA_ANALYST":  "Back Office",
    }
    for username, password, role, _, _ in USERS:
        office = office_map.get(role, "—")
        print(f"  {username:<20} {password:<16} {role:<16} {office}")

    print(f"\n  URL : http://localhost:5000")
    print("=" * 60)
    print("\n  [OK] Tous les comptes sont prêts.\n")


if __name__ == "__main__":
    main()

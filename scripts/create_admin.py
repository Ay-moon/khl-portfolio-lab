"""
Crée ou recrée le compte ADMIN de la plateforme KHL Bank CIB.
Usage : python scripts/create_admin.py
"""
import sys, os, hashlib, secrets
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'webapp'))
import db

USERNAME = "admin"
PASSWORD = "Admin2026!"
EMAIL    = "admin@khlbank.fr"

salt   = secrets.token_hex(16)
hashed = hashlib.sha256((salt + PASSWORD).encode()).hexdigest()

try:
    with db.db_cursor() as cur:
        cur.execute("SELECT user_id FROM dbo.AppUsers WHERE username = ?", USERNAME)
        existing = cur.fetchone()
        if existing:
            cur.execute(
                "UPDATE dbo.AppUsers SET password_hash=?, password_salt=?, role='ADMIN', is_active=1 WHERE username=?",
                hashed, salt, USERNAME
            )
            print(f"[OK] Compte '{USERNAME}' mis à jour (mot de passe réinitialisé).")
        else:
            cur.execute("""
                INSERT INTO dbo.AppUsers
                    (username, email, password_hash, password_salt, role, full_name, department)
                VALUES (?, ?, ?, ?, 'ADMIN', 'Administrateur KHL', 'IT Admin')
            """, USERNAME, EMAIL, hashed, salt)
            print(f"[OK] Compte '{USERNAME}' créé.")

    print(f"  Login    : {USERNAME}")
    print(f"  Password : {PASSWORD}")
except Exception as e:
    print(f"[ERREUR] {e}")
    sys.exit(1)

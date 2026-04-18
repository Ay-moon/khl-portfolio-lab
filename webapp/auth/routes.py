"""
KHL Bank Platform — Authentication Blueprint
Login / Logout / Register avec gestion des rôles métier
"""
import hashlib, secrets, re
from datetime import datetime, timedelta
from flask import (
    Blueprint, render_template, request, redirect, url_for,
    session, flash, g
)
import db, config

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


# ── Helpers ─────────────────────────────────────────────────

def _hash_password(password: str, salt: str) -> str:
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


def _make_salt() -> str:
    return secrets.token_hex(16)


def get_current_user():
    """Retourne l'utilisateur courant depuis la session."""
    if "user_id" not in session:
        return None
    try:
        with db.db_cursor() as cur:
            cur.execute(
                "SELECT user_id, username, email, role, full_name, department "
                "FROM dbo.AppUsers WHERE user_id = ? AND is_active = 1",
                session["user_id"]
            )
            row = cur.fetchone()
            if not row:
                return None
            return {
                "user_id":    row[0],
                "username":   row[1],
                "email":      row[2],
                "role":       row[3],
                "full_name":  row[4],
                "department": row[5],
                "role_info":  config.ROLES.get(row[3], {}),
            }
    except Exception:
        return None


def login_required(f):
    """Décorateur : redirige vers login si non connecté."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Veuillez vous connecter pour accéder à cette page.", "warning")
            return redirect(url_for("auth.login", next=request.path))
        return f(*args, **kwargs)
    return decorated


def role_required(*roles):
    """
    Décorateur : vérifie que l'utilisateur a le bon rôle.
    Si accès refusé → page access_denied.html avec contexte métier complet.
    """
    def decorator(f):
        from functools import wraps
        @wraps(f)
        def decorated(*args, **kwargs):
            if "user_id" not in session:
                flash("Veuillez vous connecter.", "warning")
                return redirect(url_for("auth.login"))
            user = get_current_user()
            if user and (user["role"] in roles or user["role"] == "ADMIN"):
                return f(*args, **kwargs)

            # ── Contexte pour la page d'accès refusé ────────────────
            user_role      = session.get("role", "")
            user_role_info = config.ROLES.get(user_role, {})

            # Trouver le module tenté via l'endpoint Flask
            endpoint   = request.endpoint or ""
            module_key = endpoint.split(".")[0] if "." in endpoint else ""
            module_info = config.MODULES.get(module_key, {
                "label": "cette fonctionnalité",
                "office": "Inconnu",
                "icon": "lock",
            })

            # Rôles autorisés avec leurs infos
            allowed_roles_info = []
            for r in roles:
                ri = config.ROLES.get(r, {})
                allowed_roles_info.append({
                    "role": r,
                    "label": ri.get("label", r),
                    "office": ri.get("office", ""),
                    "color": ri.get("color", "#666"),
                    "icon":  ri.get("icon", "person"),
                })

            return render_template(
                "access_denied.html",
                user_role=user_role,
                user_role_info=user_role_info,
                module_info=module_info,
                module_key=module_key,
                allowed_roles=allowed_roles_info,
                office_meta=config.OFFICE_META,
            ), 403

        return decorated
    return decorator


# ── Routes ──────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if "user_id" in session:
        return redirect(url_for("home"))

    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if not username or not password:
            error = "Identifiant et mot de passe requis."
        else:
            try:
                with db.db_cursor() as cur:
                    cur.execute(
                        "SELECT user_id, username, password_hash, password_salt, role, full_name, is_active "
                        "FROM dbo.AppUsers WHERE username = ?",
                        username
                    )
                    row = cur.fetchone()

                if row is None:
                    error = "Identifiant ou mot de passe incorrect."
                elif not row[6]:  # is_active
                    error = "Compte désactivé. Contactez l'administrateur."
                else:
                    stored_hash = row[2]
                    salt        = row[3]
                    if _hash_password(password, salt) == stored_hash:
                        session["user_id"]  = row[0]
                        session["username"] = row[1]
                        session["role"]     = row[4]
                        # Mise à jour last_login
                        with db.db_cursor() as cur2:
                            cur2.execute(
                                "UPDATE dbo.AppUsers SET last_login = SYSUTCDATETIME() WHERE user_id = ?",
                                row[0]
                            )
                        db.app_log("auth", f"LOGIN OK — {username}", username=username)
                        next_page = request.args.get("next") or url_for("home")
                        return redirect(next_page)
                    else:
                        error = "Identifiant ou mot de passe incorrect."
                        db.app_log("auth", f"LOGIN FAIL — {username}", level="WARN", username=username)
            except Exception as e:
                error = f"Erreur de connexion à la base de données : {e}"

    return render_template("auth/login.html", error=error, roles=config.ROLES)


@auth_bp.route("/logout")
def logout():
    username = session.get("username", "?")
    db.app_log("auth", f"LOGOUT — {username}", username=username)
    session.clear()
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if "user_id" in session:
        return redirect(url_for("home"))

    errors = {}
    form   = {}

    if request.method == "POST":
        form = {k: v.strip() for k, v in request.form.items()}
        username   = form.get("username", "")
        email      = form.get("email", "")
        full_name  = form.get("full_name", "")
        department = form.get("department", "")
        role       = form.get("role", "")
        password   = form.get("password", "")
        confirm    = form.get("confirm_password", "")

        # Validations
        if not username or len(username) < 3:
            errors["username"] = "Minimum 3 caractères."
        elif not re.match(r"^[a-zA-Z0-9_.-]+$", username):
            errors["username"] = "Lettres, chiffres, ., _, - uniquement."

        if not email or "@" not in email:
            errors["email"] = "Email invalide."

        if role not in config.ROLES:
            errors["role"] = "Rôle invalide."

        if len(password) < 6:
            errors["password"] = "Minimum 6 caractères."

        if password != confirm:
            errors["confirm_password"] = "Les mots de passe ne correspondent pas."

        if not errors:
            # Vérif unicité
            try:
                with db.db_cursor() as cur:
                    cur.execute(
                        "SELECT COUNT(*) FROM dbo.AppUsers WHERE username = ? OR email = ?",
                        username, email
                    )
                    if cur.fetchone()[0] > 0:
                        errors["username"] = "Cet identifiant ou email est déjà utilisé."
            except Exception as e:
                errors["db"] = str(e)

        if not errors:
            salt = _make_salt()
            hashed = _hash_password(password, salt)
            try:
                with db.db_cursor() as cur:
                    cur.execute("""
                        INSERT INTO dbo.AppUsers
                            (username, email, password_hash, password_salt, role, full_name, department)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, username, email, hashed, salt, role, full_name, department)
                db.app_log("auth", f"REGISTER — {username} [{role}]", username=username)
                flash(f"Compte créé avec succès ! Bienvenue {full_name or username}.", "success")
                return redirect(url_for("auth.login"))
            except Exception as e:
                errors["db"] = f"Erreur lors de la création : {e}"

    return render_template(
        "auth/register.html",
        errors=errors, form=form, roles=config.ROLES
    )


@auth_bp.route("/forgot", methods=["GET", "POST"])
def forgot_password():
    """Demande de réinitialisation : génère un token affiché à l'écran."""
    if "user_id" in session:
        return redirect(url_for("home"))

    token_generated = None
    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        if not username:
            error = "Veuillez saisir votre identifiant ou email."
        else:
            try:
                with db.db_cursor() as cur:
                    cur.execute(
                        "SELECT username FROM dbo.AppUsers "
                        "WHERE (username = ? OR email = ?) AND is_active = 1",
                        username, username
                    )
                    row = cur.fetchone()

                if row is None:
                    error = "Aucun compte actif trouvé avec cet identifiant ou email."
                else:
                    real_username = row[0]
                    token = secrets.token_hex(6).upper()   # ex: A3F9C2B1D7E4
                    expires_at = datetime.utcnow() + timedelta(minutes=30)
                    with db.db_cursor() as cur:
                        # Invalider les anciens tokens de cet utilisateur
                        cur.execute(
                            "UPDATE dbo.PasswordResetTokens SET used=1 "
                            "WHERE username=? AND used=0",
                            real_username
                        )
                        cur.execute(
                            "INSERT INTO dbo.PasswordResetTokens (username, token, expires_at) "
                            "VALUES (?, ?, ?)",
                            real_username, token, expires_at
                        )
                    db.app_log("auth", f"FORGOT PWD — {real_username}", username=real_username)
                    token_generated = token
            except Exception as e:
                error = f"Erreur : {e}"

    return render_template("auth/forgot_password.html",
                           error=error, token_generated=token_generated)


@auth_bp.route("/reset", methods=["GET", "POST"])
def reset_password():
    """Saisie du token + nouveau mot de passe."""
    if "user_id" in session:
        return redirect(url_for("home"))

    error = None
    success = False
    prefill_token = request.args.get("token", "")

    if request.method == "POST":
        token    = request.form.get("token", "").strip().upper()
        password = request.form.get("password", "")
        confirm  = request.form.get("confirm_password", "")

        if not token:
            error = "Le token est requis."
        elif len(password) < 6:
            error = "Le nouveau mot de passe doit faire au moins 6 caractères."
        elif password != confirm:
            error = "Les mots de passe ne correspondent pas."
        else:
            try:
                with db.db_cursor() as cur:
                    cur.execute(
                        "SELECT token_id, username FROM dbo.PasswordResetTokens "
                        "WHERE token=? AND used=0 AND expires_at > SYSUTCDATETIME()",
                        token
                    )
                    row = cur.fetchone()

                if row is None:
                    error = "Token invalide ou expiré. Faites une nouvelle demande."
                else:
                    token_id = row[0]
                    username = row[1]
                    salt   = _make_salt()
                    hashed = _hash_password(password, salt)
                    with db.db_cursor() as cur:
                        cur.execute(
                            "UPDATE dbo.AppUsers SET password_hash=?, password_salt=? "
                            "WHERE username=?",
                            hashed, salt, username
                        )
                        cur.execute(
                            "UPDATE dbo.PasswordResetTokens SET used=1 WHERE token_id=?",
                            token_id
                        )
                    db.app_log("auth", f"PWD RESET OK — {username}", username=username)
                    success = True
            except Exception as e:
                error = f"Erreur : {e}"

    return render_template("auth/reset_password.html",
                           error=error, success=success, prefill_token=prefill_token)


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    user = get_current_user()
    msg  = None
    if request.method == "POST":
        full_name  = request.form.get("full_name", "").strip()
        department = request.form.get("department", "").strip()
        try:
            with db.db_cursor() as cur:
                cur.execute(
                    "UPDATE dbo.AppUsers SET full_name=?, department=? WHERE user_id=?",
                    full_name, department, user["user_id"]
                )
            msg = "Profil mis à jour."
            db.app_log("auth", "PROFILE UPDATE", username=user["username"])
        except Exception as e:
            msg = f"Erreur : {e}"
    return render_template("auth/profile.html", user=user, msg=msg, roles=config.ROLES)


# ── Administration — Gestion des utilisateurs (ADMIN only) ──

@auth_bp.route("/admin/users")
@login_required
def admin_users():
    """Liste de tous les utilisateurs — ADMIN uniquement."""
    if session.get("role") != "ADMIN":
        flash("Accès réservé à l'administrateur.", "danger")
        return redirect(url_for("home"))

    users = []
    try:
        with db.db_cursor() as cur:
            cur.execute("""
                SELECT user_id, username, email, full_name, department,
                       role, is_active,
                       FORMAT(created_at, 'yyyy-MM-dd') as created_at,
                       FORMAT(last_login, 'yyyy-MM-dd HH:mm') as last_login
                FROM dbo.AppUsers
                ORDER BY is_active DESC, role, username
            """)
            for r in cur.fetchall():
                users.append({
                    "user_id":    r[0], "username": r[1], "email": r[2],
                    "full_name":  r[3], "dept":     r[4], "role":  r[5],
                    "is_active":  bool(r[6]),
                    "created_at": r[7] or "—",
                    "last_login": r[8] or "Jamais",
                })
    except Exception as e:
        flash(f"Erreur chargement utilisateurs : {e}", "danger")

    return render_template("auth/admin_users.html",
                           users=users, roles=config.ROLES)


@auth_bp.route("/admin/users/<int:user_id>/toggle", methods=["POST"])
@login_required
def admin_toggle_user(user_id):
    """Active ou désactive un compte utilisateur."""
    if session.get("role") != "ADMIN":
        flash("Accès réservé à l'administrateur.", "danger")
        return redirect(url_for("home"))

    try:
        with db.db_cursor() as cur:
            cur.execute("SELECT username, is_active FROM dbo.AppUsers WHERE user_id = ?", user_id)
            row = cur.fetchone()
            if not row:
                flash("Utilisateur introuvable.", "danger")
                return redirect(url_for("auth.admin_users"))
            username   = row[0]
            new_status = 0 if row[1] else 1
            cur.execute("UPDATE dbo.AppUsers SET is_active = ? WHERE user_id = ?", new_status, user_id)
        action = "ACTIVATE" if new_status else "DEACTIVATE"
        db.app_log("admin", f"{action} USER — {username}", username=session.get("username"))
        flash(f"Compte {username} {'activé' if new_status else 'désactivé'}.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")

    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/users/<int:user_id>/role", methods=["POST"])
@login_required
def admin_change_role(user_id):
    """Change le rôle d'un utilisateur."""
    if session.get("role") != "ADMIN":
        flash("Accès réservé à l'administrateur.", "danger")
        return redirect(url_for("home"))

    new_role = request.form.get("new_role", "").strip()
    if new_role not in config.ROLES:
        flash("Rôle invalide.", "danger")
        return redirect(url_for("auth.admin_users"))

    try:
        with db.db_cursor() as cur:
            cur.execute("SELECT username FROM dbo.AppUsers WHERE user_id = ?", user_id)
            row = cur.fetchone()
            if not row:
                flash("Utilisateur introuvable.", "danger")
                return redirect(url_for("auth.admin_users"))
            username = row[0]
            cur.execute("UPDATE dbo.AppUsers SET role = ? WHERE user_id = ?", new_role, user_id)
        db.app_log("admin", f"ROLE CHANGE — {username} → {new_role}", username=session.get("username"))
        flash(f"Rôle de {username} changé en {new_role}.", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")

    return redirect(url_for("auth.admin_users"))


@auth_bp.route("/admin/users/<int:user_id>/reset-pwd", methods=["POST"])
@login_required
def admin_reset_pwd(user_id):
    """Génère un token de réinitialisation de mot de passe."""
    if session.get("role") != "ADMIN":
        flash("Accès réservé à l'administrateur.", "danger")
        return redirect(url_for("home"))

    try:
        with db.db_cursor() as cur:
            cur.execute("SELECT username FROM dbo.AppUsers WHERE user_id = ?", user_id)
            row = cur.fetchone()
            if not row:
                flash("Utilisateur introuvable.", "danger")
                return redirect(url_for("auth.admin_users"))
            username = row[0]
            token = secrets.token_hex(6).upper()
            expires_at = datetime.utcnow() + timedelta(minutes=30)
            cur.execute("UPDATE dbo.PasswordResetTokens SET used=1 WHERE username=? AND used=0", username)
            cur.execute(
                "INSERT INTO dbo.PasswordResetTokens (username, token, expires_at) VALUES (?, ?, ?)",
                username, token, expires_at
            )
        db.app_log("admin", f"RESET PWD TOKEN — {username}", username=session.get("username"))
        flash(f"Token généré pour {username} : <strong class='mono'>{token}</strong> (valide 30 min)", "success")
    except Exception as e:
        flash(f"Erreur : {e}", "danger")

    return redirect(url_for("auth.admin_users"))

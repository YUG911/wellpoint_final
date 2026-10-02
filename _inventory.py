import sqlite3

con = sqlite3.connect("file:db.sqlite3?mode=ro", uri=True)
cur = con.cursor()

print("=== TABLES ===")
tables = [r[0] for r in cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
print(", ".join(tables))

print("\n=== ROLES ===")
for r in cur.execute("SELECT role_id, role_name FROM roles ORDER BY role_id"):
    print(" ", r)

print("\n=== USER COUNTS BY ROLE ===")
q = """SELECT r.role_name, COUNT(u.user_id)
       FROM users u LEFT JOIN roles r ON u.role_id = r.role_id
       GROUP BY r.role_name ORDER BY r.role_name"""
for r in cur.execute(q):
    print(f"  {str(r[0]):<14} {r[1]}")

print("\n=== USERS (id, name, email, role, status, verified) ===")
q = """SELECT u.user_id, u.full_name, u.email, r.role_name,
              u.account_status, u.is_verified,
              substr(u.password_hash,1,7), length(u.password_hash)
       FROM users u LEFT JOIN roles r ON u.role_id = r.role_id
       ORDER BY u.user_id"""
for r in cur.execute(q):
    print("  ", r)

print("\n=== LINKED PROFILES ===")
for t in ("patients", "doctors", "clinic_staff", "clinics", "admin"):
    try:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<14} {n} rows")
    except sqlite3.Error as e:
        print(f"  {t:<14} ERROR {e}")

print("\n=== APPOINTMENTS / RECORDS ===")
for t in ("appointments", "patient_records", "prescriptions", "reports",
          "clinic_hours", "verification_logs", "doctor_clinics",
          "doctor_availability", "doctors_availability"):
    try:
        n = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:<22} {n} rows")
    except sqlite3.Error:
        pass

con.close()
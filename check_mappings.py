# save as final_status.py
import sqlite3

conn = sqlite3.connect('namaste_icd11.db')
cursor = conn.cursor()

print("=" * 60)
print("📊 COMPLETE SYSTEM STATUS")
print("=" * 60)

# All codes by system
cursor.execute("SELECT system, COUNT(*) FROM namaste_codes GROUP BY system")
print("\n📋 NAMASTE CODES BY SYSTEM:")
for system, count in cursor.fetchall():
    print(f"  • {system}: {count} codes")

# Mappings by system
cursor.execute("""
    SELECT n.system, COUNT(m.id) 
    FROM namaste_codes n
    LEFT JOIN intelligent_mappings m ON n.code = m.namaste_code
    GROUP BY n.system
""")
print("\n🔗 MAPPINGS BY SYSTEM:")
total_mappings = 0
for system, count in cursor.fetchall():
    print(f"  • {system}: {count} mappings")
    total_mappings += count

# Total
cursor.execute("SELECT COUNT(*) FROM namaste_codes")
total_codes = cursor.fetchone()[0]
print(f"\n📊 TOTAL CODES: {total_codes}")
print(f"📊 TOTAL MAPPINGS: {total_mappings}")
print(f"📈 COVERAGE: {(total_mappings/total_codes*100):.1f}%")

# Sample from each system
print("\n📋 SAMPLE MAPPINGS:")
for system in ['ayurveda', 'siddha', 'unani']:
    cursor.execute("""
        SELECT n.code, m.icd11_code, m.confidence_score
        FROM namaste_codes n
        JOIN intelligent_mappings m ON n.code = m.namaste_code
        WHERE n.system = ?
        LIMIT 2
    """, (system,))
    results = cursor.fetchall()
    if results:
        print(f"\n  {system.upper()}:")
        for code, icd11, conf in results:
            print(f"    • {code} → {icd11} (conf: {conf:.2f})")

conn.close()
print("\n" + "=" * 60)
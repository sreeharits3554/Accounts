#!/usr/bin/env python3
"""Generate jp_upgrade_to_1_8.sql: copies data from an old-schema database
(loaded as `jp_old`) into a fresh structure_1.8 database (the current DB).
Usage: python gen_jp_upgrade.py > jp_upgrade_to_1_8.sql   (needs `mariadb` CLI,
with the old dump in schema `old` and structure_1.8 in schema `t`)."""
import subprocess, sys
SRC, DST = "old", "t"
def cols(db, tb):
    out = subprocess.check_output(["mariadb","-N","-e",
      f"select column_name from information_schema.columns where table_schema='{db}' and table_name='{tb}' order by ordinal_position"]).decode()
    return out.split()
tables = ["users","vehicles","parties","materials","field1_master","field2_master",
          "company_info","app_config","sms_config","whatsapp_config",
          "sms_log","whatsapp_log","audit_log","settings","transactions"]
override = {
 ("users","role"): "IF(CAST(role AS CHAR)='' OR role IS NULL,'user',role)",
 ("app_config","enable_cam1"): "COALESCE(CAST(enable_cam1 AS UNSIGNED),0)",
 ("app_config","enable_cam2"): "COALESCE(CAST(enable_cam2 AS UNSIGNED),0)",
 ("app_config","enable_cam3"): "COALESCE(CAST(enable_cam3 AS UNSIGNED),0)",
}
print("-- Copies data from old-schema database `jp_old` into the CURRENT (structure 1.8) database.")
print("-- Load the old dump into `jp_old`, USE the new database, then run this file.")
print("SET NAMES utf8mb4;\nSET FOREIGN_KEY_CHECKS=0;\nSET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\nSTART TRANSACTION;\n")
for tb in tables:
    common = [c for c in cols(SRC,tb) if c in cols(DST,tb)]
    sel = ", ".join(override.get((tb,c), f"`{c}`") for c in common)
    ins = ", ".join(f"`{c}`" for c in common)
    print(f"INSERT INTO `{tb}` ({ins})\nSELECT {sel} FROM jp_old.`{tb}`;\n")
print("""-- weighment_entries is new in 1.8: back-fill first/second weighments
INSERT INTO weighment_entries (transaction_id, entry_type, weight, charges, gst_percent, gst_amount, total_amount, payment_mode, created_at, stage, weight_value)
SELECT id, 'first', first_weight, COALESCE(charges_first,0), NULL, 0, COALESCE(charges_first,0), 'cash', COALESCE(first_datetime, created_at), 'first', first_weight
FROM transactions WHERE first_weight IS NOT NULL;
INSERT INTO weighment_entries (transaction_id, entry_type, weight, charges, gst_percent, gst_amount, total_amount, payment_mode, created_at, stage, weight_value)
SELECT id, 'second', second_weight, COALESCE(charges_second,0), NULL, 0, COALESCE(charges_second,0), 'cash', COALESCE(second_datetime, created_at), 'second', second_weight
FROM transactions WHERE second_weight IS NOT NULL AND second_weight > 0;

SET @n := (SELECT COALESCE(MAX(id),0)+1 FROM transactions);
COMMIT;
SET FOREIGN_KEY_CHECKS=1;""")

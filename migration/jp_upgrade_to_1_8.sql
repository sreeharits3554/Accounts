-- Copies data from old-schema database `jp_old` into the CURRENT (structure 1.8) database.
-- Load the old dump into `jp_old`, USE the new database, then run this file.
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS=0;
SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';
START TRANSACTION;

INSERT INTO `users` (`id`, `username`, `password`, `full_name`, `role`, `active`, `created_at`)
SELECT `id`, `username`, `password`, `full_name`, IF(CAST(role AS CHAR)='' OR role IS NULL,'user',role), `active`, `created_at` FROM jp_old.`users`;

INSERT INTO `vehicles` (`id`, `vehicle_no`, `owner_phone`, `created_at`)
SELECT `id`, `vehicle_no`, `owner_phone`, `created_at` FROM jp_old.`vehicles`;

INSERT INTO `parties` (`id`, `party_name`, `phone`, `created_at`)
SELECT `id`, `party_name`, `phone`, `created_at` FROM jp_old.`parties`;

INSERT INTO `materials` (`id`, `material_name`, `unit`, `created_at`)
SELECT `id`, `material_name`, `unit`, `created_at` FROM jp_old.`materials`;

INSERT INTO `field1_master` (`id`, `field1_name`)
SELECT `id`, `field1_name` FROM jp_old.`field1_master`;

INSERT INTO `field2_master` (`id`, `field2_name`)
SELECT `id`, `field2_name` FROM jp_old.`field2_master`;

INSERT INTO `company_info` (`id`, `company_name`, `address1`, `address2`, `phone`, `GSTIN`, `email`, `website`, `logo_path`, `paper_size`)
SELECT `id`, `company_name`, `address1`, `address2`, `phone`, `GSTIN`, `email`, `website`, `logo_path`, `paper_size` FROM jp_old.`company_info`;

INSERT INTO `app_config` (`id`, `enable_field_1`, `enable_field_2`, `paper_size`, `updated_at`, `label_first_weight`, `label_second_weight`, `label_field1`, `label_field2`, `label_remarks`, `enable_cameras`, `enable_sms`, `enable_whatsapp`, `enable_manual_first`, `enable_manual_second`, `enable_multi_weigh`, `enable_show_id`, `enable_id_filter`, `enable_cam1`, `enable_cam2`, `enable_cam3`)
SELECT `id`, `enable_field_1`, `enable_field_2`, `paper_size`, `updated_at`, `label_first_weight`, `label_second_weight`, `label_field1`, `label_field2`, `label_remarks`, `enable_cameras`, `enable_sms`, `enable_whatsapp`, `enable_manual_first`, `enable_manual_second`, `enable_multi_weigh`, `enable_show_id`, `enable_id_filter`, COALESCE(CAST(enable_cam1 AS UNSIGNED),0), COALESCE(CAST(enable_cam2 AS UNSIGNED),0), COALESCE(CAST(enable_cam3 AS UNSIGNED),0) FROM jp_old.`app_config`;

INSERT INTO `sms_config` (`id`, `base_url`, `username`, `apikey`, `sender`, `route`, `sms_template`, `dlt_template_id`, `dlt_entity_id`, `is_active`, `created_at`, `updated_at`)
SELECT `id`, `base_url`, `username`, `apikey`, `sender`, `route`, `sms_template`, `dlt_template_id`, `dlt_entity_id`, `is_active`, `created_at`, `updated_at` FROM jp_old.`sms_config`;

INSERT INTO `whatsapp_config` (`id`, `base_url`, `apikey`, `wa_template`, `is_active`, `created_at`, `updated_at`)
SELECT `id`, `base_url`, `apikey`, `wa_template`, `is_active`, `created_at`, `updated_at` FROM jp_old.`whatsapp_config`;

INSERT INTO `sms_log` (`id`, `transaction_id`, `owner_phone`, `party_phone`, `message`, `response`, `created_at`)
SELECT `id`, `transaction_id`, `owner_phone`, `party_phone`, `message`, `response`, `created_at` FROM jp_old.`sms_log`;

INSERT INTO `whatsapp_log` (`id`, `transaction_id`, `mobiles`, `message`, `responses`, `created_at`)
SELECT `id`, `transaction_id`, `mobiles`, `message`, `responses`, `created_at` FROM jp_old.`whatsapp_log`;

INSERT INTO `audit_log` (`id`, `user_id`, `action`, `details`, `created_at`)
SELECT `id`, `user_id`, `action`, `details`, `created_at` FROM jp_old.`audit_log`;

INSERT INTO `settings` (`id`, `company_name`, `logo_path`, `ticket_format`)
SELECT `id`, `company_name`, `logo_path`, `ticket_format` FROM jp_old.`settings`;

INSERT INTO `transactions` (`id`, `serial_no`, `vehicle_id`, `party_id`, `material_id`, `remarks`, `first_weight`, `first_datetime`, `second_weight`, `second_datetime`, `net_weight`, `charges_first`, `charges_second`, `status`, `created_at`, `updated_at`, `field_1`, `field_2`, `third_weight`, `fourth_weight`, `fifth_weight`, `third_net`, `fourth_net`, `fifth_net`, `net_total`, `material2`, `material3`, `material4`, `third_datetime`, `fourth_datetime`, `fifth_datetime`, `snap_camF1`, `snap_camF2`, `snap_camF3`, `snap_camS1`, `snap_camS2`, `snap_camS3`)
SELECT `id`, `serial_no`, `vehicle_id`, `party_id`, `material_id`, `remarks`, `first_weight`, `first_datetime`, `second_weight`, `second_datetime`, `net_weight`, `charges_first`, `charges_second`, `status`, `created_at`, `updated_at`, `field_1`, `field_2`, `third_weight`, `fourth_weight`, `fifth_weight`, `third_net`, `fourth_net`, `fifth_net`, `net_total`, `material2`, `material3`, `material4`, `third_datetime`, `fourth_datetime`, `fifth_datetime`, `snap_camF1`, `snap_camF2`, `snap_camF3`, `snap_camS1`, `snap_camS2`, `snap_camS3` FROM jp_old.`transactions`;

-- weighment_entries is new in 1.8: back-fill first/second weighments
INSERT INTO weighment_entries (transaction_id, entry_type, weight, charges, gst_percent, gst_amount, total_amount, payment_mode, created_at, stage, weight_value)
SELECT id, 'first', first_weight, COALESCE(charges_first,0), NULL, 0, COALESCE(charges_first,0), 'cash', COALESCE(first_datetime, created_at), 'first', first_weight
FROM transactions WHERE first_weight IS NOT NULL;
INSERT INTO weighment_entries (transaction_id, entry_type, weight, charges, gst_percent, gst_amount, total_amount, payment_mode, created_at, stage, weight_value)
SELECT id, 'second', second_weight, COALESCE(charges_second,0), NULL, 0, COALESCE(charges_second,0), 'cash', COALESCE(second_datetime, created_at), 'second', second_weight
FROM transactions WHERE second_weight IS NOT NULL AND second_weight > 0;

SET @n := (SELECT COALESCE(MAX(id),0)+1 FROM transactions);
COMMIT;
SET FOREIGN_KEY_CHECKS=1;

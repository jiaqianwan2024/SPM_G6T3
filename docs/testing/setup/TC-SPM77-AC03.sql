-- TC-SPM77-AC03 (SPM-77): Coordinator notified of shortfall
-- Automated in e2e/spm77.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM77-AC03
-- Empties every table, then loads users, organisations and the records this case uses.
-- Generated from scripts/seed.py; do not edit by hand. Dates are offsets from the time it is loaded.
SET NAMES utf8mb4;
SET @now = UTC_TIMESTAMP();
SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM `user`.`organisations`;
DELETE FROM `user`.`users`;
DELETE FROM `event`.`event_readiness_items`;
DELETE FROM `event`.`events`;
DELETE FROM `event`.`event_assignments`;
DELETE FROM `event`.`event_change_requests`;
DELETE FROM `event`.`event_field_changes`;
DELETE FROM `event`.`event_reschedules`;
DELETE FROM `event`.`event_reviews`;
DELETE FROM `event`.`event_safety_handoffs`;
DELETE FROM `event`.`event_safety_reviews`;
DELETE FROM `event`.`event_status_history`;
DELETE FROM `event`.`event_clarification_replies`;
DELETE FROM `venue`.`venues`;
DELETE FROM `venue`.`venue_activity_log`;
DELETE FROM `venue`.`venue_bookings`;
DELETE FROM `venue`.`venue_unavailability`;
DELETE FROM `equipment`.`equipment_info`;
DELETE FROM `equipment`.`equipment_activity_log`;
DELETE FROM `equipment`.`equipment_requests`;
DELETE FROM `equipment`.`equipment_units`;
DELETE FROM `equipment`.`equipment_reservations`;
DELETE FROM `registration`.`registration_windows`;
DELETE FROM `registration`.`attendee_registrations`;
DELETE FROM `notification`.`notifications`;
-- Users and organisations
INSERT INTO `user`.`organisations` (`organisation_id`, `name`, `created_at`) VALUES ('org-1', 'Apex Partners', @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`organisations` (`organisation_id`, `name`, `created_at`) VALUES ('org-2', 'Beacon Media', @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`organisations` (`organisation_id`, `name`, `created_at`) VALUES ('org-3', 'Solo Studio', @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u1', 'organiser@connectsphere.com', 'Alice Tan', 'organiser', 'org-1', NULL, NULL, NULL, 'pVMDk9zhxaS3fzZIIODBsWQ8bYX2', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u10', 'attendee2@connectsphere.com', 'Gwen Ong', 'attendee', NULL, NULL, NULL, NULL, 'aV9bHDTJk7Z0AHz0SmyJ5EtgXDr2', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u11', 'venue2@connectsphere.com', 'Vera Lim', 'venue', NULL, 'Venues', NULL, NULL, 'VTsPweu5xUdQ9UuIqqxedAh3NZF2', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u12', 'tech2@connectsphere.com', 'Tom Teo', 'techsupport', NULL, 'Technical Support', NULL, NULL, '1quNqjC6ikZnsWBL7rRGLk1qamR2', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u13', 'safety@connectsphere.com', 'Hana Yusof', 'safety', NULL, 'Safety', NULL, NULL, 'wyxrzs6xwLMfQ79KWYuJHLYduwk1', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u14', 'lead@connectsphere.com', 'Rachel Goh', 'coordinatorlead', NULL, 'Events', NULL, NULL, 'xmXcWbsgcAfNHx1f0SmUmeWTey72', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u2', 'coordinator@connectsphere.com', 'Ben Lee', 'coordinator', NULL, 'Events', NULL, NULL, 'MzXojtJGGebRpCVuiPFWZmFpBpQ2', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u3', 'venue@connectsphere.com', 'Vinod Kumar', 'venue', NULL, 'Venues', NULL, NULL, 'Ti2w3jtoG7X8zLqGq4VC3xpYzWH2', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u4', 'tech@connectsphere.com', 'Tia Ho', 'techsupport', NULL, 'Technical Support', NULL, NULL, 'ra3h1S75j3aE74vvJnAF28vb5jG3', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u5', 'attendee@connectsphere.com', 'Amy Wong', 'attendee', NULL, NULL, NULL, NULL, 'fTY5kANfdCcbHPKA8HOWyXxzrHu1', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u6', 'coordinator2@connectsphere.com', 'Cara Ng', 'coordinator', NULL, 'Events', NULL, NULL, 'jkGzDNeZoQSW7Jc1RsEfGOQmEz23', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u7', 'organiser2@connectsphere.com', 'Dana Koh', 'organiser', 'org-2', NULL, NULL, NULL, 'nAAmlnmveNS9it5iKjhpudVhyml1', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u8', 'organiser3@connectsphere.com', 'Evan Ng', 'organiser', 'org-1', NULL, NULL, NULL, 'uaa1CLFA1EN1FOlUSNcSjdE4jKw1', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
INSERT INTO `user`.`users` (`user_id`, `email`, `display_name`, `role`, `organisation_id`, `department`, `phone`, `communication_preferences`, `firebase_uid`, `created_at`, `updated_at`) VALUES ('u9', 'organiser4@connectsphere.com', 'Fay Lim', 'organiser', 'org-3', NULL, NULL, NULL, 'AhHVawglmXQNxhVlVkXvYjwIBIj2', @now + INTERVAL -10 SECOND, @now + INTERVAL -10 SECOND);
-- equipment-eq1
INSERT INTO `equipment`.`equipment_info` (`equipment_id`, `name`, `category`, `description`, `location`, `total_quantity`, `code`, `home_location`, `technical_notes`, `damaged_count`, `maintenance_count`, `retired_count`) VALUES ('eq1', 'Projector PX-200', 'Display', 'Includes HDMI + VGA adapters', 'Marina Hall store', 4, 'eq1', 'Marina Hall store', 'Keep a spare lamp in the same store.', 0, 0, 0);
INSERT INTO `equipment`.`equipment_units` (`unit_id`, `equipment_id`, `status`) VALUES ('u-eq1', 'eq1', 'available');
-- equipment-eq3
INSERT INTO `equipment`.`equipment_info` (`equipment_id`, `name`, `category`, `description`, `location`, `total_quantity`, `code`, `home_location`, `technical_notes`, `damaged_count`, `maintenance_count`, `retired_count`) VALUES ('eq3', 'LED wall panel', 'Display', 'One panel is damaged and stays in the catalogue', 'Exhibition store', 2, 'eq3', 'Exhibition store', 'Do not send the damaged panel out.', 1, 0, 0);
INSERT INTO `equipment`.`equipment_units` (`unit_id`, `equipment_id`, `status`) VALUES ('u-eq3', 'eq3', 'maintenance');
-- event-e3
INSERT INTO `event`.`events` (`event_id`, `organiser_id`, `organisation_id`, `coordinator_id`, `name`, `purpose`, `description`, `category`, `proposed_start_at`, `proposed_end_at`, `expected_attendance`, `venue_requirements`, `accessibility_needs`, `equipment_requirements`, `layout_preference`, `registration_enabled`, `registration_opens_at`, `registration_closes_at`, `capacity`, `status`, `submitted_at`, `created_at`, `updated_at`, `internal_notes`, `organiser_contact`, `preferred_location`, `required_facilities`, `accessibility_note`, `accessibility_selections`, `equipment_lines`, `confirmed_by`, `confirmed_at`, `safety_officer_id`, `cancellation_reason`, `cancelled_by`, `cancelled_at`) VALUES ('e3', 'u1', 'org-1', 'u2', 'Partner Networking Night', 'Informal networking for partner organisations.', 'An evening reception for partner organisations, with short introductions and drinks.', 'Networking', @now + INTERVAL 2592000 SECOND, @now + INTERVAL 2602800 SECOND, 80, 'Banquet layout.', '', 'PA system.', 'Banquet', 0, @now + INTERVAL 345600 SECOND, @now + INTERVAL 1209600 SECOND, 100, 'planning', @now + INTERVAL -432000 SECOND, @now + INTERVAL 0 SECOND, @now + INTERVAL 0 SECOND, NULL, NULL, '', NULL, '', NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL);
INSERT INTO `event`.`event_assignments` (`assignment_id`, `event_id`, `coordinator_id`, `assigned_by`, `assigned_at`) VALUES ('asgn-e3', 'e3', 'u2', 'u2', @now + INTERVAL -432000 SECOND);
INSERT INTO `event`.`event_status_history` (`history_id`, `event_id`, `from_status`, `to_status`, `changed_by`, `note`, `created_at`) VALUES ('hist-e3', 'e3', 'submitted', 'planning', 'u1', 'Seeded demo status', @now + INTERVAL 0 SECOND);
INSERT INTO `equipment`.`equipment_requests` (`request_id`, `event_id`, `equipment_id`, `quantity`, `technical_requirements`, `requested_by`, `status`, `starts_at`, `ends_at`, `reviewed_by`, `review_note`, `created_at`, `reviewed_at`, `decision_reason`, `alternative_equipment_id`, `shortfall`, `reserved_quantity`) VALUES ('eq-shortfall', 'e3', 'eq3', 2, 'LED wall — one unit still unavailable', 'u2', 'partial', @now + INTERVAL 2592000 SECOND, @now + INTERVAL 2602800 SECOND, 'u4', 'Partly fulfilled; one panel still unavailable', @now + INTERVAL -172800 SECOND, NULL, '', NULL, 1, 1);
INSERT INTO `equipment`.`equipment_reservations` (`reservation_id`, `request_id`, `event_id`, `equipment_id`, `quantity`, `starts_at`, `ends_at`, `status`, `needs_reverification`, `reverification_note`) VALUES ('er-e3', 'eq-shortfall', 'e3', 'eq3', 1, @now + INTERVAL 2592000 SECOND, @now + INTERVAL 2602800 SECOND, 'partial', 0, NULL);
SET FOREIGN_KEY_CHECKS = 1;

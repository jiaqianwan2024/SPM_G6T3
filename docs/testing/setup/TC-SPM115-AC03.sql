-- TC-SPM115-AC03 (SPM-115): Original booking remains readable
-- Automated in e2e/spm115.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM115-AC03
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
-- venue-v1
INSERT INTO `venue`.`venues` (`venue_id`, `name`, `location`, `facilities`, `accessibility`, `layouts`, `operating_hours`, `turnaround_minutes`, `is_active`, `created_at`, `code`, `address`, `floor`, `description`, `setup_minutes`, `emergency_access`, `restrictions`) VALUES ('v1', 'Marina Hall A', 'HarbourFront Centre', '[\"Projector\", \"PA system\", \"Video-conferencing\", \"Stage\"]', '[\"Wheelchair accessible\", \"Accessible restrooms nearby\"]', '[{\"name\": \"Theatre\", \"capacity\": 300}, {\"name\": \"Classroom\", \"capacity\": 180}, {\"name\": \"Banquet\", \"capacity\": 220}]', '[{\"day\": \"Mon\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Tue\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Wed\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Thu\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Fri\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Sat\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Sun\", \"opens\": \"00:00\", \"closes\": \"24:00\"}]', 60, 1, @now + INTERVAL 0 SECOND, 'MH-A', '1 HarbourFront Walk, Singapore 098585', '2', 'ConnectSphere\'s largest multipurpose hall.', 30, 'Four exits: two to the waterfront promenade, two to the lift lobby. Assembly point at the promenade. Fire engine access from HarbourFront Walk.', 'No open flames or haze machines. Amplified sound must end by 22:00. Floor load 5 kN/m2.');
-- venue-v3
INSERT INTO `venue`.`venues` (`venue_id`, `name`, `location`, `facilities`, `accessibility`, `layouts`, `operating_hours`, `turnaround_minutes`, `is_active`, `created_at`, `code`, `address`, `floor`, `description`, `setup_minutes`, `emergency_access`, `restrictions`) VALUES ('v3', 'Exhibition Hall B', 'Suntec Singapore Convention & Exhibition Centre', '[\"Loading dock\", \"PA system\", \"Booth power points\"]', '[\"Wheelchair accessible\", \"Accessible restrooms nearby\"]', '[{\"name\": \"Exhibition\", \"capacity\": 500}, {\"name\": \"Theatre\", \"capacity\": 350}]', '[{\"day\": \"Mon\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Tue\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Wed\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Thu\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Fri\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Sat\", \"opens\": \"00:00\", \"closes\": \"24:00\"}, {\"day\": \"Sun\", \"opens\": \"00:00\", \"closes\": \"24:00\"}]', 120, 1, @now + INTERVAL 0 SECOND, 'EH-B', '1 Raffles Boulevard, Singapore 039593', '1', 'Large exhibition space with loading dock access.', 45, 'Eight exits around the hall, two wide enough for vehicles. Assembly point at the north plaza. Emergency vehicles via Temasek Boulevard loading bay.', 'Exhibition stands must keep 3 m aisles to every exit. Generators need the venue\'s approval.');
SET FOREIGN_KEY_CHECKS = 1;

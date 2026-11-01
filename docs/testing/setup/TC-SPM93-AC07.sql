-- TC-SPM93-AC07 (SPM-93): Attendees receive only attendee-visible triggers
-- Automated in e2e/spm93.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM93-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

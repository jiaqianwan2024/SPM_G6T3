-- TC-SPM127-AC01c (SPM-127): Attendees open only confirmed event pages and their own registrations
-- Automated in e2e/spm127.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM127-AC01c
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

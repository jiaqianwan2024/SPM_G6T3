-- TC-SPM127-AC03c (SPM-127): Staff-only and organiser-only pages are 403 for an attendee
-- Automated in e2e/spm127.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM127-AC03c
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

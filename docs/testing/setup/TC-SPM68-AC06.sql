-- TC-SPM68-AC06 (SPM-68): Attendees cannot see threads
-- Automated in e2e/spm68.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM68-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

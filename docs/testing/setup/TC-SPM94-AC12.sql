-- TC-SPM94-AC12 (SPM-94): Mark all read disabled when nothing is unread
-- Automated in e2e/spm94.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM94-AC12
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

-- TC-SPM94-AC01 (SPM-94): Unread count on every screen updates after a read
-- Automated in e2e/spm94.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM94-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

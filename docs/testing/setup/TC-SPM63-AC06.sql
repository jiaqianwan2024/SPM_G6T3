-- TC-SPM63-AC06 (SPM-63): Pending does not lock the venue
-- Automated in e2e/spm63.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM63-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

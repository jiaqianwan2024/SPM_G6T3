-- TC-SPM11-AC01 (SPM-11): Registration succeeds only for confirmed, enabled, in-period events with a place
-- Automated in e2e/spm11.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM11-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

-- TC-SPM11-AC08 (SPM-11): Server enforces the same rules without the UI
-- Automated in e2e/spm11.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM11-AC08
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

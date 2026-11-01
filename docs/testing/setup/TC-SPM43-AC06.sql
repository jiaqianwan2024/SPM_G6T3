-- TC-SPM43-AC06 (SPM-43): Logout prevents Back access
-- Automated in e2e/spm43.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM43-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

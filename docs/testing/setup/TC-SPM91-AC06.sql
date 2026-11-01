-- TC-SPM91-AC06 (SPM-91): Closed or unopened periods excluded
-- Automated in e2e/spm91.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM91-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

-- TC-SPM91-AC05 (SPM-91): Non-open statuses never appear; direct read refused
-- Automated in e2e/spm91.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM91-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

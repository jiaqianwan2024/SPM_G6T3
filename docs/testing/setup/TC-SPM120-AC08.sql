-- TC-SPM120-AC08 (SPM-120): Other roles get 403 on decisions
-- Automated in e2e/spm120.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM120-AC08
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

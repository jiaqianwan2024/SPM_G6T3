-- TC-SPM05-AC02 (SPM-5): Update readiness status
-- Automated in e2e/spm05.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM05-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

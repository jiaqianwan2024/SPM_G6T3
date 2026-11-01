-- TC-SPM90-AC05 (SPM-90): Turning registration off warns, confirms, and notifies
-- Automated in e2e/spm90.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM90-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

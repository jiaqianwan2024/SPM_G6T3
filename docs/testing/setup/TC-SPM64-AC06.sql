-- TC-SPM64-AC06 (SPM-64): Touching windows fine, touching event times can clash
-- Automated in e2e/spm64.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM64-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

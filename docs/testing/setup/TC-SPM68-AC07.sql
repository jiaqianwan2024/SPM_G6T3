-- TC-SPM68-AC07 (SPM-68): Threads remain after later statuses
-- Automated in e2e/spm68.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM68-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

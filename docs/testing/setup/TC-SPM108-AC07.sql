-- TC-SPM108-AC07 (SPM-108): Internal roles can read any calendar
-- Automated in e2e/spm108.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM108-AC07
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

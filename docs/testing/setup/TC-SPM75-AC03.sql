-- TC-SPM75-AC03 (SPM-75): Available = owned − OOS − overlapping
-- Automated in e2e/spm75.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM75-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

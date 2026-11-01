-- TC-SPM93-AC06 (SPM-93): One notification per recipient per occurrence
-- Automated in e2e/spm93.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM93-AC06
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

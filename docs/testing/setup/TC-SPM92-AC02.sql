-- TC-SPM92-AC02 (SPM-92): Upcoming first, then past
-- Automated in e2e/spm92.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM92-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

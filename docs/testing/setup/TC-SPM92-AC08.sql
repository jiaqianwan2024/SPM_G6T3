-- TC-SPM92-AC08 (SPM-92): Empty state points at browsing events
-- Automated in e2e/spm92.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM92-AC08
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

-- TC-SPM92-AC04 (SPM-92): Cancelled events marked cancelled
-- Automated in e2e/spm92.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM92-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

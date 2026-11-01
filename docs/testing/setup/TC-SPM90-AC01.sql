-- TC-SPM90-AC01 (SPM-90): Assigned coordinator sets period and capacity through Confirmed
-- Automated in e2e/spm90.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM90-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

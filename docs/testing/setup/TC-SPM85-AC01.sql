-- TC-SPM85-AC01 (SPM-85): Coordinator sees current, proposed, and reason
-- Automated in e2e/spm85.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM85-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

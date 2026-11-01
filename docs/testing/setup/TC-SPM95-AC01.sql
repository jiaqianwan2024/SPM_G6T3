-- TC-SPM95-AC01 (SPM-95): Daily check selects in-lead-time events with outstanding work
-- Automated in e2e/spm95.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM95-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

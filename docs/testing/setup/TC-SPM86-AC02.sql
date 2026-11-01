-- TC-SPM86-AC02 (SPM-86): Flag visible on event, readiness, calendar, queues
-- Automated in e2e/spm86.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM86-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

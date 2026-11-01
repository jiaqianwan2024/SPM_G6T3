-- TC-SPM73-EXTRA01 (SPM-73): the queue API leaves completed events out unless includeCompleted is set
-- Automated in e2e/spm73.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM73-EXTRA01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

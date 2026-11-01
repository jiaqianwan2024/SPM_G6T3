-- TC-SPM57-AC01b (SPM-57): A long queue is grouped by venue; the venue, event name and event date filters narrow every section and its count
-- Automated in e2e/spm57.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM57-AC01b
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

-- TC-SPM117-AC02 (SPM-117): A newly submitted request stays unassigned until the Lead assigns it
-- Automated in e2e/spm117.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM117-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

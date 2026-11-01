-- TC-SPM93-AC02 (SPM-93): Record fields: recipient, trigger, event, message, link, time, read
-- Automated in e2e/spm93.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM93-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

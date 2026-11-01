-- TC-SPM115-AC05 (SPM-115): Recording a block leaves the event status unchanged
-- Automated in e2e/spm115.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM115-AC05
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

-- TC-SPM118-AC02 (SPM-118): An Event Coordinator who tries to reassign gets 403
-- Automated in e2e/spm118.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM118-AC02
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

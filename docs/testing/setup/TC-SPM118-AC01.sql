-- TC-SPM118-AC01 (SPM-118): The Lead reassigns an event to a different coordinator; the current one cannot be chosen again
-- Automated in e2e/spm118.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM118-AC01
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

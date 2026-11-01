-- TC-SPM118-AC03 (SPM-118): Edit permission moves at once from the previous to the new coordinator
-- Automated in e2e/spm118.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM118-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

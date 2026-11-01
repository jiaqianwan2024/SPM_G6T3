-- TC-SPM81-AC03 (SPM-81): Blank period still submits, flagged outstanding
-- Automated in e2e/spm81.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM81-AC03
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

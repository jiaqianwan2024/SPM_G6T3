-- TC-SPM121-AC04 (SPM-121): Confirm unavailable while the safety check is outstanding, rejected, or returned for changes
-- Automated in e2e/spm121.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM121-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;

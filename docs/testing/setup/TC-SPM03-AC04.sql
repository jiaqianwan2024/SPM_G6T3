-- TC-SPM03-AC04 (SPM-3): Out-of-service units cannot be reserved
-- Automated in e2e/spm03.spec.js. Run on the test database before the test:
--   python scripts/test_setup.py TC-SPM03-AC04
-- Resets every table to the seeded demo data, dated from now.
SOURCE /setup/base.sql;
